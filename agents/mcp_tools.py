import asyncio
import json
import logging
import uuid
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from langchain_mcp_adapters.client import MultiServerMCPClient

from agents.common import ReactToolsCallingAgentState, normalize_tool_node
from agents.remote_tools_wrapper import TOOLS, GENERATED_TOOLS
from agents.state import State
from agents.vmcp_server_manager import vmsm
from agents.trajectory_manager import tracjectory_manager
from config.config_ui import config as _config
from data_model.messages import AssistantMessage, ToolCall, ToolMessage
from llm.common import current_llm
from utils.utils import extract_base_url


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


def call_llm_model_node(state: ReactToolsCallingAgentState, config: RunnableConfig) -> Dict:
    """
    Calls LLM model passing it all messages. The response message is appended to messages
    list.

    Args:
        state (ReactToolsCallingAgentState): The state of the graph
        config (RunnableConfig): The configuration of the graph

    Returns:
        Dict: The response to be added to messages list (in dict format)
    """
    messages = state["messages"]
    last_message = state["messages"][-1]

    logging.info(f"=====> Calling LLM to response (call_llm_model_node).")
    logging.info(f"Latest message is: {last_message}")

    response = state["_llm"].invoke(messages, config)
    return {"messages": [response]}


async def pre_hook(skillberry_context: Dict, assistant_message: AssistantMessage) -> None:
    """
    pre-hook. Append assistant message to trajectory.
    """
    logging.info (f"pre_hook: {skillberry_context}, {assistant_message}")
    tracjectory_manager.add_message(skillberry_context, assistant_message)


async def post_hook(skillberry_context: Dict, tool_message: ToolMessage) -> None:
    """
    post-hook. Append tool result to trajectory.
    """
    logging.info(f"post_hook: {skillberry_context}, {tool_message}")
    tracjectory_manager.add_message(skillberry_context, tool_message)


def _extract_mcp_request(request: Any) -> AssistantMessage:
    """
    Fills up an assistant message out from the request.

    Note: MCPToolCallRequest does not have tool_call_id notion so we
    generate such ourselves.
    """
    logging.info(f"Enter _extract_mcp_request (request): {request}")
    assert request.name, "Cannot extract tool name from MCP request"
    assert request.args, "Cannot extract tool args from MCP request"

    tool_name = request.name
    args = request.args

    tool_call_id = f"chatcmpl-tool-{uuid.uuid4().hex}"

    assistant_message = AssistantMessage(
        role="assistant",
        tool_calls=[ToolCall
            (
                id=tool_call_id,
                name=tool_name,
                arguments=args
            )
        ]
    )

    logging.info(f"Exit _extract_mcp_request (assistant_message): {assistant_message}")
    return assistant_message, tool_call_id


def _extract_mcp_result(result: Any, too_call_id: str = "") -> ToolMessage:
    """
    Fills up a tool message (result) out from the result along with the passed
    tool call id (the ID of the tool call message).

    """
    logging.info(f"Enter _extract_mcp_result (result): {result}")

    is_error = result.isError
    raw_text = result.content[0].text if result.content else ""

    tool_message = ToolMessage(
        # Note: in tau2 environment manager there is no id
        id=too_call_id,
        content=raw_text,
        requestor="assistant",
        role="tool",
        error=is_error
    )

    logging.info(f"Exit _extract_mcp_result (tool_message): {tool_message}")
    return tool_message 


class CustomInterceptor:
    def __init__(self, skillberry_context: Dict):
        """
        Initialize this with provided context.

        Args:
            skillberry_context (Dict): The context
        """
        self.skillberry_context = skillberry_context

    async def __call__(
        self,
        request,
        handler,
    ):
        """
        This method is called whenever the middleware decides to call an MCP tool.
        The method is responsible to properly correlate between call and result via ID.
    
        If tool call is of generated tool - the call and response are added to a local trajectory
        store managed by the agent.

        Args:
            request (Any): Tool call request
            handler (Any): Tool invocation entry point

        Returns:
            Any: Tool result
        """
        assistant_message, tool_call_id = _extract_mcp_request(request)
        tool_name = assistant_message.tool_calls[0].name
        if tool_name in GENERATED_TOOLS:
            await pre_hook(self.skillberry_context, assistant_message)

        # MCP adapter to perform the call (manages sessions & MCP URI internally)
        result = await handler(request)

        tool_message = _extract_mcp_result(result, tool_call_id)
        if tool_name in GENERATED_TOOLS:
            await post_hook(self.skillberry_context, tool_message)

        # Return the original result
        return result


