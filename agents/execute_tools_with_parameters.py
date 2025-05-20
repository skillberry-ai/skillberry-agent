import json
import logging

from langchain_core.language_models import LanguageModelInput
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from agents.remote_tools_wrapper import generate_dynamic_tool
from agents.state import State
from config.config_ui import config as _config
from llm.common import llm

from typing import Annotated, Sequence, TypedDict, Union, Dict, Any, Type, Callable, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph.message import add_messages
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

tools_repo_base_url = _config.get("tools_repo_base_url")

headers = {"Accept": "application/json"}

execute_tools_with_parameters_chat_prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", "You are an expert in invocation function and tools"),
        (
            "system",
            "If a tool returns no results or fails,consider using a different tool or approach",
        ),
        (
            "system",
            "Provide a final response only when you're confident you have sufficient information",
        ),
        (
            "system",
            "You use the observations from the tools to provide accurate responses",
        ),
        (
            "system",
            "The final response should not provide any names or descriptions of used functions and tools",
        ),
        (
            "system",
            "The final response should not include explanations about the tool calling process",
        ),
        "{chat_history}",
    ]
)


class ReactToolsCallingAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    _tools: Sequence[Union[Dict[str, Any], Type, Callable, BaseTool]]
    _llm: LanguageModelInput


def tool_node(state: ReactToolsCallingAgentState):
    def get_tool(_tool_name: str):
        for _tool in state["_tools"]:
            if _tool.name == _tool_name:
                return _tool
        return None

    def parse_tool_call_from_content(content: str) -> Optional[List[Dict[str, Any]]]:
        for i in range(len(content), 0, -1):
            try:
                parsed = json.loads(content[:i])
                return [{
                    "type": parsed.get("type", "function"),
                    "name": parsed.get("name", ""),
                    "args": parsed.get("parameters", {}),
                    "id": parsed.get("id", f"{i}"),
                }]
            except json.JSONDecodeError:
                continue
        return None

    outputs = []
    thinking_log = ""
    last_message = state["messages"][-1]

    # Check if the content of the tool is in the last message content
    if not last_message.tool_calls:
        # parse the tool call from the content
        tool_calls = parse_tool_call_from_content(last_message.content)
        if tool_calls is None:
            logging.error(
                f"tool_node: The tool call was not found in the content: {last_message.content}"
            )
            thinking_log += (
                "skipping tool call. "
            )
            outputs.append(
                SystemMessage(
                    f"Could not find the tool call in the content: {last_message.content}"
                )
            )
            return {"messages": outputs, "thinking_log": thinking_log}
        else:
            # Set the .tools_calls  of the last message
            # to the parsed tool calls
            last_message.tool_calls = tool_calls

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

        if tool_invocation_status is "success":
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
        else:
            thinking_log += f"calling the tool {tool_name} failed. "

    return {"messages": outputs, "thinking_log": thinking_log}


def call_llm_model_node(state: ReactToolsCallingAgentState, config: RunnableConfig):
    last_message = state["messages"][-1]
    logging.info(f"=====> Calling LLM to response.)")
    logging.info(f"Latest message is: {last_message}")
    response = state["_llm"].invoke(state["messages"], config)
    return {"messages": [response]}


def should_continue(state: ReactToolsCallingAgentState):
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls:
        # if one of the tool names is found inside the message, skip
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


def generate_list_of_tools(state: State):
    _tools = []
    scope = {}

    for _tool in state["existing_tools"]:
        try:
            logging.info(f"existing_tools: Generating local tool stub {_tool['name']}")
            tool_func = generate_dynamic_tool(_tool, scope, tools_repo_base_url)
            _tools.append(tool_func)
        except Exception as e:
            logging.error(
                f"existing_tools: Error while generate_dynamic_tool {_tool['name']}: {e}"
            )

    for _tool in state["generated_tools"]:
        try:
            logging.info(f"existing_tools: Generating local tool stub {_tool['name']}")
            tool_func = generate_dynamic_tool(_tool, scope, tools_repo_base_url)
            _tools.append(tool_func)
        except Exception as e:
            logging.error(
                f"need_to_generate_tools: Error while generate_dynamic_tool {_tool['name']}: {e}"
            )

    return _tools


# execute the tools with the parameters
def execute_tools_with_parameters(state: State):
    thinking_log = ""
    logging.info(f"=======>>> execute_tools_with_parameters. started <<<=======")

    # get the original chat history from the state
    chat_history = state["chat_history"]

    # Generate the list of tools
    _tools = generate_list_of_tools(state)

    # bind the tools to the LLM
    try:
        if not _tools:
            thinking_log += (
                "I don't have any tools to use. using the LLM model as-is to response. "
            )
            logging.info(f"=====> No tools, not binding")
            _llm_with_tools = llm
        else:
            thinking_log += "I will now use the tools and the LLM model to respond. "
            logging.info(f"=====> Binding tools: {_tools}")
            _llm_with_tools = llm.bind_tools(
                tools=_tools, tool_choice="auto", strict=True
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

    # Use a React tool calling agent
    # Define a new graph
    workflow = StateGraph(ReactToolsCallingAgentState)

    # Define the nodes
    workflow.add_node("llm", call_llm_model_node)
    workflow.add_node("tools", tool_node)

    # Set the entrypoint as `llm`
    workflow.set_entry_point("llm")

    # Add edges
    workflow.add_edge("tools", "llm")
    workflow.add_conditional_edges(
        "llm",
        should_continue,
        {
            "continue_call_tools": "tools",
            "end": END,
        },
    )

    # compile the graph
    react_tools_graph = workflow.compile()

    # Helper function for formatting the stream nicely
    def trace_stream(stream):
        _final_message = None

        for s in stream:
            message = s["messages"][-1]
            logging.info(message)
            _final_message = message
        return _final_message

    # Building the basic prompt for the React tools agent
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
                    "_tools": _tools,
                    "_llm": _llm_with_tools,
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
