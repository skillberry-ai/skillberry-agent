# Standard library imports
import asyncio
import logging
import os
from typing import Any, Dict

# Third-party imports
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool
from pydantic import create_model, Field

# Local application imports
from config.config_ui import config as _config
from llm.common import current_llm
from skillberry_agent_lib.data_model.virtual_mcp_server import VirtualMcpServer
from skillberry_agent_lib.langgraph_nodes import (
    create_react_tools_workflow,
)
from skillberry_agent_lib.mcp_interceptor import get_mcp_tools
from skillberry_agent_lib.prompt import build_chat_messages
from skillberry_agent_lib.skill_manager import resolve_skill_uuid
from skillberry_agent_lib.trajectory_manager import trajectory_manager
from skillberry_agent_lib.utils import log_tools_info
from skillberry_agent_lib.vmcp_server_manager import (
    get_or_create_vmcp_server,
    remove_vmcp_server,
)

logger = logging.getLogger(__name__)


def convert_openai_tool_to_langchain(tool_dict: Dict[str, Any]) -> Any:
    """
    Convert an OpenAI format tool to a LangChain StructuredTool.

    Args:
        tool_dict: Tool in OpenAI format with structure:
            {
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "description": "tool description",
                    "parameters": {...json schema...}
                }
            }

    Returns:
        LangChain StructuredTool object
    """
    function_def = tool_dict.get("function", {})
    tool_name = function_def.get("name", "unknown_tool")
    tool_description = function_def.get("description", "")
    parameters = function_def.get("parameters", {})

    # Create a Pydantic model from the JSON schema
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    # Build field definitions for the Pydantic model
    field_definitions = {}
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        prop_description = prop_schema.get("description", "")
        is_required = prop_name in required

        # Map JSON schema types to Python types
        type_mapping = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        python_type = type_mapping.get(prop_type, str)

        # Create field with optional/required handling
        if is_required:
            field_definitions[prop_name] = (
                python_type,
                Field(..., description=prop_description),
            )
        else:
            field_definitions[prop_name] = (
                python_type,
                Field(None, description=prop_description),
            )

    # Create the Pydantic model dynamically
    if field_definitions:
        ArgsModel = create_model(f"{tool_name}Args", **field_definitions)
    else:
        # Empty model if no parameters
        ArgsModel = create_model(f"{tool_name}Args")

    # Create a dummy function that will never be called
    # (the actual execution happens through agents's tool system)
    def dummy_func(**kwargs):
        """This function is never called - tools are executed by the agent system"""
        raise NotImplementedError(
            f"Tool {tool_name} should be executed by the agent system"
        )

    # Create the StructuredTool
    langchain_tool = StructuredTool(
        name=tool_name,
        description=tool_description,
        func=dummy_func,
        args_schema=ArgsModel,
    )

    return langchain_tool


