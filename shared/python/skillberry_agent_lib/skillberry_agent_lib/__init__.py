# coding: utf-8

"""
    Skillberry Agent Library

    Core utilities for Skillberry agents including message handling,
    trajectory management, and API client functionality.
"""

__version__ = "1.0.0"

# Import main classes and functions
from skillberry_agent_lib.data_model.messages import (
    SystemMessage,
    UserMessage,
    AssistantMessage,
    ToolMessage,
    SystemRole,
    UserRole,
    AssistantRole,
    ToolRole,
    ToolRequestor,
    format_time,
    get_now,
)

from skillberry_agent_lib.trajectory_manager import TrajectoryManager

from skillberry_agent_lib.skillberry_store import SkillberryStore

from skillberry_agent_lib.skill_manager import resolve_skill_uuid

from skillberry_agent_lib.utils import (
    SKILLBERRY_CONTEXT,
    flatten_keys,
    extract_base_url,
)

from skillberry_agent_lib.vmcp_server_manager import (
    get_or_create_vmcp_server,
    remove_vmcp_server,
    clear_vmcp_servers,
)

from skillberry_agent_lib.mcp_interceptor import (
    create_tool_interceptor,
    get_mcp_tools,
    get_mcp_prompts,
)

from skillberry_agent_lib.prompt import (
    build_chat_messages,
)

__all__ = [
    # Version
    "__version__",
    
    # Messages
    "SystemMessage",
    "UserMessage",
    "AssistantMessage",
    "ToolMessage",
    "SystemRole",
    "UserRole",
    "AssistantRole",
    "ToolRole",
    "ToolRequestor",
    "format_time",
    "get_now",
    
    # Trajectory Manager
    "TrajectoryManager",
    
    # API Client
    "SkillberryAPI",
    
    # Skill Manager
    "resolve_skill_uuid",
    
    # Utils
    "SKILLBERRY_CONTEXT",
    "flatten_keys",
    "extract_base_url",
    
    # VMCP Server Manager
    "get_or_create_vmcp_server",
    "remove_vmcp_server",
    "clear_vmcp_servers",
    
    # MCP Interceptor
    "create_tool_interceptor",
    "get_mcp_tools",
    "get_mcp_prompts",
    
    # Prompt utilities
    "build_chat_messages",
]

# Made with Bob
