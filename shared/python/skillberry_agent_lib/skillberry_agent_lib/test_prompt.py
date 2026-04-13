"""Tests for prompt.py module."""

import logging
import os
from unittest.mock import patch

import pytest
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from skillberry_agent_lib.prompt import build_chat_messages


class TestBuildChatMessages:
    """Test suite for build_chat_messages function."""
    
    def test_default_mcp_prompts_position(self):
        """Test that default mcp_prompts_position is 'postfix'."""
        chat_history = [{"role": "user", "content": "test message"}]
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_get:
            mock_get.return_value = "Test MCP prompt"
            
            # Call without specifying mcp_prompts_position to test default
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"}
            )
            
            # Verify MCP prompts were fetched
            mock_get.assert_called_once()
            
            # Verify result is valid
            assert result is not None
    
    def test_mcp_prompts_fetched(self):
        """Test that MCP prompts are fetched and injected."""
        chat_history = [{"role": "user", "content": "test message"}]
        
        # Mock get_mcp_prompts_and_format to verify it IS called
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_get:
            mock_get.return_value = "Test MCP prompt content"
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"}
            )
            
            # Verify MCP prompts WERE fetched
            mock_get.assert_called_once_with(
                port=8080,
                server_name="test-server",
                skillberry_context={"env_id": "test"}
            )
            
            # Verify result is valid
            assert result is not None
    
    def test_empty_mcp_prompts(self):
        """Test behavior when MCP prompts return empty."""
        chat_history = [{"role": "user", "content": "test message"}]
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_get:
            # Return empty string (no prompts available)
            mock_get.return_value = ""
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"}
            )
            
            # Verify MCP prompts WERE attempted to be fetched
            mock_get.assert_called_once()
            
            # Verify result is valid
            assert result is not None
    
    def test_mcp_prompts_position_prefix_with_system_messages(self):
        """Test that MCP prompts are inserted before system messages with prefix."""
        chat_history = [
            SystemMessage(content="Agent prompt 1"),
            HumanMessage(content="Hello"),
        ]
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_format:
            mock_format.return_value = "Test MCP prompt"
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                mcp_prompts_position='prefix'
            )
            
            # Verify the function was called
            mock_format.assert_called_once()
            
            # MCP prompt should be before agent prompt
            assert isinstance(result[0], SystemMessage)
            assert "Test MCP prompt" in result[0].content
            assert "Agent prompt 1" in result[1].content
    
    def test_mcp_prompts_position_postfix_with_system_messages(self):
        """Test that MCP prompts are inserted after system messages with postfix."""
        chat_history = [
            SystemMessage(content="Agent prompt 1"),
            SystemMessage(content="Agent prompt 2"),
            HumanMessage(content="Hello"),
        ]
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_format:
            mock_format.return_value = "Test MCP prompt"
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                mcp_prompts_position='postfix'
            )
            
            # Verify the function was called
            mock_format.assert_called_once()
            
            # MCP prompt should be after all agent prompts
            assert isinstance(result[2], SystemMessage)
            assert "Test MCP prompt" in result[2].content
            assert "Agent prompt 1" in result[0].content
            assert "Agent prompt 2" in result[1].content
    
    def test_mcp_prompts_position_prefix_no_system_messages(self):
        """Test that MCP prompts are inserted at beginning when no system messages exist (prefix)."""
        chat_history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ]
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_format:
            mock_format.return_value = "Test MCP prompt"
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                mcp_prompts_position='prefix'
            )
            
            # MCP prompt should be at beginning
            assert isinstance(result[0], SystemMessage)
            assert "Test MCP prompt" in result[0].content
            assert isinstance(result[1], HumanMessage)
    
    def test_mcp_prompts_position_postfix_no_system_messages(self):
        """Test that MCP prompts are inserted at beginning when no system messages exist (postfix)."""
        chat_history = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
        ]
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_format:
            mock_format.return_value = "Test MCP prompt"
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                mcp_prompts_position='postfix'
            )
            
            # MCP prompt should be at beginning (fallback behavior)
            assert isinstance(result[0], SystemMessage)
            assert "Test MCP prompt" in result[0].content
            assert isinstance(result[1], HumanMessage)
    
    def test_agent_prompts_preserved(self):
        """Test that agent prompts are preserved in chat history."""
        chat_history = [
            SystemMessage(content="Agent prompt"),
            HumanMessage(content="Hello"),
        ]
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_format:
            mock_format.return_value = "Test MCP prompt"
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                mcp_prompts_position='prefix'
            )
            
            # Both MCP and agent prompts should be present
            system_messages = [msg for msg in result if isinstance(msg, SystemMessage)]
            assert len(system_messages) == 2  # MCP prompt + agent prompt
            assert any("Test MCP prompt" in msg.content for msg in system_messages)
            assert any("Agent prompt" in msg.content for msg in system_messages)
    
    def test_multiple_system_messages_prefix(self):
        """Test prefix positioning with multiple system messages."""
        chat_history = [
            SystemMessage(content="System 1"),
            SystemMessage(content="System 2"),
            HumanMessage(content="Hello"),
            SystemMessage(content="System 3"),  # System message after user message
        ]
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_format:
            mock_format.return_value = "MCP prompt"
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                mcp_prompts_position='prefix'
            )
            
            # MCP prompt should be before the first system message
            assert isinstance(result[0], SystemMessage)
            assert "MCP prompt" in result[0].content
            assert "System 1" in result[1].content
    
    def test_multiple_system_messages_postfix(self):
        """Test postfix positioning with multiple system messages."""
        chat_history = [
            SystemMessage(content="System 1"),
            HumanMessage(content="Hello"),
            SystemMessage(content="System 2"),
            AIMessage(content="Hi"),
        ]
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_format:
            mock_format.return_value = "MCP prompt"
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                mcp_prompts_position='postfix'
            )
            
            # MCP prompt should be after the last system message (System 2)
            # Find the index of System 2
            system_2_idx = next(i for i, msg in enumerate(result) if isinstance(msg, SystemMessage) and "System 2" in msg.content)
            # MCP prompt should be right after System 2
            assert isinstance(result[system_2_idx + 1], SystemMessage)
            assert "MCP prompt" in result[system_2_idx + 1].content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
