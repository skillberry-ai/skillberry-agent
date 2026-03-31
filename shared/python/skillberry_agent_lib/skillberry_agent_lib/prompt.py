"""
Shared prompt utilities for Skillberry agents.

This module provides common prompt templates and formatting functions
for MCP prompts injection and chat prompt templates that are shared
across different agent implementations.
"""

import logging
import os
from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate


def _get_enable_mcp_prompts_from_env() -> bool:
    """Get enable_mcp_prompts setting from environment variable.
    
    Checks ENABLE_MCP_PROMPTS environment variable. Only returns True
    if explicitly set to 'true' (case-insensitive). Returns False otherwise.
    
    Returns:
        bool: True if ENABLE_MCP_PROMPTS is explicitly set to 'true', False otherwise
    """
    env_value = os.getenv('ENABLE_MCP_PROMPTS', '').lower()
    return env_value == 'true'


def get_mcp_prompts_and_format(
    port: int,
    server_name: str,
    skillberry_context: dict
) -> str:
    """Get MCP prompts from server and format them for system prompt.
    
    This is a convenience function that combines getting prompts from
    the MCP server and formatting them for inclusion in system messages.
    
    Args:
        port: Port number of the MCP server
        server_name: Name of the MCP server
        skillberry_context: Context dictionary with env_id and other metadata
        
    Returns:
        str: Formatted prompts text ready for system prompt injection.
             May return empty string if no prompts available.
    """
    from skillberry_agent_lib.mcp_interceptor import get_mcp_prompts
    
    def concatenate_prompts(prompts: list) -> str:
        """Concatenate MCP prompts by joining their descriptions."""
        if not prompts:
            return ""
        
        prompt_sections = []
        for prompt in prompts:
            description = getattr(prompt, 'description', '')
            
            # Append the prompt description as-is without any markers
            if description:
                prompt_sections.append(description)
        
        if prompt_sections:
            return "\n".join(prompt_sections)
        return ""
    
    mcp_prompts = get_mcp_prompts(
        port=port,
        server_name=server_name,
        skillberry_context=skillberry_context
    )
    return concatenate_prompts(mcp_prompts)


# Standard chat prompt template for tool execution
# This template is used across different agent implementations
execute_tools_with_parameters_chat_prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", "You are an expert assistant"),
        (
            "system",
            "If a tool returns an exception, and error, no result or any other failure, "
            "return to the user immediately! and the user to provide additional information or clarification. "
            "DO NOT try to call any additional tools or functions until the user provides additional information or clarification.",
        ),
        # TODO (weit): remove transfer_to_human_agents
        (
            "system",
            "Try to use tools and ask the user for clarification and additional information as much as possible. "
            " If, and only if this completely fails, use the transfer_to_human_agents tool.",
        ),
        "{chat_history}",
    ]
)


def build_chat_messages(
    chat_history: list,
    mcp_port: int,
    mcp_server_name: str,
    skillberry_context: dict,
    base_template: Optional[ChatPromptTemplate] = None,
    enable_mcp_prompts: Optional[bool] = None
):
    """Build chat messages with optional MCP prompts injection.
    
    This function handles the complete flow of:
    1. Getting MCP prompts from the server (if enabled)
    2. Injecting them into the system messages before chat_history
    3. Invoking the template with chat_history to get final messages
    
    Args:
        chat_history: List of chat messages providing conversation context
        mcp_port: Port number of the MCP server
        mcp_server_name: Name of the MCP server
        skillberry_context: Context dictionary
        base_template: Base ChatPromptTemplate to use. If None, uses execute_tools_with_parameters_chat_prompt_template
        enable_mcp_prompts: Whether to fetch and inject MCP prompts.
                          If None (default), reads from ENABLE_MCP_PROMPTS env var.
                          If explicitly set to True/False, overrides env var.
        
    Returns:
        Invoked chat messages ready for LLM consumption
    """
    # Use provided template or default
    if base_template is None:
        base_template = execute_tools_with_parameters_chat_prompt_template
    
    # Determine if MCP prompts should be enabled
    # Priority: explicit parameter > environment variable > default (False)
    if enable_mcp_prompts is None:
        enable_mcp_prompts = _get_enable_mcp_prompts_from_env()
    
    # Early return if MCP prompts are disabled
    if not enable_mcp_prompts:
        logging.debug("MCP prompts disabled, using base template only")
        return base_template.invoke(chat_history)
    
    # Get and format MCP prompts from server
    mcp_prompts_text = get_mcp_prompts_and_format(
        port=mcp_port,
        server_name=mcp_server_name,
        skillberry_context=skillberry_context
    )
    
    logging.info(f"Injecting MCP prompts into system messages")
    logging.debug(f"MCP prompts content:\n{mcp_prompts_text}")
    
    # Get the base messages from the existing template
    base_messages = list(base_template.messages)
    
    # Find the position of chat_history placeholder and insert before it
    chat_history_idx = None
    for idx, msg in enumerate(base_messages):
        if isinstance(msg, tuple) and msg[0] == "{chat_history}":
            chat_history_idx = idx
            break
        elif hasattr(msg, 'prompt') and '{chat_history}' in str(msg.prompt):
            chat_history_idx = idx
            break
    
    # Insert MCP prompts before chat_history, or at the end if not found
    insert_position = chat_history_idx if chat_history_idx is not None else len(base_messages) - 1
    base_messages.insert(insert_position, ("system", mcp_prompts_text))
    
    # Create new template with MCP prompts
    chat_prompt_template = ChatPromptTemplate.from_messages(base_messages)
    return chat_prompt_template.invoke(chat_history)


__all__ = [
    "build_chat_messages",
]

# Made with Bob
