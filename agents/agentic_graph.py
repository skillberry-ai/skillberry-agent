# Standard library imports
import asyncio
import logging
import os

# Third-party imports
# Local application imports
from config.config_ui import config as _config
from llm.common import current_llm
from skillberry_agent_lib.data_model.virtual_mcp_server import VirtualMcpServer
from skillberry_agent_lib.langgraph_nodes import (
    create_react_tools_workflow,
)
from skillberry_agent_lib.mcp_interceptor import get_mcp_tools
from skillberry_agent_lib.prompt import (
    build_chat_messages,
)
from skillberry_agent_lib.skill_manager import resolve_skill_uuid
from skillberry_agent_lib.trajectory_manager import trajectory_manager
from skillberry_agent_lib.vmcp_server_manager import get_or_create_vmcp_server, remove_vmcp_server


logger = logging.getLogger(__name__)


def execute_agentic_graph(chat_history: list, skillberry_context: dict):
    """
    Execute agentic workflow with MCP tools.
    
    Environment Variables:
        SKILL_UUID: Direct skill UUID (optional, highest priority)
        SKILL_NAME: Skill name to resolve (optional, medium priority)
        ENABLE_THINK_LOGS: Include thinking logs in response (default: false)
    
    This function orchestrates the complete agentic workflow:
    1. Read skill configuration from environment variables
    2. Resolve skill UUID using multiple strategies
    3. Create or get VMCP server with resolved skill
    4. Get tools from the MCP server with interceptor
    5. Bind tools to LLM
    6. Create and compile the React workflow
    7. Prepare chat messages with MCP prompts injection
    8. Invoke the graph and stream results
    9. Build final response
    
    Skill Resolution Strategy:
    - SKILL_UUID env var: Direct skill UUID (highest priority)
    - SKILL_NAME env var: Skill name to resolve via API (medium priority)
    - Chat history: Extract search term for skill discovery (lowest priority, fallback)
    
    The VMCP server is managed per env_id and reused across calls within the same context.
    Use the disconnect() function to clean up the server when the session ends.
    
    Parameters:
        chat_history: List of chat messages providing conversation context
        skillberry_context: Context dictionary containing env_id and other metadata (must not be None)
    
    Returns:
        str: The final AI response content
        
    Raises:
        ValueError: If skillberry_context is None or VMCP server creation fails
    """
    # Validate context is not None
    if skillberry_context is None:
        raise ValueError("skillberry_context cannot be None")
    
    logging.info(f"=======>>> execute_agentic_graph started <<<=======")
    thinking_log = ""
    
    # Check if think logs should be included in response
    enable_think_logs = os.environ.get('ENABLE_THINK_LOGS', 'false').lower() in ('true', '1', 'yes')
    logging.info(f"Think logs enabled: {enable_think_logs}")

    # 1. Read skill configuration from environment variables
    env_skill_uuid = os.environ.get('SKILL_UUID')
    env_skill_name = os.environ.get('SKILL_NAME')
    
    logging.info(f"Environment: SKILL_UUID={env_skill_uuid}, SKILL_NAME={env_skill_name}")
    
    # 2. Resolve skill UUID using multiple strategies
    resolved_skill_uuid = resolve_skill_uuid(
        skill_uuid=env_skill_uuid,
        skill_name=env_skill_name,
        chat_history=chat_history
    )
    
    logging.info(f"Resolved skill UUID: {resolved_skill_uuid}")
    
    # 3. Create or get VMCP server with resolved skill
    try:
        vmcp_data = get_or_create_vmcp_server(
            skillberry_context,
            skill_uuid=resolved_skill_uuid
        )
    except ValueError as e:
        error_msg = f"Failed to create VMCP server: {e}"
        logging.error(error_msg)
        return error_msg
    
    server = VirtualMcpServer(**vmcp_data)
    port = server.port
    
    # 4. Get tools from the MCP server with interceptor
    tools = get_mcp_tools(
        port=port,
        server_name=server.name,
        skillberry_context=skillberry_context
    )

    logging.info(f"MCP TOOLS -=-=-=-=-=-=-=-=-=- {tools} -=-=-=-=-=-=-=-=-=-=-=-=-=-")
    
    # 5. Bind tools to LLM
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
        return "Sorry, failed to answer using skillberry (tools binding)"

    # 6. Create and compile the React workflow
    workflow = create_react_tools_workflow(
        tools=tools,
        enable_tool_logging=False,
        normalize_anthropic_to_openai=True,
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

    # 7. Prepare chat messages with MCP prompts injection
    original_chat_messages = build_chat_messages(
        chat_history=chat_history,
        mcp_port=port,
        mcp_server_name=server.name,
        skillberry_context=skillberry_context
    )
    
    llm_messages = original_chat_messages.to_messages()

    # 8. Invoke the graph and stream results
    try:
        logging.info(f"=====> Invoking the tools react agent")
        logging.info(f"Chat history has {len(chat_history)} messages")
        logging.info(f"LLM messages prepared: {len(llm_messages)} messages")
        recursion_limit = _config.get("tools_react_agent__recursion_limit")

        final_message = asyncio.run(trace_stream(graph.astream(
            {
                "messages": llm_messages,
                "llm": llm_with_tools
            },
            {
                "recursion_limit": recursion_limit,
                "max_execution_time": 120
            },
            stream_mode="values",
        )))
    except Exception as e:
        logging.error(f"Error while streaming to the react agent: {e}")
        return "Sorry, failed to answer using skillberry (invoke react agent)"

    logger.info(
        f"=====> The agentic flow has finished executing the tools with parameters"
    )

    # 9. Build final response
    try:
        ai_response = final_message.content
        logging.info(f"final AI response: {final_message.content} given from: {llm_messages}")
        thinking_log += f"I am done. Returning a response to the user."
        
        # Conditionally include think logs based on environment variable
        if enable_think_logs:
            output_content = f"<think>{thinking_log}</think>\n{ai_response}"
        else:
            output_content = ai_response
    except Exception as e:
        logging.error(f"Error building final response: {e}")
        output_content = "Sorry, failed to answer using skillberry (response building)"

    logger.info(f"output_content: {output_content}")
    logging.info(f"=======>>> execute_agentic_graph ended <<<=======")
    
    return output_content


def trajectory(skillberry_context: dict) -> list:
    """
    Get the trajectory of tool calls and results tracked by the interceptor.
    Parameters:
        skillberry_context: Context dictionary containing the context
        
    Returns:
        List of messages (AssistantMessage and ToolMessage) representing the trajectory
        Empty list if trajectory retrieval fails
    """
    try:
        trajectory = trajectory_manager.get_trajectory(skillberry_context)
        logger.info(f"Retrieved trajectory with {len(trajectory)} messages")
        
        # Convert to dict format for compatibility
        trajectory_dicts = []
        for msg in trajectory:
            msg_dict = msg.model_dump()
            trajectory_dicts.append(msg_dict)
        
        return trajectory_dicts
    except ValueError as e:
        logger.error(f"Failed to get trajectory: {e}")
        return []  # Return empty list on error


def disconnect(skillberry_context: dict):
    """
    Disconnect from the attached virtual mcp server and clean up trajectory.
    
    Parameters:
        skillberry_context: Context dictionary containing the context
    """
    logger.info(f"Disconnecting from vmcp_server for context: {skillberry_context}")

    # Remove VMCP server (handles both local registry and Tools Service)
    try:
        removed = remove_vmcp_server(skillberry_context)
        if removed:
            logger.info(f"Successfully removed VMCP server for context: {skillberry_context}")
        else:
            logger.warning(f"VMCP server not found in local registry for context: {skillberry_context} (may have been removed from Tools Service)")
    except Exception as e:
        logger.warning(f"Failed to remove VMCP server: {e}")
    
    # Clean up trajectory
    try:
        trajectory_manager.remove_trajectory(skillberry_context)
        logger.info(f"Cleaned up trajectory for context: {skillberry_context}")
    except Exception as e:
        logger.warning(f"Failed to clean up trajectory: {e}")
