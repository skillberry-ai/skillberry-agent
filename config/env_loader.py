"""
Environment variable loader for Skillberry Proxy Agent configuration.

This module provides utilities to load and parse environment variables
based on the configuration structure defined in config_structure.py.
"""

import os
import json
import logging
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)


# Type conversion constants
TRUE_VALUES = {"true", "1", "yes", "on", "enabled"}
FALSE_VALUES = {"false", "0", "no", "off", "disabled"}


class EnvVarError(Exception):
    """Base exception for environment variable errors."""
    pass


class EnvVarTypeError(EnvVarError):
    """Environment variable type conversion failed."""
    def __init__(self, env_var: str, expected_type: str, value: str, reason: str):
        self.env_var = env_var
        self.expected_type = expected_type
        self.value = value
        self.reason = reason
        super().__init__(
            f"Environment variable {env_var} has invalid value '{value}' "
            f"for type {expected_type}: {reason}"
        )


class EnvVarUnknownKeyError(EnvVarError):
    """Environment variable references unknown config key."""
    def __init__(self, env_var: str, path: str):
        self.env_var = env_var
        self.path = path
        super().__init__(
            f"Environment variable {env_var} references unknown config path: {path}"
        )


def parse_bool(value: str) -> bool:
    """
    Parse a string value as a boolean.
    
    Args:
        value: String value to parse
        
    Returns:
        Boolean value
        
    Raises:
        ValueError: If value is not a valid boolean string
    """
    value_lower = value.lower().strip()
    if value_lower in TRUE_VALUES:
        return True
    elif value_lower in FALSE_VALUES:
        return False
    else:
        raise ValueError(
            f"Invalid boolean value: '{value}'. "
            f"Valid true values: {TRUE_VALUES}. "
            f"Valid false values: {FALSE_VALUES}"
        )


def parse_int(value: str) -> int:
    """
    Parse a string value as an integer.
    
    Args:
        value: String value to parse
        
    Returns:
        Integer value
        
    Raises:
        ValueError: If value is not a valid integer
    """
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(f"Invalid integer value: '{value}': {e}")


def parse_float(value: str) -> float:
    """
    Parse a string value as a float.
    
    Args:
        value: String value to parse
        
    Returns:
        Float value
        
    Raises:
        ValueError: If value is not a valid float
    """
    try:
        return float(value)
    except ValueError as e:
        raise ValueError(f"Invalid float value: '{value}': {e}")


def parse_list(value: str) -> list:
    """
    Parse a string value as a JSON array.
    
    Args:
        value: String value to parse (JSON array format)
        
    Returns:
        List value
        
    Raises:
        ValueError: If value is not a valid JSON array
    """
    try:
        result = json.loads(value)
        if not isinstance(result, list):
            raise ValueError("Expected JSON array")
        return result
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON array: {e}")


def parse_dict(value: str) -> dict:
    """
    Parse a string value as a JSON object.
    
    Args:
        value: String value to parse (JSON object format)
        
    Returns:
        Dictionary value
        
    Raises:
        ValueError: If value is not a valid JSON object
    """
    try:
        result = json.loads(value)
        if not isinstance(result, dict):
            raise ValueError("Expected JSON object")
        return result
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON object: {e}")


def parse_env_value(value: str, expected_type: type) -> Any:
    """
    Convert string environment variable value to expected type.
    
    Args:
        value: String value from environment variable
        expected_type: Expected Python type (bool, int, float, str, list, dict)
        
    Returns:
        Converted value of the expected type
        
    Raises:
        ValueError: If conversion fails
    """
    if expected_type is bool:
        return parse_bool(value)
    elif expected_type is int:
        return parse_int(value)
    elif expected_type is float:
        return parse_float(value)
    elif expected_type is str:
        return value
    elif expected_type is list:
        return parse_list(value)
    elif expected_type is dict:
        return parse_dict(value)
    else:
        raise ValueError(f"Unsupported type: {expected_type}")


def get_env_var_name(path: str, prefix: str = "SPA") -> str:
    """
    Convert config path (using __ notation) to environment variable name.
    
    Args:
        path: Configuration path (e.g., "advanced__debug")
        prefix: Environment variable prefix (default: "SPA")
        
    Returns:
        Environment variable name (e.g., "SPA_ADVANCED__DEBUG")
        
    Examples:
        >>> get_env_var_name("temperature")
        'SPA_TEMPERATURE'
        >>> get_env_var_name("advanced__debug")
        'SPA_ADVANCED__DEBUG'
        >>> get_env_var_name("tools_react_agent__recursion_limit")
        'SPA_TOOLS_REACT_AGENT__RECURSION_LIMIT'
    """
    return f"{prefix}_{path.upper()}"


