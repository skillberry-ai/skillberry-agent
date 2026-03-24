"""
Test utilities for skillberry_agent_lib tests.
Following the pattern from skillberry-store (no conftest.py for unit tests).
"""

from typing import Dict
from skillberry_agent_lib.data_model.messages import (
    AssistantMessage,
    ToolMessage,
    ToolCall,
)


def create_sample_context(env_id: str = "test-env-001") -> Dict:
    """Creates a standard test context."""
    return {"env_id": env_id}


def create_assistant_message(content: str = "Test response") -> AssistantMessage:
    """Creates a sample assistant message."""
    return AssistantMessage(
        role="assistant",
        content=content,
    )


def create_tool_message(
    call_id: str = "call_123",
    content: str = "Tool result"
) -> ToolMessage:
    """Creates a sample tool message."""
    return ToolMessage(
        id=call_id,
        role="tool",
        content=content,
        requestor="assistant",
    )


def create_assistant_with_tool_call(
    tool_name: str = "test_tool",
    arguments: dict = None
) -> AssistantMessage:
    """Creates an assistant message with tool calls."""
    if arguments is None:
        arguments = {"param": "value"}
    
    return AssistantMessage(
        role="assistant",
        tool_calls=[
            ToolCall(
                id="call_456",
                name=tool_name,
                arguments=arguments,
                requestor="assistant",
            )
        ],
    )

# Made with Bob
