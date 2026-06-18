"""
Integration tests for DynamicConfig with environment variable support.
"""

import pytest
import os
import json
import tempfile
from pathlib import Path
from config.config import DynamicConfig

# Test configuration structure
TEST_STRUCTURE = {
    "temperature": {"type": "float", "default": 0.0, "label": "Temperature"},
    "provider_name": {
        "type": "str",
        "default": "default_provider",
        "label": "Provider Name",
    },
    "max_tokens": {"type": "int", "default": 100, "label": "Max Tokens"},
    "advanced": {
        "type": "group",
        "label": "Advanced Settings",
        "children": {
            "debug": {"type": "bool", "default": False, "label": "Debug Mode"},
            "log_file": {
                "type": "str",
                "default": "/tmp/default.log",
                "label": "Log File",
            },
        },
    },
}


class TestDynamicConfigBasic:
    """Test basic DynamicConfig functionality."""

    def test_load_defaults(self, tmp_path):
        """Test loading with only defaults."""
        config_file = tmp_path / "config.json"
        config = DynamicConfig(
            TEST_STRUCTURE, config_file=str(config_file), enable_env_vars=False
        )

        assert config.get("temperature") == 0.0
        assert config.get("provider_name") == "default_provider"
        assert config.get("max_tokens") == 100
        assert config.get("advanced__debug") is False
        assert config.get("advanced__log_file") == "/tmp/default.log"

    def test_load_from_file(self, tmp_path):
        """Test loading from config file."""
        config_file = tmp_path / "config.json"

        # Create config file
        file_data = {
            "temperature": 0.5,
            "provider_name": "custom_provider",
            "max_tokens": 200,
            "advanced": {"debug": True, "log_file": "/tmp/custom.log"},
        }
        with open(config_file, "w") as f:
            json.dump(file_data, f)

        config = DynamicConfig(
            TEST_STRUCTURE, config_file=str(config_file), enable_env_vars=False
        )

        assert config.get("temperature") == 0.5
        assert config.get("provider_name") == "custom_provider"
        assert config.get("max_tokens") == 200
        assert config.get("advanced__debug") is True
        assert config.get("advanced__log_file") == "/tmp/custom.log"


class TestDynamicConfigEnvVars:
    """Test environment variable support."""

    def test_env_var_overrides_default(self, tmp_path, monkeypatch):
        """Test that env var overrides default value."""
        config_file = tmp_path / "config.json"
        monkeypatch.setenv("SPA_TEMPERATURE", "0.8")

        config = DynamicConfig(TEST_STRUCTURE, config_file=str(config_file))

        assert config.get("temperature") == 0.8

    def test_env_var_overrides_file(self, tmp_path, monkeypatch):
        """Test that env var ALWAYS overrides config file value."""
        config_file = tmp_path / "config.json"

        # Create config file with value
        file_data = {"temperature": 0.5}
        with open(config_file, "w") as f:
            json.dump(file_data, f)

        # Override with env var
        monkeypatch.setenv("SPA_TEMPERATURE", "0.9")

        config = DynamicConfig(TEST_STRUCTURE, config_file=str(config_file))

        # Env var should win
        assert config.get("temperature") == 0.9

    def test_multiple_env_vars(self, tmp_path, monkeypatch):
        """Test multiple environment variables."""
        config_file = tmp_path / "config.json"

        monkeypatch.setenv("SPA_TEMPERATURE", "0.7")
        monkeypatch.setenv("SPA_PROVIDER_NAME", "env_provider")
        monkeypatch.setenv("SPA_MAX_TOKENS", "500")

        config = DynamicConfig(TEST_STRUCTURE, config_file=str(config_file))

        assert config.get("temperature") == 0.7
        assert config.get("provider_name") == "env_provider"
        assert config.get("max_tokens") == 500

    def test_nested_env_vars(self, tmp_path, monkeypatch):
        """Test nested environment variables."""
        config_file = tmp_path / "config.json"

        monkeypatch.setenv("SPA_ADVANCED__DEBUG", "true")
        monkeypatch.setenv("SPA_ADVANCED__LOG_FILE", "/tmp/env.log")

        config = DynamicConfig(TEST_STRUCTURE, config_file=str(config_file))

        assert config.get("advanced__debug") is True
        assert config.get("advanced__log_file") == "/tmp/env.log"

    def test_partial_env_override(self, tmp_path, monkeypatch):
        """Test partial override with env vars."""
        config_file = tmp_path / "config.json"

        # File has some values
        file_data = {"temperature": 0.5, "provider_name": "file_provider"}
        with open(config_file, "w") as f:
            json.dump(file_data, f)

        # Env var overrides only temperature
        monkeypatch.setenv("SPA_TEMPERATURE", "0.9")

        config = DynamicConfig(TEST_STRUCTURE, config_file=str(config_file))

        assert config.get("temperature") == 0.9  # From env var
        assert config.get("provider_name") == "file_provider"  # From file
        assert config.get("max_tokens") == 100  # From default