def validate_env_value(value: Any, expected_type: type, path: str) -> None:
    """
    Validate that parsed value matches expected type.
    
    Args:
        value: Parsed value to validate
        expected_type: Expected Python type
        path: Configuration path (for error messages)
        
    Raises:
        TypeError: If value doesn't match expected type
    """
    if not isinstance(value, expected_type):
        raise TypeError(
            f"Configuration path '{path}': expected type {expected_type.__name__}, "
            f"got {type(value).__name__}"
        )


def load_env_vars_for_structure(
    structure: Dict[str, Any],
    prefix: str = "SPA",
    _current_path: str = ""
) -> Dict[str, Any]:
    """
    Scan environment for variables matching config structure.
    
    Recursively traverses the configuration structure and checks for
    corresponding environment variables. Returns a dictionary with the
    same structure as the config, containing only values found in
    environment variables.
    
    Args:
        structure: Configuration structure dictionary
        prefix: Environment variable prefix (default: "SPA")
        _current_path: Internal parameter for recursion
        
    Returns:
        Dictionary with same structure as config, containing only
        values found in environment variables
        
    Examples:
        >>> structure = {
        ...     "temperature": {"type": "float", "default": 0},
        ...     "advanced": {
        ...         "type": "group",
        ...         "children": {
        ...             "debug": {"type": "bool", "default": False}
        ...         }
        ...     }
        ... }
        >>> os.environ["SPA_TEMPERATURE"] = "0.7"
        >>> os.environ["SPA_ADVANCED__DEBUG"] = "true"
        >>> result = load_env_vars_for_structure(structure)
        >>> result
        {'temperature': 0.7, 'advanced': {'debug': True}}
    """
    TYPE_MAP = {
        "int": int,
        "str": str,
        "string": str,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
    }
    
    result = {}
    
    for key, spec in structure.items():
        # Build the full path for this key
        full_path = f"{_current_path}__{key}" if _current_path else key
        
        if spec["type"] == "group":
            # Recursively process nested groups
            nested_result = load_env_vars_for_structure(
                spec["children"],
                prefix,
                full_path
            )
            if nested_result:
                result[key] = nested_result
        else:
            # Check for environment variable
            env_var_name = get_env_var_name(full_path, prefix)
            env_value = os.environ.get(env_var_name)
            
            if env_value is not None:
                # Environment variable exists, parse it
                expected_type = TYPE_MAP.get(spec["type"])
                
                if expected_type is None:
                    logger.warning(
                        f"Unknown type '{spec['type']}' for {full_path}, "
                        f"skipping environment variable {env_var_name}"
                    )
                    continue
                
                try:
                    parsed_value = parse_env_value(env_value, expected_type)
                    validate_env_value(parsed_value, expected_type, full_path)
                    result[key] = parsed_value
                    logger.info(
                        f"Loaded {env_var_name}={parsed_value} "
                        f"(type: {expected_type.__name__})"
                    )
                except (ValueError, TypeError) as e:
                    logger.error(
                        f"Failed to parse environment variable {env_var_name}: {e}. "
                        f"Using default value from config."
                    )
                    # Don't include in result, will fall back to default/file value
    
    return result


def get_all_env_var_names(structure: Dict[str, Any], prefix: str = "SPA") -> Set[str]:
    """
    Get all possible environment variable names for a configuration structure.
    
    Useful for documentation and validation.
    
    Args:
        structure: Configuration structure dictionary
        prefix: Environment variable prefix (default: "SPA")
        
    Returns:
        Set of all possible environment variable names
        
    Examples:
        >>> structure = {
        ...     "temperature": {"type": "float", "default": 0},
        ...     "advanced": {
        ...         "type": "group",
        ...         "children": {
        ...             "debug": {"type": "bool", "default": False}
        ...         }
        ...     }
        ... }
        >>> names = get_all_env_var_names(structure)
        >>> sorted(names)
        ['SPA_ADVANCED__DEBUG', 'SPA_TEMPERATURE']
    """
    def _collect_names(struct: Dict[str, Any], path: str = "") -> Set[str]:
        names = set()
        for key, spec in struct.items():
            full_path = f"{path}__{key}" if path else key
            if spec["type"] == "group":
                names.update(_collect_names(spec["children"], full_path))
            else:
                names.add(get_env_var_name(full_path, prefix))
        return names
    
    return _collect_names(structure)

# Made with Bob
