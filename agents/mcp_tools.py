import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional

import requests
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agents.common import ReactToolsCallingAgentState, normalize_tool_node
from agents.state import State
from agents.trajectory_manager import tracjectory_manager
from config.config_ui import config as _config
from data_model.messages import AssistantMessage, ToolCall, ToolMessage
from data_model.virtual_mcp_server import VirtualMcpServer
from llm.common import current_llm
from utils.skillberry_api import skillberry_api


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


def normalize_message_content(messages):
    """Convert Anthropic-style content to OpenAI-compatible format"""
    normalized = []
    for msg in messages:
        if hasattr(msg, 'content') and isinstance(msg.content, list):
            # Extract text from [{'text': '...', 'type': 'text'}] format
            text_parts = []
            for item in msg.content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text_parts.append(item.get('text', ''))
            # Create new message with string content
            if hasattr(msg, 'model_copy'):
                # Pydantic v2
                normalized_msg = msg.model_copy(update={'content': ' '.join(text_parts)})
            elif hasattr(msg, 'copy'):
                # Pydantic v1
                normalized_msg = msg.copy(update={'content': ' '.join(text_parts)})
            else:
                # Fallback: create new message of same type
                normalized_msg = type(msg)(content=' '.join(text_parts), **{k: v for k, v in msg.__dict__.items() if k != 'content'})
            normalized.append(normalized_msg)
        else:
            normalized.append(msg)
    return normalized


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

    # Normalize message content to OpenAI format before sending to LLM
    # This creates a temporary copy for the LLM invocation without modifying state
    normalized_messages = normalize_message_content(messages)
    response = state["_llm"].invoke(normalized_messages, config)
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
        
        # Always call pre_hook for all tools
        await pre_hook(self.skillberry_context, assistant_message)

        # MCP adapter to perform the call (manages sessions & MCP URI internally)
        result = await handler(request)

        tool_message = _extract_mcp_result(result, tool_call_id)
        
        # Always call post_hook for all tools
        await post_hook(self.skillberry_context, tool_message)

        # Return the original result
        return result

def create_tool_interceptor(skillberry_context: Dict):
    """Factory function to create a CustomInterceptor with the given context.
    
    Args:
        skillberry_context: The context to pass to the interceptor
        
    Returns:
        CustomInterceptor instance configured with the provided context
    """
    return CustomInterceptor(skillberry_context)