def execute_agentic_graph(
    chat_messages: list, skillberry_context: dict, agent_tools: list | None = None
):
    """
    Execute agentic workflow with MCP tools and optional chat request tools.

    Environment Variables:
        SKILL_UUID: Direct skill UUID (optional, highest priority)
        SKILL_NAME: Skill name to resolve (optional, medium priority)
        ENABLE_THINK_LOGS: Include thinking logs in response (default: false)
        USE_AGENT_TOOLS: Enable/disable agent tools from chat request (default: true)
        USE_AGENT_PROMPTS: Enable/disable agent prompts (system messages) from chat request (default: true)
        MCP_PROMPTS_POSITION: Position of MCP prompts relative to system messages:
            - 'prefix': Before system messages
            - 'postfix': After system messages
            Default: postfix

    This function orchestrates the complete agentic workflow:
    1. Resolve skill UUID using multiple strategies
    2. Create or get VMCP server with resolved skill
    3. Get tools from the MCP server with interceptor
    4. Bind tools to LLM
    5. Create and compile the React workflow
    6. Prepare chat messages with MCP prompts injection
    7. Invoke the graph and stream results
    8. Build final response

    Skill Resolution Strategy:
    - SKILL_UUID env var: Direct skill UUID (highest priority)
    - SKILL_NAME env var: Skill name to resolve via API (medium priority)
    - Chat history: Extract search term for skill discovery (lowest priority, fallback)

    The VMCP server is managed per env_id and reused across calls within the same context.
    Use the disconnect() function to clean up the server when the session ends.

    Parameters:
        chat_messages: List of chat messages providing conversation context.
                      May include agent prompts (system messages) that will be filtered based on USE_AGENT_PROMPTS.
        skillberry_context: Context dictionary containing env_id and other metadata (must not be None)
        agent_tools: Optional list of chat request tools in OpenAI format to bind alongside MCP tools

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

    # Read environment variables
    env_skill_uuid = os.environ.get("SKILL_UUID")
    env_skill_name = os.environ.get("SKILL_NAME")
    env_enable_think_logs = os.environ.get("ENABLE_THINK_LOGS", "false")
    env_use_agent_tools = os.environ.get("USE_AGENT_TOOLS", "true")
    env_use_agent_prompts = os.environ.get("USE_AGENT_PROMPTS", "true")
    env_mcp_prompts_position = os.environ.get("MCP_PROMPTS_POSITION", "postfix")

    # Log environment variables
    logging.info("=" * 80)
    logging.info("[ENVIRONMENT VARIABLES]")
    logging.info(
        f"SKILL_UUID={env_skill_uuid}, SKILL_NAME={env_skill_name}, ENABLE_THINK_LOGS={env_enable_think_logs}"
        f" USE_AGENT_TOOLS={env_use_agent_tools}, USE_AGENT_PROMPTS={env_use_agent_prompts}"
        f" MCP_PROMPTS_POSITION={env_mcp_prompts_position}"
    )
    logging.info("=" * 80)

    # Parse boolean environment variables
    enable_think_logs = env_enable_think_logs.lower() in ("true", "1", "yes")
    use_agent_tools = env_use_agent_tools.lower() in ("true", "1", "yes")
    use_agent_prompts = env_use_agent_prompts.lower() in ("true", "1", "yes")

    # Check if agent tools should be included
    if not use_agent_tools and agent_tools:
        logging.info(
            f"Agent tools disabled by USE_AGENT_TOOLS environment variable - ignoring tools from request"
        )
        agent_tools = None

    # Check if agent prompts should be included
    if not use_agent_prompts:
        # Filter out system messages (agent prompts) from chat_messages
        original_count = len(chat_messages)
        chat_messages = [
            msg for msg in chat_messages if not isinstance(msg, SystemMessage)
        ]
        filtered_count = original_count - len(chat_messages)
        if filtered_count > 0:
            logging.info(
                f"Agent prompts disabled by USE_AGENT_PROMPTS environment variable - filtered out {filtered_count} system messages"
            )
    else:
        # Count agent prompts for logging
        agent_prompt_count = sum(
            1 for msg in chat_messages if isinstance(msg, SystemMessage)
        )
        if agent_prompt_count > 0:
            logging.info(
                f"Agent prompts enabled - preserving {agent_prompt_count} system messages in chat_messages"
            )

    # 1. Resolve skill UUID using multiple strategies
    resolved_skill_uuid = resolve_skill_uuid(
        skill_uuid=env_skill_uuid, skill_name=env_skill_name, chat_history=chat_messages
    )

    logging.info(f"Resolved skill UUID: {resolved_skill_uuid}")

    # 2. Create or get VMCP server with resolved skill
    try:
        vmcp_data = get_or_create_vmcp_server(
            skillberry_context, skill_uuid=resolved_skill_uuid
        )
    except ValueError as e:
        error_msg = f"Failed to create VMCP server: {e}"
        logging.error(error_msg)
        return error_msg

    server = VirtualMcpServer(**vmcp_data)
    port = server.port

    # 3. Get tools from the MCP server with interceptor
    tools = get_mcp_tools(
        port=port, server_name=server.name, skillberry_context=skillberry_context
    )

    logging.info(f"MCP TOOLS -=-=-=-=-=-=-=-=-=- {tools} -=-=-=-=-=-=-=-=-=-=-=-=-=-")
    if not tools:
        logging.warning(f"=====> WARNING: No tools retrieved from MCP server!")
    logging.info(f"MCP TOOLS COUNT: {len(tools)}")

    # 3.5. Prepare tools for binding - keep everything in LangChain format
    all_tools = []
    agent_executable_tool_names = (
        []
    )  # Track tools that should be executed by the agent (not by workflow)
    # Start with MCP tools (already in LangChain format)
    if tools:
        logging.info(f"=====> Using {len(tools)} MCP tools")
        all_tools.extend(tools)

    # Convert chat request tools from OpenAI format to LangChain format
    if agent_tools:
        logging.info(
            f"=====> Converting {len(agent_tools)} chat request tools from OpenAI to LangChain format"
        )
        for tool_dict in agent_tools:
            try:
                langchain_tool = convert_openai_tool_to_langchain(tool_dict)
                all_tools.append(langchain_tool)
                agent_executable_tool_names.append(
                    langchain_tool.name
                )  # Mark as agent-executable
                logging.info(
                    f"=====> Converted chat request tool: {langchain_tool.name} (agent-executable)"
                )
            except Exception as e:
                tool_name = tool_dict.get("function", {}).get("name", "unknown")
                logging.error(f"=====> Failed to convert tool {tool_name}: {e}")

    logging.info(f"=====> Total tools for binding: {len(all_tools)}")
    logging.info(
        f"=====> Agent-executable tools (must be executed by the agent): {agent_executable_tool_names}"
    )

    # 4. Bind tools to LLM
    try:
        if not all_tools:
            thinking_log += (
                "I don't have any tools to use. using the LLM model as-is to response. "
            )
            logging.info(f"=====> No tools, not binding")
            logging.info(
                f"=====> WARNING: LLM will NOT be able to call tools - it will only generate text responses"
            )
            llm_with_tools = current_llm.llm
        else:
            thinking_log += "I will now use the tools and the LLM model to respond. "
            logging.info(f"=====> Binding {len(all_tools)} tools to LLM")
            log_tools_info(all_tools, prefix="=====>")
            llm_with_tools = current_llm.llm.bind_tools(
                tools=all_tools, tool_choice="auto"
            )
            logging.info(f"=====> Tools successfully bound to LLM")

    except Exception as e:
        logging.error(f"Error while binding tools: {e}")
        return "Sorry, failed to answer using skillberry (tools binding)"

    # 5. Create and compile the React workflow with all tools (all in LangChain format)
    workflow = create_react_tools_workflow(
        tools=all_tools,
        enable_tool_logging=False,
        normalize_anthropic_to_openai=True,
        agent_executable_tool_names=agent_executable_tool_names,  # Pass agent-executable tools
    )

    graph = workflow.compile()

    # 6. Prepare chat messages with MCP prompts injection
    logging.info(f"=====> Preparing chat messages with MCP prompts injection")
    mcp_prompts_position = env_mcp_prompts_position
    llm_messages = build_chat_messages(
        chat_history=chat_messages,
        mcp_port=port,
        mcp_server_name=server.name,
        skillberry_context=skillberry_context,
        mcp_prompts_position=mcp_prompts_position,
    )

    # 7. Invoke the graph and stream results
    try:
        logging.info(f"=====> Invoking the tools react agent")
        logging.info(f"Chat history has {len(chat_messages)} messages")
        logging.info(f"LLM messages prepared: {len(llm_messages)} messages")
        recursion_limit = _config.get("tools_react_agent__recursion_limit")

        # Log all messages being passed to the graph
        logging.info(f"Number of messages being passed to graph: {len(llm_messages)}")
        for i, msg in enumerate(llm_messages):
            logging.info(
                f"Message {i+1}: type={type(msg).__name__}, role={getattr(msg, 'type', 'N/A')}, content_preview={str(msg.content)[:100]}..."
            )

        # Stream results and capture final message
        async def process_stream():
            final_message = None
            async for s in graph.astream(
                {"messages": llm_messages, "llm": llm_with_tools},
                {"recursion_limit": recursion_limit, "max_execution_time": 120},
                stream_mode="values",
            ):
                message = s["messages"][-1]
                final_message = message
            return final_message

        final_message = asyncio.run(process_stream())
    except Exception as e:
        logging.error(f"Error while streaming to the react agent: {e}")
        return "I apologize, but I'm experiencing a technical difficulty at the moment. Could you please repeat your request?"

    logger.info(
        f"=====> The agentic flow has finished executing the tools with parameters"
    )

    # 8. Build final response
    try:
        # Check if final_message has tool_calls that need to be executed by the agent
        if hasattr(final_message, "tool_calls") and final_message.tool_calls:
            logging.info(
                f"final AI response has {len(final_message.tool_calls)} tool calls - returning AIMessage for the agent to execute"
            )
            logging.info(
                f"Tool calls: {[tc.get('name') for tc in final_message.tool_calls]}"
            )
            # Return the AIMessage object so tool_calls are preserved
            return final_message
        else:
            # No tool calls - return content as string (legacy behavior)
            ai_response = final_message.content
            logging.info(
                f"final AI response: {final_message.content} given from: {llm_messages}"
            )
            thinking_log += f"I am done. Returning a response to the user."

            # Conditionally include think logs based on environment variable
            if enable_think_logs:
                output_content = f"<think>{thinking_log}</think>\n{ai_response}"
            else:
                output_content = ai_response

            logger.info(f"output_content: {output_content}")
            logging.info(f"=======>>> execute_agentic_graph ended <<<=======")
            return output_content
    except Exception as e:
        logging.error(f"Error building final response: {e}")
        output_content = "Sorry, failed to answer using skillberry (response building)"
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
            logger.info(
                f"Successfully removed VMCP server for context: {skillberry_context}"
            )
        else:
            logger.warning(
                f"VMCP server not found in local registry for context: {skillberry_context} (may have been removed from Tools Service)"
            )
    except Exception as e:
        logger.warning(f"Failed to remove VMCP server: {e}")

    # Clean up trajectory
    try:
        trajectory_manager.remove_trajectory(skillberry_context)
        logger.info(f"Cleaned up trajectory for context: {skillberry_context}")
    except Exception as e:
        logger.warning(f"Failed to clean up trajectory: {e}")