class TestDynamicConfigPriority:
    """Test configuration priority system."""

    def test_priority_env_over_file_over_default(self, tmp_path, monkeypatch):
        """Test: env var > file > default"""
        config_file = tmp_path / "config.json"

        # Default is 0.0
        # Set file to 0.5
        file_data = {"temperature": 0.5}
        with open(config_file, "w") as f:
            json.dump(file_data, f)

        # Set env var to 0.9
        monkeypatch.setenv("SPA_TEMPERATURE", "0.9")

        config = DynamicConfig(TEST_STRUCTURE, config_file=str(config_file))

        # Env var should win
        assert config.get("temperature") == 0.9

    def test_file_over_default(self, tmp_path):
        """Test: file > default (no env var)."""
        config_file = tmp_path / "config.json"

        # Default is 0.0
        # Set file to 0.5
        file_data = {"temperature": 0.5}
        with open(config_file, "w") as f:
            json.dump(file_data, f)

        config = DynamicConfig(TEST_STRUCTURE, config_file=str(config_file))

        # File should win over default
        assert config.get("temperature") == 0.5

    def test_default_when_nothing_else(self, tmp_path):
        """Test: default when no file or env var."""
        config_file = tmp_path / "config.json"

        config = DynamicConfig(TEST_STRUCTURE, config_file=str(config_file))

        # Should use default
        assert config.get("temperature") == 0.0


class TestDynamicConfigDotenv:
    """Test .env file support."""

    def test_dotenv_file_loaded(self, tmp_path, monkeypatch):
        """Test that .env file is loaded automatically."""
        # Clear any existing SPA_ env vars
        for key in list(os.environ.keys()):
            if key.startswith("SPA_"):
                monkeypatch.delenv(key, raising=False)

        config_file = tmp_path / "config.json"
        env_file = tmp_path / ".env"

        # Create .env file
        env_file.write_text("SPA_TEMPERATURE=0.7\nSPA_PROVIDER_NAME=dotenv_provider")

        # Use explicit dotenv_path instead of chdir
        config = DynamicConfig(
            TEST_STRUCTURE, config_file=str(config_file), dotenv_path=str(env_file)
        )

        assert config.get("temperature") == 0.7
        assert config.get("provider_name") == "dotenv_provider"

    def test_system_env_overrides_dotenv(self, tmp_path, monkeypatch):
        """Test that system env vars override .env file."""
        # Clear any existing SPA_ env vars
        for key in list(os.environ.keys()):
            if key.startswith("SPA_"):
                monkeypatch.delenv(key, raising=False)

        config_file = tmp_path / "config.json"
        env_file = tmp_path / ".env"

        # Create .env file with one value
        env_file.write_text("SPA_TEMPERATURE=0.7")

        # Set system env var with different value
        monkeypatch.setenv("SPA_TEMPERATURE", "0.9")

        config = DynamicConfig(
            TEST_STRUCTURE, config_file=str(config_file), dotenv_path=str(env_file)
        )

        # System env var should win
        assert config.get("temperature") == 0.9

    def test_dotenv_with_file_config(self, tmp_path, monkeypatch):
        """Test .env file with config file."""
        # Clear any existing SPA_ env vars
        for key in list(os.environ.keys()):
            if key.startswith("SPA_"):
                monkeypatch.delenv(key, raising=False)

        config_file = tmp_path / "config.json"
        env_file = tmp_path / ".env"

        # Config file
        file_data = {"temperature": 0.5, "provider_name": "file_provider"}
        with open(config_file, "w") as f:
            json.dump(file_data, f)

        # .env file overrides temperature
        env_file.write_text("SPA_TEMPERATURE=0.8")

        config = DynamicConfig(
            TEST_STRUCTURE, config_file=str(config_file), dotenv_path=str(env_file)
        )

        assert config.get("temperature") == 0.8  # From .env
        assert config.get("provider_name") == "file_provider"  # From file

    def test_custom_dotenv_path(self, tmp_path, monkeypatch):
        """Test loading .env from custom path."""
        # Clear any existing SPA_ env vars
        for key in list(os.environ.keys()):
            if key.startswith("SPA_"):
                monkeypatch.delenv(key, raising=False)

        config_file = tmp_path / "config.json"
        env_file = tmp_path / "custom.env"

        # Create custom .env file
        env_file.write_text("SPA_TEMPERATURE=0.6")

        config = DynamicConfig(
            TEST_STRUCTURE, config_file=str(config_file), dotenv_path=str(env_file)
        )

        assert config.get("temperature") == 0.6


