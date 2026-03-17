# Standard library imports
import asyncio
import json
import logging

# Third-party imports
from langchain_core.prompts import ChatPromptTemplate

# Local application imports
from agents.state import State
from config.config_ui import config as _config
from llm.common import current_llm
from skillberry_agent_lib.data_model.virtual_mcp_server import VirtualMcpServer
from skillberry_agent_lib.langgraph_nodes import (
    create_react_tools_workflow,
)
from skillberry_agent_lib.mcp_interceptor import get_mcp_tools
from skillberry_agent_lib.skillberry_api import skillberry_api
from skillberry_agent_lib.trajectory_manager import trajectory_manager
from skillberry_agent_lib.vmcp_server_manager import create_vmcp_server, resolve_skill_uuid



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


def mcp_tools(chat_history: list, skillberry_context: dict,
              skill_name=None, skill_uuid=None, enable_skill_search=False):
    """
    Defines and compiles a LangGraph workflow for a react-style agent, connecting
    LLM and tool nodes with conditional logic to control execution flow.

    Note: This method selects the proper MCP server (using context) for LLM completion.

    Parameters:
        chat_history: List of chat messages
        skillberry_context: Context dictionary containing env_id, task_id, etc.
        skill_name: Optional skill name to resolve to UUID
        skill_uuid: Optional skill UUID (if not provided, will be resolved from skill_name)
        enable_skill_search: If True, enables runtime skill search (not yet implemented)
    
    Returns:
        str: The final AI response content
    
    The MCP server is removed upon "disconnect" control command (once the scenario completes).

    """
    logging.info(f"=======>>> mcp_tools started <<<=======")
    thinking_log = ""

    # Resolve skill UUID using shared library helper method
    try:
        # Handle enable_skill_search mode
        if enable_skill_search:
            # Runtime mode: Not currently implemented in mcp_tools
            logging.error("[RUNTIME MODE] Skill search enabled - VMCP creation on-demand is not currently implemented in mcp_tools()")
            raise NotImplementedError("Runtime skill search mode (enable_skill_search=True) is not currently implemented in mcp_tools()")
        
        resolved_skill_uuid = resolve_skill_uuid(skill_name, skill_uuid)
    except NotImplementedError as e:
        error_msg = str(e)
        logging.error(f"NotImplementedError in mcp_tools: {error_msg}")
        return error_msg

    # Get or create singleton server with resolved skill_uuid
    logging.info(f"Getting/creating singleton MCP server with skill_uuid: {resolved_skill_uuid}")

    # Create the vmcpserver and provide it with the context.
    # This context is then forwarded to the tools execution environment (the handler() function).
    # The environment ID (env_id) is propagated throughout the tools' runtime to ensure that all
    # operations are performed on the correct environment instance.
    vmcp_data = create_vmcp_server(skillberry_context, skill_uuid=resolved_skill_uuid)
    
    # Create VirtualMcpServer instance from the returned data
    server = VirtualMcpServer(**vmcp_data)

    port = server.port
    
    # Get tools from the MCP server with interceptor
    tools = get_mcp_tools(
        port=port,
        server_name=server.name,
        skillberry_context=skillberry_context
    )

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
        return "Sorry, failed to answer using skillberry (tools binding)"

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

    # 5. Build final response
    try:
        ai_response = final_message.content
        logging.info(f"final AI response: {final_message.content} given from: {llm_messages}")
        thinking_log += f"I am done. Returning a response to the user."
        
        output_content = f"<think>{thinking_log}</think>\n{ai_response}"
    except Exception as e:
        logging.error(f"Error building final response: {e}")
        output_content = "Sorry, failed to answer using skillberry (response building)"

    logger.info(f"output_content: {output_content}")
    logging.info(f"=======>>> mcp_tools ended <<<=======")
    
    return output_content


def trajectory(skillberry_context: dict) -> list:
    """
    Get the trajectory of tool calls and results tracked by the interceptor.
    
    Parameters:
        skillberry_context: The skillberry context dictionary containing env_id, task_id, etc.
    
    Returns:
        List of messages (AssistantMessage and ToolMessage) representing the trajectory
    """
    trajectory = trajectory_manager.get_trajectory(skillberry_context)
    logger.info(f"Retrieved trajectory with {len(trajectory)} messages")
    
    # Convert to dict format for compatibility
    trajectory_dicts = []
    for msg in trajectory:
        msg_dict = msg.model_dump()
        trajectory_dicts.append(msg_dict)
    
    return trajectory_dicts


def disconnect(skillberry_context: dict):
    """
    Disconnect from the attached virtual mcp server and clean up trajectory.
    
    Parameters:
        skillberry_context: The skillberry context dictionary containing env_id, task_id, etc.
    """   
    # Use hardcoded server name to match current API implementation
    server_name = "my-vmcp-server"
    logger.info(f"Disconnecting from vmcp_server: '{server_name}'")

    try:
        skillberry_api.remove_vmcp_server(name=server_name)
    except Exception as e:
        logger.warning(f"Failed to remove VMCP server '{server_name}': {e}")
    
    # Clean up trajectory
    try:
        trajectory_manager.remove_trajectory(skillberry_context)
        logger.info(f"Cleaned up trajectory for env_id: {skillberry_context.get('env_id')}")
    except Exception as e:
        logger.warning(f"Failed to clean up trajectory: {e}")
