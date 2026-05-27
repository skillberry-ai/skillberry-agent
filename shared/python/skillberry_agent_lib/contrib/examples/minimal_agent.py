"""
Minimal Agent Example - Complete End-to-End Implementation

This script demonstrates the 8 steps to build a production-ready agent using
the Skillberry Agent Library. It shows a working example that you can run
and modify for your own use cases.

Prerequisites:
1. Skillberry Tools Store running on http://localhost:8000
   GitHub: https://github.com/skillberry-ai/skillberry-store
2. A skill imported into the store (e.g., 'calculator')
3. LLM provider credentials set in environment variables (via llm-switchboard)
   GitHub: https://github.com/skillberry-ai/llm-switchboard

Usage:
    python minimal_agent.py
"""

import asyncio
import logging
import os
from typing import Any, List, Optional

# Skillberry Agent Library imports
from skillberry_agent_lib import (
    resolve_skill_uuid,
    get_or_create_vmcp_server,
    get_mcp_tools,
    build_chat_messages,
    TrajectoryManager,
    remove_vmcp_server,
)
from skillberry_agent_lib.data_model.virtual_mcp_server import VirtualMcpServer
from skillberry_agent_lib.langgraph_nodes import create_react_tools_workflow

# LLM imports (using llm-switchboard)
from llm_switchboard.llm import get_llm
import inspect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleLLMAdapter:
    """
    Minimal LangChain-compatible adapter for llm-switchboard.
    
    This adapter provides the basic interface needed by LangGraph:
    - bind_tools() for tool binding
    - invoke() for message generation
    
    Note: This simple adapter does not support tool calling. The trajectory
    will be empty because trajectory is populated by the MCP interceptor
    only when tools are actually executed.
    
    For production use with full tool support, see llm/common.py's
    LLMClientLangChainAdapter which includes complete message conversion,
    tool calling, error handling, and more.
    """
    
    def __init__(self, client: Any, model_name: str, model_in_generate: bool):
        self.client = client
        self.model_name = model_name
        self.model_in_generate = model_in_generate
        self._bound_tools = []
    
    def bind_tools(self, tools: List[Any], **kwargs) -> "SimpleLLMAdapter":
        """Bind tools to the LLM for tool calling"""
        self._bound_tools = tools
        return self
    
    def invoke(self, messages: List[Any], config: Optional[Any] = None, **kwargs) -> Any:
        """Invoke the LLM with messages
        
        Args:
            messages: List of messages to send to the LLM
            config: Optional LangChain config (callbacks, tags, metadata, etc.)
            **kwargs: Additional keyword arguments
        """
        # In a real implementation, you'd convert messages to the right format
        # and handle tool calls properly. See llm/common.py for details.
        if self.model_in_generate:
            kwargs["model"] = self.model_name
        
        response = self.client.generate(prompt=messages, **kwargs)
        return response


