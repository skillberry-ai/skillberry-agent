import os
import json
import logging
from typing import Optional
from dotenv import load_dotenv

from config.env_loader import load_env_vars_for_structure

logger = logging.getLogger(__name__)


class DynamicConfig:
    TYPE_MAP = {
        "int": int,
        "str": str,
        "string": str,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
    }

    def __init__(
        self,
        structure,
        config_file="/tmp/tool-agent-config.json",
        enable_env_vars=True,
        env_prefix="SPA",
        dotenv_path: Optional[str] = None,
    ):
        """
        Initialize DynamicConfig with environment variable support.

        Args:
            structure: Configuration structure dictionary
            config_file: Path to JSON configuration file
            enable_env_vars: Whether to load environment variables
            env_prefix: Prefix for environment variables (default: "SPA")
            dotenv_path: Optional path to .env file (auto-discovers if None)
        """
        self.structure = structure
        self.config_file = config_file
        self.enable_env_vars = enable_env_vars
        self.env_prefix = env_prefix
        self.dotenv_path = dotenv_path

        # Load .env file if enabled
        if self.enable_env_vars:
            self._load_dotenv()

        self.config = self.load_config()

    def _load_dotenv(self):
        """
        Load environment variables from .env file using python-dotenv.

        Priority:
        1. System environment variables (highest)
        2. .env file variables

        The load_dotenv() function will NOT override existing environment variables.
        """
        if self.dotenv_path:
            # Load from specified path
            loaded = load_dotenv(dotenv_path=self.dotenv_path, override=False)
            if loaded:
                logger.info(f"Loaded environment variables from {self.dotenv_path}")
        else:
            # Auto-discover .env file in current directory or parent directories
            loaded = load_dotenv(override=False)
            if loaded:
                logger.info("Loaded environment variables from .env file")

    def load_config(self):
        """
        Load configuration with priority:
        1. Defaults from structure
        2. Values from config file
        3. Values from .env file (loaded into environment)
        4. System environment variables (HIGHEST PRIORITY)

        Environment variables (system + .env) ALWAYS override config file values when set.
        """
        # Step 1: Apply defaults
        config = self.apply_defaults(self.structure, {})

        # Step 2: Load from file
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    file_config = json.load(f)
                config = self._merge_configs(config, file_config)
                logger.debug(f"Loaded configuration from {self.config_file}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load config file {self.config_file}: {e}")
                # Continue with defaults

        # Step 3: Override with env vars (includes .env file variables)
        # Note: .env file was already loaded in __init__ via _load_dotenv()
        if self.enable_env_vars:
            env_config = load_env_vars_for_structure(self.structure, self.env_prefix)
            if env_config:
                config = self._merge_configs(config, env_config)
                logger.info(
                    f"Applied environment variable overrides with prefix {self.env_prefix}_"
                )

        return config

    def _merge_configs(self, base: dict, override: dict) -> dict:
        """
        Recursively merge override into base.
        Values in override ALWAYS replace values in base.

        Args:
            base: Base configuration dictionary
            override: Override configuration dictionary

        Returns:
            Merged configuration dictionary
        """
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursively merge nested dictionaries
                result[key] = self._merge_configs(result[key], value)
            else:
                # Override value
                result[key] = value
        return result

    def apply_defaults(self, structure, config):
        """Recursively applies default values to missing fields."""
        new_config = {}
        for key, value in structure.items():
            if value["type"] == "group":
                new_config[key] = self.apply_defaults(
                    value["children"], config.get(key, {})
                )
            else:
                new_config[key] = config.get(key, value["default"])
        return new_config

    def restore_defaults(self):
        """Restores all configuration values to their default settings."""
        self.config = self.apply_defaults(self.structure, {})
        self.save_config()

    def save_config(self):
        """Saves the configuration to a file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=4)
        except IOError as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        """Retrieves a configuration value using '__' notation for nesting."""
        keys = key.split("__")
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key, value):
        """Sets a configuration value using '__' notation with type validation."""
        keys = key.split("__")
        config = self.config
        current_structure = self.structure

        # Traverse structure to get an expected type
        for k in keys[:-1]:
            if k in current_structure and current_structure[k]["type"] == "group":
                current_structure = current_structure[k]["children"]
            else:
                raise KeyError(f"Invalid config path: {key}")

        last_key = keys[-1]
        if last_key not in current_structure:
            raise KeyError(f"Unknown config key: {key}")

        expected_type = self.TYPE_MAP.get(current_structure[last_key]["type"])

        if expected_type is float and isinstance(value, int):
            value = float(value)

        if expected_type and not isinstance(value, expected_type):
            raise TypeError(
                f"Expected '{expected_type.__name__}' for key '{key}', but got '{type(value).__name__}'"
            )

        # Traverse and set value
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        config[last_key] = value
        self.save_config()

    def get_type(self, key):
        """Returns the expected type of configuration key."""
        keys = key.split("__")
        current_structure = self.structure

        for k in keys[:-1]:
            if k in current_structure and current_structure[k]["type"] == "group":
                current_structure = current_structure[k]["children"]
            else:
                return None  # Key path does not exist

        last_key = keys[-1]
        if last_key not in current_structure:
            return None  # Unknown key

        return self.TYPE_MAP.get(current_structure[last_key]["type"])

    def isinstance_check(self, key):
        """Checks if the value stored under `key` matches its expected type."""
        keys = key.split("__")
        value = self.get(key)
        current_structure = self.structure

        for k in keys[:-1]:
            if k in current_structure and current_structure[k]["type"] == "group":
                current_structure = current_structure[k]["children"]
            else:
                return False  # Key path does not exist

        last_key = keys[-1]
        if last_key not in current_structure:
            return False  # Unknown key

        expected_type = self.TYPE_MAP.get(current_structure[last_key]["type"])
        if expected_type is None:
            return False  # Unknown type
        return isinstance(value, expected_type)