def mcp_tools(state: State):
    """
    Defines and compiles a LangGraph workflow for a react-style agent, connecting
    LLM and tool nodes with conditional logic to control execution flow.

    Note: This method/node selects the proper MCP server (using context) for LLM completion.

    If no MCP server is found out from the given context, a new MCP server is created using
    the skill-based approach. The skill is found by searching the Skillberry Store using
    "airline" as the search term (matching Tau2 LangChain agent pattern).
    
    The MCP server is removed upon "disconnect" control command (once the scenario completes).

    """
    logging.info(f"=======>>> Node: mcp_tools. started <<<=======")
    thinking_log = ""

    chat_history = state["chat_history"]
    skillberry_context = state["skillberry_context"]

    try:
        server = vmsm.get_server(skillberry_context)
        logging.info(f"Found existing MCP server: {server.name} on port {server.port}")
    except: # not found
        # Use skill-based approach (similar to Tau2 LangChain agent)
        # Using "airline" as the search term to find airline-related skills
        search_term = "airline"
        
        logging.info(f"Creating MCP server using skill-based approach with search term: '{search_term}'")
        server = vmsm.add_server(
            skillberry_context,
            skill_search_term=search_term
        )

    port = server.port
    
    # Get tools from the MCP server and cache them (matching Tau2 pattern)
    logging.info(f"[MCP DEBUG] Getting MCP tools from port: {port}")
    from utils.tools_service_api import tools_service
    tools = tools_service.get_mcp_tools(port=port, server_name=server.name)
    logging.info(f"[MCP DEBUG] Retrieved {len(tools)} tools from MCP server")
    for idx, tool in enumerate(tools):
        tool_name = getattr(tool, "name", "unknown")
        tool_desc = getattr(tool, "description", "no description")
        logging.info(f"[MCP DEBUG] Tool {idx+1}: name='{tool_name}', description='{tool_desc}'")

    logging.info(f"MCP TOOLS -=-=-=-=-=-=-=-=-=- {tools} -=-=-=-=-=-=-=-=-=-=-=-=-=-")
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

    # 3. Define the graph
    workflow = StateGraph(ReactToolsCallingAgentState)
    workflow.set_entry_point("llm")

    workflow.add_node("llm", call_llm_model_node)
    workflow.add_node("normalize", normalize_tool_node)
    
    # Wrap ToolNode to convert list-format content to string format for OpenAI compatibility
    original_tool_node = ToolNode(tools)
    
    async def convert_tool_messages_node(state: ReactToolsCallingAgentState) -> Dict[str, Any]:
        """
        Convert LangGraph tool message format to OpenAI-compatible format.
        LangGraph's ToolNode produces content as: [{'text': '...', 'type': 'text'}]
        OpenAI API expects content as: "..."
        """
        # Call original ToolNode asynchronously
        result = await original_tool_node.ainvoke(state)
        
        # Convert message content from list to string
        messages = result.get("messages", [])
        for msg in messages:
            if hasattr(msg, 'content') and isinstance(msg.content, list):
                # Extract text from list format
                if msg.content and isinstance(msg.content[0], dict) and 'text' in msg.content[0]:
                    msg.content = msg.content[0]['text']
                elif msg.content:
                    # Fallback: convert entire list to string
                    msg.content = str(msg.content)
                else:
                    msg.content = ""
        
        return {"messages": messages}
    
    workflow.add_node("tools", convert_tool_messages_node)

    workflow.add_edge("llm", "normalize")
    workflow.add_edge("tools", "llm")
    workflow.add_conditional_edges(
        "normalize",
        tools_condition,
    )

    graph = workflow.compile()

    async def trace_stream(stream):
        """
        Helper function for formatting the stream nicely

        """
        _final_message = None

        async for s in stream:
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
        llm_messages = original_chat_messages.to_messages()

        # 4. Invoke the graph
        final_message = asyncio.run (trace_stream(graph.astream(
            {
                "messages": llm_messages,
                "_llm": llm_with_tools
            },
            {
                "recursion_limit": recursion_limit,
                "max_execution_time": 120
            },
            stream_mode="values",
        )))
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

    # 5. Build final response
    try:
        ai_response = final_message.content
        logging.info (f"final AI response: {final_message.content} given from: {llm_messages}")
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
    logging.info(f"=======>>> Node: mcp_tools. ended <<<=======")
    return {"messages": messages, "thinking_log": thinking_log}
