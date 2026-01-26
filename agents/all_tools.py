import json
import logging
from typing import Dict

from config.config_ui import config as _config

from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from langgraph.graph import StateGraph, END

from agents.common import (
    normalize_tool_node,
    parse_tool_call_from_content,
    ReactToolsCallingAgentState,
)
from agents.remote_tools_wrapper import generate_dynamic_tool, TOOLS, GENERATED_TOOLS
from agents.state import State

from llm.common import current_llm


logger = logging.getLogger(__name__)


execute_tools_with_parameters_chat_prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", "You are an expert assistant"),
        (
            "system",
            "If a tool returns an exception, and error, no result or any other failure, "
            "return to the user immediately! and the user to provide additional information or clarification. "
            "DO NOT try to call any additional tools or functions until the user provides additional information or clarification.",
        ),
        (
            "system",
            "Try to use tools and ask the user for clarification and additional information as much as possible. "
            " If, and only if this completely fails, use the transfer_to_human_agents tool.",
        ),
        "{chat_history}",
        (
            "system",
            "DO NOT USE the transfer_to_human_agents tool !!!",
        ),
    ]
)


def tool_node(state: ReactToolsCallingAgentState):
    def get_tool(_tool_name: str):
        for _tool in state["_tools"]:
            if _tool.name == _tool_name:
                return _tool
        return None

    outputs = []
    thinking_log = ""
    last_message = state["messages"][-1]

    # Check if the content of the tool is in the last message content
    if not last_message.tool_calls:
        # parse the tool call from the content
        tool_calls = parse_tool_call_from_content(last_message.content)
        assert tool_calls is None, f"last_message.content should not contain tool_call (due to normalize step)"

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        logging.info(
            f"=====> The agentic flow will now call the function {tool_name} with args {tool_args}"
        )
        tool_function = get_tool(tool_name)
        if tool_function is None:
            raise ValueError(f"tool_node: The Tool {tool_name} was not found")

        tool_invocation_status = "success"
        try:
            tool_result = tool_function.invoke(tool_args)
            logging.info(
                f"=====> The agentic flow called the function {tool_name}\n"
                f"=====> With args {tool_args} and got result: {tool_result}\n"
            )

            if tool_result is None or tool_result == "" or tool_result == "None":
                logging.error(
                    f"=====> The tool {tool_name} returned None or empty string\n!!! failure !!!\n"
                )
                tool_invocation_status = "error"

            if "EXCEPTION:" in tool_result:
                logging.error(
                    f"=====> The tool {tool_name} returned an exception\n!!! failure !!!\n"
                )
                tool_invocation_status = "error"
                
            # check if ToolMessage already exist in the previous messages
            # with the same response. If so fail the tool
            for message in state["messages"]:
                if isinstance(message, ToolMessage):
                    if message.content == tool_result:
                        logging.error(
                            f"=====> The tool {tool_name} was already called by the agent, "
                            f"and returned the same response: {tool_result}"
                            f"\n!!! failure !!!\n"
                        )
                        outputs.append(
                            SystemMessage(
                                f"A previous call to {tool_name} with parameters {tool_args} "
                                f"already resulted {tool_result} !!!"
                                f"Do not invoke the {tool_name} again with the parameters {tool_args} !!! "
                                f"Continue to response to the user without calling {tool_name} "
                                f"with the parameters {tool_args} !!!"
                            )
                        )
                        tool_invocation_status = "error"

        except Exception as e:
            logging.error(f"tool_node: Error while calling tool {tool_name}: {e}")
            tool_invocation_status = "error"
            tool_result = ""

        outputs.append(
            ToolMessage(
                status=tool_invocation_status,
                content=tool_result,
                artifact=tool_result,
                type="tool",
                tool_call_id=tool_call["id"],
                id=tool_call["id"],
            )
        )

        # Add the appropriate log message
        if tool_invocation_status == "success":
            thinking_log += f"calling the tool {tool_name} succeeded. "
        elif tool_invocation_status == "error":
            thinking_log += f"calling the tool {tool_name} failed with exception. "
        else:
            thinking_log += f"calling the tool {tool_name} failed. "

    logging.info (f"[WEIT] Exit with: {len(outputs)}")
    return {"messages": outputs, "thinking_log": thinking_log}


def call_llm_model_node(state: ReactToolsCallingAgentState, config: RunnableConfig):
    last_message = state["messages"][-1]
    logging.info(f"=====> Calling LLM to response (call_llm_model_node).")
    logging.info(f"Latest message is: {last_message}")
    response = state["_llm"].invoke(state["messages"], config)
    return {"messages": [response]}


