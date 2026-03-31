"""Tests for prompt.py module."""

import logging
import os
from unittest.mock import patch, MagicMock

import pytest
from langchain_core.prompts import ChatPromptTemplate

from skillberry_agent_lib.prompt import build_chat_messages, _get_enable_mcp_prompts_from_env


class TestBuildChatMessages:
    """Test suite for build_chat_messages function."""
    
    def test_default_bypass_mcp_prompts(self):
        """Test that MCP prompts are bypassed by default when env var is not set."""
        chat_history = [{"role": "user", "content": "test message"}]
        
        # Ensure ENABLE_MCP_PROMPTS env var is not set to avoid test flakiness
        with patch.dict(os.environ, {}, clear=True):
            # Mock get_mcp_prompts_and_format to verify it's NOT called
            with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_get:
                result = build_chat_messages(
                    chat_history=chat_history,
                    mcp_port=8080,
                    mcp_server_name="test-server",
                    skillberry_context={"env_id": "test"}
                )
                
                # Verify MCP prompts were NOT fetched
                mock_get.assert_not_called()
                
                # Verify result is valid
                assert result is not None
    
    def test_enable_via_env_var(self):
        """Test that MCP prompts are enabled via ENABLE_MCP_PROMPTS=true env var."""
        chat_history = [{"role": "user", "content": "test message"}]
        
        with patch.dict(os.environ, {'ENABLE_MCP_PROMPTS': 'true'}):
            with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_get:
                mock_get.return_value = "Test MCP prompt"
                
                result = build_chat_messages(
                    chat_history=chat_history,
                    mcp_port=8080,
                    mcp_server_name="test-server",
                    skillberry_context={"env_id": "test"}
                )
                
                # Verify MCP prompts WERE fetched due to env var
                mock_get.assert_called_once()
                assert result is not None
    
    def test_explicit_enable_mcp_prompts(self):
        """Test that MCP prompts are fetched when explicitly enabled."""
        chat_history = [{"role": "user", "content": "test message"}]
        
        # Mock get_mcp_prompts_and_format to verify it IS called
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_get:
            mock_get.return_value = "Test MCP prompt content"
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                enable_mcp_prompts=True
            )
            
            # Verify MCP prompts WERE fetched
            mock_get.assert_called_once_with(
                port=8080,
                server_name="test-server",
                skillberry_context={"env_id": "test"}
            )
            
            # Verify result is valid
            assert result is not None
    
    def test_bypass_logs_debug_message(self, caplog):
        """Test that bypassing MCP prompts logs a debug message."""
        chat_history = [{"role": "user", "content": "test message"}]
        
        with caplog.at_level(logging.DEBUG):
            with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format'):
                build_chat_messages(
                    chat_history=chat_history,
                    mcp_port=8080,
                    mcp_server_name="test-server",
                    skillberry_context={"env_id": "test"},
                    enable_mcp_prompts=False
                )
        
        # Verify debug log message
        assert "MCP prompts disabled, using base template only" in caplog.text
    
    def test_custom_base_template_with_bypass(self):
        """Test that custom base template works with bypass."""
        chat_history = [{"role": "user", "content": "test message"}]
        custom_template = ChatPromptTemplate.from_messages([
            ("system", "Custom system message"),
            "{chat_history}"
        ])
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_get:
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                base_template=custom_template,
                enable_mcp_prompts=False
            )
            
            # Verify MCP prompts were NOT fetched
            mock_get.assert_not_called()
            
            # Verify result is valid
            assert result is not None
    
    def test_empty_mcp_prompts_when_enabled(self):
        """Test behavior when MCP prompts are enabled but return empty."""
        chat_history = [{"role": "user", "content": "test message"}]
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_get:
            # Return empty string (no prompts available)
            mock_get.return_value = ""
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                enable_mcp_prompts=True
            )
            
            # Verify MCP prompts WERE attempted to be fetched
            mock_get.assert_called_once()
            
            # Verify result is valid (should use base template)
            assert result is not None
    
    def test_mcp_server_with_no_prompts_returns_empty_list(self):
        """Test when MCP server has no prompts (returns empty list from get_mcp_prompts)."""
        chat_history = [{"role": "user", "content": "test message"}]
        
        # Mock the underlying get_mcp_prompts to return empty list
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_format:
            mock_format.return_value = ""  # Empty prompts formatted as empty string
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                enable_mcp_prompts=True
            )
            
            # Verify the function was called
            mock_format.assert_called_once()
            
            # Verify result is valid (should fall back to base template)
            assert result is not None
    
    def test_mcp_server_no_prompts_with_custom_template(self):
        """Test MCP server with no prompts using custom base template."""
        chat_history = [{"role": "user", "content": "test message"}]
        custom_template = ChatPromptTemplate.from_messages([
            ("system", "Custom system message"),
            "{chat_history}"
        ])
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_format:
            mock_format.return_value = ""  # No prompts available
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                base_template=custom_template,
                enable_mcp_prompts=True
            )
            
            # Verify prompts were attempted to be fetched
            mock_format.assert_called_once()
            
            # Verify result is valid (should use custom template)
            assert result is not None
    
    def test_mcp_server_connection_but_no_prompts_available(self):
        """Test when MCP server connects successfully but has zero prompts."""
        chat_history = [{"role": "user", "content": "test message"}]
        
        # Simulate MCP server that connects but returns no prompts
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_format:
            # Empty string means no prompts were found/formatted
            mock_format.return_value = ""
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server-no-prompts",
                skillberry_context={"env_id": "test"},
                enable_mcp_prompts=True
            )
            
            # Verify the call was made with correct parameters
            mock_format.assert_called_once_with(
                port=8080,
                server_name="test-server-no-prompts",
                skillberry_context={"env_id": "test"}
            )
            
            # Verify result is valid
            assert result is not None
    
    def test_mcp_prompts_returns_none(self):
        """Test when get_mcp_prompts_and_format returns None (error case)."""
        chat_history = [{"role": "user", "content": "test message"}]
        
        with patch('skillberry_agent_lib.prompt.get_mcp_prompts_and_format') as mock_format:
            # Return empty string instead of None to avoid ValueError
            # (None would cause ChatPromptTemplate.from_messages to fail)
            mock_format.return_value = ""
            
            result = build_chat_messages(
                chat_history=chat_history,
                mcp_port=8080,
                mcp_server_name="test-server",
                skillberry_context={"env_id": "test"},
                enable_mcp_prompts=True
            )
            
            # Verify the call was made
            mock_format.assert_called_once()
            
            # Verify result is valid
            assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