class TestDynamicConfigUIInteraction:
    """Test Configuration UI interaction with env vars."""

    def test_set_value_with_env_override(self, tmp_path, monkeypatch):
        """Test setting value when env var is set."""
        config_file = tmp_path / "config.json"

        # Set env var
        monkeypatch.setenv("SPA_TEMPERATURE", "0.9")

        config = DynamicConfig(TEST_STRUCTURE, config_file=str(config_file))

        # Initial value from env var
        assert config.get("temperature") == 0.9

        # User changes via UI
        config.set("temperature", 0.7)

        # Value changes in current session
        assert config.get("temperature") == 0.7

        # Config file is updated
        with open(config_file) as f:
            file_data = json.load(f)
        assert file_data["temperature"] == 0.7

    def test_restart_reverts_to_env_var(self, tmp_path, monkeypatch):
        """Test that restart reverts to env var value."""
        config_file = tmp_path / "config.json"

        # Set env var
        monkeypatch.setenv("SPA_TEMPERATURE", "0.9")

        # First session
        config = DynamicConfig(TEST_STRUCTURE, config_file=str(config_file))
        assert config.get("temperature") == 0.9

        # User changes via UI
        config.set("temperature", 0.7)
        assert config.get("temperature") == 0.7

        # Simulate restart - create new config instance
        config2 = DynamicConfig(TEST_STRUCTURE, config_file=str(config_file))

        # Should revert to env var
        assert config2.get("temperature") == 0.9

    def test_set_value_without_env_override(self, tmp_path):
        """Test setting value when no env var is set."""
        config_file = tmp_path / "config.json"

        config = DynamicConfig(
            TEST_STRUCTURE, config_file=str(config_file), enable_env_vars=False
        )

        # Initial value from default
        assert config.get("temperature") == 0.0

        # User changes via UI
        config.set("temperature", 0.7)

        # Value changes
        assert config.get("temperature") == 0.7

        # Reload - should persist
        config2 = DynamicConfig(
            TEST_STRUCTURE, config_file=str(config_file), enable_env_vars=False
        )
        assert config2.get("temperature") == 0.7


class TestDynamicConfigCustomPrefix:
    """Test custom environment variable prefix."""

    def test_custom_prefix(self, tmp_path, monkeypatch):
        """Test using custom prefix."""
        config_file = tmp_path / "config.json"

        monkeypatch.setenv("CUSTOM_TEMPERATURE", "0.8")

        config = DynamicConfig(
            TEST_STRUCTURE, config_file=str(config_file), env_prefix="CUSTOM"
        )

        assert config.get("temperature") == 0.8

    def test_wrong_prefix_ignored(self, tmp_path, monkeypatch):
        """Test that wrong prefix is ignored."""
        # Clear any existing SPA_ env vars
        for key in list(os.environ.keys()):
            if key.startswith("SPA_") or key.startswith("CUSTOM_"):
                monkeypatch.delenv(key, raising=False)

        config_file = tmp_path / "config.json"

        monkeypatch.setenv("WRONG_TEMPERATURE", "0.8")

        config = DynamicConfig(
            TEST_STRUCTURE, config_file=str(config_file), env_prefix="SPA"
        )

        # Should use default, not env var with wrong prefix
        assert config.get("temperature") == 0.0


class TestDynamicConfigDisableEnvVars:
    """Test disabling environment variable support."""

    def test_disable_env_vars(self, tmp_path, monkeypatch):
        """Test that env vars are ignored when disabled."""
        config_file = tmp_path / "config.json"

        monkeypatch.setenv("SPA_TEMPERATURE", "0.9")

        config = DynamicConfig(
            TEST_STRUCTURE, config_file=str(config_file), enable_env_vars=False
        )

        # Should use default, not env var
        assert config.get("temperature") == 0.0


# Made with Bob