def _create_vmcp_server(skillberry_context: Optional[Dict], skill_uuid: Optional[str]) -> VirtualMcpServer:
    """Create VMCP server with given skill UUID.
    
    This function creates a singleton VMCP server.

    Args:
        skillberry_context: The context for the MCP server (can be None)
        skill_uuid: UUID of skill to use, or None for no skill
        
    Returns:
        VirtualMcpServer instance
        
    Raises:
        ValueError: If server exists with different skill_uuid
    """
    from utils.skillberry_api import skillberry_api

    # Handle None skillberry_context
    if skillberry_context is None:
        logging.warning("skillberry_context is None, using default context")
        skillberry_context = {"env_id": "default"}

    # TODO (weit) hard code
    server_name = "proxy-vmcp-server"
    logging.info(f"Creating VMCP server '{server_name}' with skill_uuid: {skill_uuid}")
    
    # Check if server already exists
    vmcp_server_info = None
    try:
        vmcp_server_info = skillberry_api.get_vmcp_server_details(name=server_name)
        logging.info(f"Found existing VMCP server '{server_name}'")
        
        # # Check if existing server has different skill_uuid
        # existing_skill_uuid = vmcp_server_info.get("skill_uuid")
        # if existing_skill_uuid and skill_uuid and existing_skill_uuid != skill_uuid:
        #     raise ValueError(
        #         f"VMCP server '{server_name}' already exists with skill_uuid '{existing_skill_uuid}', "
        #         f"but requested skill_uuid is '{skill_uuid}'. "
        #         f"Please remove the existing server first or use the same skill_uuid."
        #     )
        
        logging.info(f"Reusing existing VMCP server '{server_name}'")
    except ValueError:
        # Re-raise ValueError for UUID mismatch
        raise
    except Exception as e:
        logging.debug(f"No existing VMCP server found (or error): {e}")
        logging.info(f"Will create new VMCP server '{server_name}'")
    
    # If server doesn't exist, create it
    if vmcp_server_info is None:
        # Create VMCP server
        vmcp_response = skillberry_api.add_vmcp_server(
            name=server_name,
            description="Skillberry MCP Server (singleton)",
            skill_uuid=skill_uuid,
            skillberry_context=skillberry_context
        )
        logging.info(f"VMCP server created with response: {vmcp_response}")
        
        # Get full server details including runtime information
        vmcp_server_info = skillberry_api.get_vmcp_server_details(name=server_name)
        logging.info(f"Retrieved VMCP server info: {vmcp_server_info}")
    
    # Extract necessary fields for VirtualMcpServer
    vmcp_data = {
        "name": vmcp_server_info.get("name") or server_name,
        "description": vmcp_server_info.get("description") or "Proxy MCP Server",
        "port": vmcp_server_info.get("port"),
        "tools": vmcp_server_info.get("runtime", {}).get("tools", [])
    }
    logging.info(f"Constructed VMCP data: {vmcp_data}")
    
    server = VirtualMcpServer(**vmcp_data)
    
    logger.info(f"Successfully created VMCP server on port {server.port}")
    
    return server


def _resolve_skill_uuid(
    skill_name: Optional[str],
    skill_uuid: Optional[str],
    enable_skill_search: bool
) -> Optional[str]:
    """
    Resolve skill UUID based on provided parameters.
    
    Args:
        skill_name: Name of the skill to resolve
        skill_uuid: Direct UUID specification
        enable_skill_search: Whether to enable runtime skill search
        
    Returns:
        Resolved skill UUID or None
        
    Raises:
        NotImplementedError: If enable_skill_search is True (not yet implemented)
    """

    # Determine mode and resolve skill_uuid accordingly
    if enable_skill_search:
        # Runtime mode: Not currently implemented in mcp_tools
        logging.error("[RUNTIME MODE] Skill search enabled - VMCP creation on-demand is not currently implemented in mcp_tools()")
        raise NotImplementedError("Runtime skill search mode (enable_skill_search=True) is not currently implemented in mcp_tools()")
            
    elif skill_uuid:
        # Build-time mode: Direct UUID specification
        logging.info(f"[BUILD-TIME] Using explicit skill UUID: {skill_uuid}")
        return skill_uuid
        
    elif skill_name:
        # Build-time mode: Get skill by name
        logging.info(f"[BUILD-TIME] Getting skill by name: '{skill_name}'")
        try:
            skill_data = skillberry_api.get_skill(skill_name)
            if skill_data:
                resolved_skill_uuid = skill_data.get("uuid")
                if resolved_skill_uuid:
                    logging.info(f"[BUILD-TIME] Resolved skill '{skill_name}' to UUID: {resolved_skill_uuid}")
                    return resolved_skill_uuid
                else:
                    logging.warning(f"Skill '{skill_name}' found but has no UUID, creating VMCP without skill")
                    return None
            else:
                logging.warning(f"No skill data returned for skill name: '{skill_name}', creating VMCP without skill")
                return None
        except requests.exceptions.HTTPError as e:
            logging.warning(f"HTTP error while getting skill '{skill_name}': {e}. Creating VMCP without skill")
            return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request error while getting skill '{skill_name}': {e}. Creating VMCP without skill")
            return None
        except Exception as e:
            logging.warning(f"Unexpected error while getting skill '{skill_name}': {e}. Creating VMCP without skill")
            return None
            
    else:
        # Fallback mode: Use domain-based search (backward compatibility)
        logging.warning("[DEFAULT MODE] No skill specified, using domain-based search")
        search_term = "airline"  # Default search term
        logging.info(f"Searching for skill with search term: '{search_term}'")
        try:
            resolved_skill_uuid = skillberry_api.find_skill_uuid_by_search(search_term)
            if resolved_skill_uuid:
                logging.info(f"Found skill UUID: {resolved_skill_uuid} for search term: '{search_term}'")
                return resolved_skill_uuid
            else:
                logging.warning(f"No skill found for search term: '{search_term}', creating VMCP without skill")
                return None
        except requests.exceptions.HTTPError as e:
            logging.warning(f"HTTP error while searching for skill with term '{search_term}': {e}. Creating VMCP without skill")
            return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request error while searching for skill with term '{search_term}': {e}. Creating VMCP without skill")
            return None
        except Exception as e:
            logging.warning(f"Unexpected error while searching for skill with term '{search_term}': {e}. Creating VMCP without skill")
            return None