async def run_minimal_agent():
    """
    Complete minimal agent implementation following the 8-step pattern.
    """
    
    # ========================================================================
    # STEP 1: Resolve skill and create VMCP server
    # ========================================================================
    logger.info("Step 1: Resolving skill and creating VMCP server...")
    
    # Define agent context (required for tracking)
    agent_context = {
        "env_id": "minimal-agent-example",
        "task_id": "demo-task-001",
    }
    
    # Set skill configuration via environment variables
    # Priority: SKILL_UUID > SKILL_NAME > chat history search
    os.environ['SKILL_NAME'] = 'calculate'  # Change to your skill name
    
    # Resolve skill UUID
    chat_history = []  # Empty for this example
    resolved_uuid = resolve_skill_uuid(
        skill_uuid=os.environ.get('SKILL_UUID'),
        skill_name=os.environ.get('SKILL_NAME'),
        chat_history=chat_history
    )
    
    if not resolved_uuid:
        logger.error("Failed to resolve skill UUID. Make sure the skill exists in the store.")
        return
    
    logger.info(f"Resolved skill UUID: {resolved_uuid}")
    
    # Create VMCP server
    try:
        vmcp_data = get_or_create_vmcp_server(
            agent_context,
            skill_uuid=resolved_uuid,
        )
        server = VirtualMcpServer(**vmcp_data)
        port = server.port
        logger.info(f"Created VMCP server on port {port}")
    except ValueError as e:
        logger.error(f"Failed to create VMCP server: {e}")
        return
    
    # ========================================================================
    # STEP 2: Get tools from MCP server
    # ========================================================================
    logger.info("Step 2: Getting tools from MCP server...")
    
    tools = get_mcp_tools(
        port=port,
        server_name=server.name,
        skillberry_context=agent_context,
    )
    
    logger.info(f"Loaded {len(tools)} MCP tools")
    
    # ========================================================================
    # STEP 3: Initialize and bind LLM with tools
    # ========================================================================
    logger.info("Step 3: Initializing LLM and binding tools...")
    
    # Get LLM provider from llm-switchboard
    provider_name = "litellm.rits"  # Change to your provider
    model_name = "openai/gpt-oss-120b"  # Change to your model
    
    try:
        ProviderClass = get_llm(provider_name)
        
        # Check if provider accepts model_name in constructor
        signature = inspect.signature(ProviderClass)
        if "model_name" in signature.parameters:
            llm_client = ProviderClass(model_name=model_name)
            model_in_generate = False
        else:
            llm_client = ProviderClass()
            model_in_generate = True
        
        # Wrap in adapter
        llm = SimpleLLMAdapter(llm_client, model_name, model_in_generate)
        
        # Bind tools
        if tools:
            llm_with_tools = llm.bind_tools(tools=tools, tool_choice="auto")
            logger.info(f"Bound {len(tools)} tools to LLM")
        else:
            llm_with_tools = llm
            logger.warning("No tools available")
            
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        return
    
    # ========================================================================
    # STEP 4: Create and compile React workflow
    # ========================================================================
    logger.info("Step 4: Creating React workflow...")
    
    workflow = create_react_tools_workflow(
        tools=tools,
        enable_tool_logging=True,
        tool_logger=logger,
        normalize_anthropic_to_openai=False,  # Set True if using Anthropic
    )
    
    graph = workflow.compile()
    logger.info("Workflow compiled successfully")
    
    # ========================================================================
    # STEP 5: Build chat messages with MCP prompts injection
    # ========================================================================
    logger.info("Step 5: Building chat messages with MCP prompts...")
    
    # Prepare chat history
    user_query = "Calculate the result of this expression: 25 * 4 + 10"
    chat_history = [
        {"role": "user", "content": user_query}
    ]
    
    # Build messages with MCP prompts injection
    llm_messages = build_chat_messages(
        chat_history=chat_history,
        mcp_port=port,
        mcp_server_name=server.name,
        skillberry_context=agent_context,
        mcp_prompts_position='postfix'  # MCP prompts after system messages
    )
    
    logger.info(f"Prepared {len(llm_messages)} messages for agent")
    
    # ========================================================================
    # STEP 6: Invoke graph with configuration
    # ========================================================================
    logger.info("Step 6: Invoking agent...")
    logger.info(f"User query: {user_query}")
    
    try:
        final_message = None
        
        async for state in graph.astream(
            {
                "messages": llm_messages,
                "llm": llm_with_tools,
            },
            {
                "recursion_limit": 20,
                "max_execution_time": 120
            },
            stream_mode="values",
        ):
            message = state["messages"][-1]
            logger.debug(f"Step: {message.type}")
            final_message = message
        
        logger.info("Agent execution completed")
        
    except Exception as e:
        logger.error(f"Error during agent execution: {e}")
        return
    
    # ========================================================================
    # STEP 7: Handle final response
    # ========================================================================
    logger.info("Step 7: Processing final response...")
    
    if hasattr(final_message, 'tool_calls') and final_message.tool_calls:
        logger.info(f"Agent returned {len(final_message.tool_calls)} tool calls")
        for tool_call in final_message.tool_calls:
            logger.info(f"  Tool: {tool_call.get('name')}")
    else:
        response = final_message.content
        logger.info(f"Agent response: {response}")
        print(f"\n{'='*60}")
        print(f"RESULT: {response}")
        print(f"{'='*60}\n")
    
    # ========================================================================
    # STEP 8: Cleanup with error handling
    # ========================================================================
    logger.info("Step 8: Cleaning up resources...")
    
    # Initialize trajectory manager
    trajectory_manager = TrajectoryManager()
    
    # Note: Trajectory will be empty (see SimpleLLMAdapter note at top of file)
    
    # Cleanup VMCP server
    try:
        removed = remove_vmcp_server(agent_context)
        if removed:
            logger.info("VMCP server removed successfully")
        else:
            logger.warning("VMCP server not found (may have been already removed)")
    except Exception as e:
        logger.warning(f"Failed to remove VMCP server: {e}")
    
    # Cleanup trajectory
    try:
        trajectory_manager.remove_trajectory(agent_context)
        logger.info("Trajectory cleaned up")
    except Exception as e:
        logger.warning(f"Failed to clean up trajectory: {e}")
    
    logger.info("Agent execution complete!")


if __name__ == "__main__":
    # Run the minimal agent
    asyncio.run(run_minimal_agent())

# Made with Bob
