import logging
from typing import Any, Dict, List
import uuid

from skillberry_agent_lib.data_model.messages import AssistantMessage, ToolCall, ToolMessage
from skillberry_agent_lib.skillberry_store import skillberry_store
from skillberry_agent_lib.trajectory_manager import trajectory_manager


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


async def pre_hook(skillberry_context: Dict, assistant_message: AssistantMessage) -> None:
    """
    pre-hook. Append assistant message to trajectory.
    
    Note: Catches ValueError to prevent trajectory tracking from breaking tool execution.
    """
    logging.info(f"pre_hook: {skillberry_context}, {assistant_message}")
    try:
        trajectory_manager.add_message(skillberry_context, assistant_message)
    except ValueError as e:
        logging.error(f"pre_hook failed to add message to trajectory: {e}")
        # Don't re-raise - trajectory tracking should not break tool execution


async def post_hook(skillberry_context: Dict, tool_message: ToolMessage) -> None:
    """
    post-hook. Append tool result to trajectory.
    
    Note: Catches ValueError to prevent trajectory tracking from breaking tool execution.
    """
    logging.info(f"post_hook: {skillberry_context}, {tool_message}")
    try:
        trajectory_manager.add_message(skillberry_context, tool_message)
    except ValueError as e:
        logging.error(f"post_hook failed to add message to trajectory: {e}")
        # Don't re-raise - trajectory tracking should not break tool execution


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
        skillberry_context: The context to pass to the interceptor (must not be None)
        
    Returns:
        CustomInterceptor instance configured with the provided context
        
    Raises:
        ValueError: If skillberry_context is None
    """
    # Validate context is not None
    if skillberry_context is None:
        raise ValueError("skillberry_context cannot be None")
    
    return CustomInterceptor(skillberry_context)


def get_mcp_tools(
    port: int,
    server_name: str,
    skillberry_context: Dict
) -> List[Any]:
    """
    Get MCP tools from a server with interceptor configured.
    
    This function encapsulates the common pattern of:
    1. Creating a tool interceptor with the skillberry context
    2. Getting tools from the MCP server via the skillberry API
    3. Logging tool information for debugging
    
    Args:
        port: The port number where the MCP server is running
        server_name: Name identifier for the MCP server
        skillberry_context: The context to pass to the interceptor (must not be None)
        
    Returns:
        List of tools available from the MCP server
        
    Raises:
        ValueError: If skillberry_context is None
    """
    # Validate context is not None
    if skillberry_context is None:
        raise ValueError("skillberry_context cannot be None")
    
    logging.info(f"[MCP DEBUG] Getting MCP tools from port: {port}")
    
    # Create tool interceptor with the skillberry context
    interceptor = create_tool_interceptor(skillberry_context)
    
    # Get tools with the interceptor
    tools = skillberry_store.get_mcp_tools(
        port=port,
        server_name=server_name,
        tool_interceptors=[interceptor]
    )
    
    logging.info(f"[MCP DEBUG] Retrieved {len(tools)} tools from MCP server")
    for idx, tool in enumerate(tools):
        tool_name = getattr(tool, "name", "unknown")
        tool_desc = getattr(tool, "description", "no description")
        logging.info(f"[MCP DEBUG] Tool {idx+1}: name='{tool_name}', description='{tool_desc}'")
    
    return tools


def get_mcp_prompts(
    port: int,
    server_name: str,
    skillberry_context: Dict
) -> List[Any]:
    """
    Get MCP prompts from a server.
    
    This function encapsulates the common pattern of:
    1. Getting prompts from the MCP server via the skillberry API
    2. Logging prompt information for debugging
    
    Args:
        port: The port number where the MCP server is running
        server_name: Name identifier for the MCP server
        skillberry_context: The context (for consistency with get_mcp_tools)
        
    Returns:
        List of prompts available from the MCP server
        
    Raises:
        ValueError: If skillberry_context is None
    """
    # Validate context is not None
    if skillberry_context is None:
        raise ValueError("skillberry_context cannot be None")
    
    logging.debug(f"[MCP DEBUG] Getting MCP prompts from port: {port}")
    
    # Get prompts from the MCP server
    prompts = skillberry_api.get_mcp_prompts(
        port=port,
        server_name=server_name
    )
    
    logging.debug(f"[MCP DEBUG] Retrieved {len(prompts)} prompts from MCP server")
    for idx, prompt in enumerate(prompts):
        prompt_name = getattr(prompt, "name", "unknown")
        prompt_desc = getattr(prompt, "description", "no description")
        logging.debug(f"[MCP DEBUG] Prompt {idx+1}: name='{prompt_name}', description='{prompt_desc}'")
    
    return prompts