def mcp_tools(state: State):
    """
    Defines and compiles a LangGraph workflow for a react-style agent, connecting
    LLM and tool nodes with conditional logic to control execution flow.

    Note: This method/node selects the proper MCP server (using context) for LLM completion.

    The function accepts skill_name, skill_uuid, and enable_skill_search from state:
    - If skill_uuid is provided, it will be used directly
    - If skill_name is provided, it will be resolved to skill_uuid
    - If enable_skill_search is True, runtime skill search will be performed
    - If none are provided, raises NotImplementedError (fallback logic not yet implemented)
    
    The MCP server is removed upon "disconnect" control command (once the scenario completes).

    """
    logging.info(f"=======>>> Node: mcp_tools. started <<<=======")
    thinking_log = ""

    chat_history = state["chat_history"]
    skillberry_context = state["skillberry_context"]
    skill_name = state.get("skill_name")
    skill_uuid = state.get("skill_uuid")
    enable_skill_search = state.get("enable_skill_search", False)

    # Resolve skill UUID using helper method
    try:
        resolved_skill_uuid = _resolve_skill_uuid(skill_name, skill_uuid, enable_skill_search)
    except NotImplementedError as e:
        return {
            "messages": [
                {
                    "role": "ai",
                    "content": str(e),
                }
            ]
        }

    # Get or create singleton server with resolved skill_uuid
    logging.info(f"Getting/creating singleton MCP server with skill_uuid: {resolved_skill_uuid}")

    # Create the vmcpserver and provide it with the context.
    # This context is then forwarded to the tools execution environment (the handler() function).
    # The environment ID (env_id) is propagated throughout the tools’ runtime to ensure that all
    # operations are performed on the correct environment instance.
    server = _create_vmcp_server(skillberry_context, skill_uuid=resolved_skill_uuid)

    port = server.port
    
    # Get tools from the MCP server and cache them (matching Tau2 pattern)
    logging.info(f"[MCP DEBUG] Getting MCP tools from port: {port}")
    from utils.skillberry_api import skillberry_api
    
    # Create tool interceptor with the skillberry context
    interceptor = create_tool_interceptor(skillberry_context)
    
    # Get tools with the interceptor
    tools = skillberry_api.get_mcp_tools(
        port=port,
        server_name=server.name,
        tool_interceptors=[interceptor]
    )
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
                            "output": "Sorry, failed to answer using skillberry (tools binding)"
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
    workflow.add_node(ToolNode(tools))
    
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
                        f"Sorry, failed to answer using skillberry (invoke react agent)",
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
        output_content = "Sorry, failed to answer using skillberry (json.dumps)"

    logger.info(f"output_content: {output_content}")

    messages = [{"role": "ai", "content": output_content}]
    logging.info(f"=======>>> Node: mcp_tools. ended <<<=======")
    return {"messages": messages, "thinking_log": thinking_log}
