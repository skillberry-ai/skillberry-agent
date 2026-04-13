"""
Shared prompt utilities for Skillberry agents.

This module provides common utilities for MCP prompts injection
that are shared across different agent implementations.
"""

import logging
from typing import Optional


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


def build_chat_messages(
    chat_history: list,
    mcp_port: int,
    mcp_server_name: str,
    skillberry_context: dict,
    mcp_prompts_position: str = 'postfix'
) -> list:
    """Build chat messages with MCP prompts injection.
    
    This function injects MCP prompts at the configured position relative to
    system messages already present in the chat history.
    
    IMPORTANT: This function expects chat_history to contain LangChain message types
    (HumanMessage, AIMessage, SystemMessage, ToolMessage from langchain_core.messages).
    
    Args:
        chat_history: List of LangChain BaseMessage objects (will be modified in-place)
        mcp_port: Port number of the MCP server
        mcp_server_name: Name of the MCP server
        skillberry_context: Context dictionary
        mcp_prompts_position: Where to insert MCP prompts relative to system messages:
            - 'prefix': Before all system messages (or at beginning if no system messages exist)
            - 'postfix': After all system messages (or at beginning if no system messages exist)
            Default: 'postfix'
        
    Returns:
        list: Modified chat_history with MCP prompts inserted (LangChain BaseMessage objects)
    """
    from langchain_core.messages import SystemMessage
    
    # Get and format MCP prompts from server
    mcp_prompts_text = get_mcp_prompts_and_format(
        port=mcp_port,
        server_name=mcp_server_name,
        skillberry_context=skillberry_context
    )
    
    if not mcp_prompts_text:
        logging.warning("No MCP prompts retrieved from server")
        return chat_history
    
    logging.info(f"Injecting MCP prompts into chat messages (position: {mcp_prompts_position})")
    logging.debug(f"MCP prompts content:\n{mcp_prompts_text}")
    
    # Create system message with MCP prompts
    mcp_system_message = SystemMessage(content=mcp_prompts_text)
    
    # Find system messages in chat_history
    first_system_idx = None
    last_system_idx = None
    for idx, msg in enumerate(chat_history):
        if isinstance(msg, SystemMessage):
            if first_system_idx is None:
                first_system_idx = idx
            last_system_idx = idx
    
    # Determine insertion position based on mcp_prompts_position
    if mcp_prompts_position == 'prefix':
        # Insert before first system message, or at beginning if no system messages
        if first_system_idx is not None:
            logging.info(f"Inserting MCP prompts before first system message at index {first_system_idx}")
            chat_history.insert(first_system_idx, mcp_system_message)
        else:
            logging.info("No system messages found, inserting MCP prompts at beginning")
            chat_history.insert(0, mcp_system_message)
            
    else:  # postfix
        # Insert after last system message, or at beginning if no system messages
        if last_system_idx is not None:
            logging.info(f"Inserting MCP prompts after last system message at index {last_system_idx}")
            chat_history.insert(last_system_idx + 1, mcp_system_message)
        else:
            logging.info("No system messages found, inserting MCP prompts at beginning")
            chat_history.insert(0, mcp_system_message)
    
    return chat_history


__all__ = [
    "build_chat_messages",
]

# Made with Bob