def should_continue(state: ReactToolsCallingAgentState) -> str:
    """
    Special node to determine whether to continue with calling tools or retuning from the
    state graph i.e. returning final response to the user.
 
    Args:
        state (ReactToolsCallingAgentState): the current state of the graph (i.e.
                                             messages, etc)

    Returns:
        str: the string to be interpreted by the state graph orchestrator (i.e. "end"
             or "continue_tool_calls")
    """
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls:
        # if one of the tool names is found inside the message, skip
        # TODO (weit): remove this
        for tool in state["_tools"]:
            if tool.name in str(last_message.content):
                logging.info(f"=====> Tool name was found in the content")
                return "continue_call_tools"

        logging.info(
            f"=====> The agentic flow will now return to the user (no more tool_calls)"
        )
        return "end"
    else:
        logging.info(f"=====> The agentic flow will continue, calling additional tools")
        return "continue_call_tools"


def all_tools(state: State):
    """
    Defines and compiles a LangGraph workflow for a react-style agent, connecting
    LLM and tool nodes with conditional logic to control execution flow.

    Note: This method/node selects all TAu-2 tools for LLM completion.

    """
    logging.info(f"=======>>> execute_tools_with_parameters. started <<<=======")
    thinking_log = ""

    chat_history = state["chat_history"]
    skillberry_context = state["skillberry_context"]

    # Generate the list of tools
    tools = generate_list_of_tools(skillberry_context)
    try:
        if not tools:
            thinking_log += (
                "I don't have any tools to use. using the LLM model as-is to response. "
            )
            logging.info(f"=====> No tools, not binding")
            llm_with_tools = current_llm.llm
        else:
            thinking_log += "I will now use the tools and the LLM model to respond. "
            logging.info(f"=====> Binding tools: {tools}")
            llm_with_tools = current_llm.llm.bind_tools(
                tools=tools, tool_choice="auto"
            )

    except Exception as e:
        logging.error(f"Error while binding tools: {e}")
        return {
            "messages": [
                {
                    "role": "ai",
                    "content": json.dumps(
                        {
                            "output": "Sorry, failed to answer using blueberry (tools binding)"
                        },
                        indent=4,
                    ),
                }
            ]
        }

    workflow = StateGraph(ReactToolsCallingAgentState)
    workflow.set_entry_point("llm")

    workflow.add_node("llm", call_llm_model_node)
    workflow.add_node("normalize", normalize_tool_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge("llm", "normalize")
    workflow.add_edge("tools", "llm")
    workflow.add_conditional_edges(
        "normalize",
        should_continue,
        {
            "continue_call_tools": "tools",
            "end": END,
        },
    )

    react_tools_graph = workflow.compile()

    def trace_stream(stream):
        """
        Helper function for formatting the stream nicely

        """
        _final_message = None

        for s in stream:
            message = s["messages"][-1]
            logging.info(message)
            _final_message = message
        return _final_message

    original_chat_messages = execute_tools_with_parameters_chat_prompt_template.invoke(
        chat_history
    )

    try:
        logging.info(f"=====> Invoking the tools react agent")
        recursion_limit = _config.get("tools_react_agent__recursion_limit")
        final_message = trace_stream(
            react_tools_graph.stream(
                {
                    "messages": original_chat_messages.to_messages(),
                    "_tools": tools,
                    "_llm": llm_with_tools,
                },
                {"recursion_limit": recursion_limit, "max_execution_time": 120},
                stream_mode="values",
            )
        )
    except Exception as e:
        logging.error(f"Error while streaming to the react agent: {e}")
        return {
            "messages": [
                {
                    "role": "ai",
                    "content": json.dumps(
                        f"Sorry, failed to answer using blueberry (invoke react agent)",
                        indent=4,
                    ),
                }
            ]
        }

    logger.info(
        f"=====> The agentic flow has finished executing the tools with parameters"
    )
    try:
        ai_response = final_message.content

        thinking_log += f"I am done. Returning a response to the user."
        session_thinking_log_as_str = ""
        for state_thinking_log in state["thinking_log"]:
            session_thinking_log_as_str = " ".join(
                [session_thinking_log_as_str, state_thinking_log.content]
            )
        session_thinking_log_as_str = " ".join(
            [session_thinking_log_as_str, thinking_log]
        )

        output_content = f"<think>{session_thinking_log_as_str}</think>\n{ai_response}"
    except Exception as e:
        logging.error(f"Error while json.dumps: {e}")
        output_content = "Sorry, failed to answer using blueberry (json.dumps)"

    logger.info(f"output_content: {output_content}")

    messages = [{"role": "ai", "content": output_content}]
    logging.info(f"=======>>> execute_tools_with_parameters. ended <<<=======")
    return {"messages": messages, "thinking_log": thinking_log}


def generate_list_of_tools(skillberry_context: Dict):
    """
    Translates tau-2 tools into OpenAI callable tools.

    """
    tools = []
    scope = {}

    TOTAL_TOOLS = TOOLS + GENERATED_TOOLS

    for tool_name in TOTAL_TOOLS:
        try:
            tool_func = generate_dynamic_tool(tool_name, scope, skillberry_context=skillberry_context)
            tools.append(tool_func)
        except Exception as e:
            logging.error(
                f"generate_list_of_tools: Error in generate_dynamic_tool {tool_name}: {e}"
            )

    return tools
