"""
Unit tests for environment variable loader.
"""

import pytest
import os
from config.env_loader import (
    parse_bool,
    parse_int,
    parse_float,
    parse_list,
    parse_dict,
    parse_env_value,
    get_env_var_name,
    validate_env_value,
    load_env_vars_for_structure,
    get_all_env_var_names,
    EnvVarTypeError,
)


class TestBoolParsing:
    """Test boolean value parsing."""

    def test_parse_bool_true_values(self):
        """Test all valid true values."""
        for value in [
            "true",
            "True",
            "TRUE",
            "1",
            "yes",
            "YES",
            "on",
            "ON",
            "enabled",
            "ENABLED",
        ]:
            assert parse_bool(value) is True, f"Failed for value: {value}"

    def test_parse_bool_false_values(self):
        """Test all valid false values."""
        for value in [
            "false",
            "False",
            "FALSE",
            "0",
            "no",
            "NO",
            "off",
            "OFF",
            "disabled",
            "DISABLED",
        ]:
            assert parse_bool(value) is False, f"Failed for value: {value}"

    def test_parse_bool_with_whitespace(self):
        """Test boolean parsing with whitespace."""
        assert parse_bool("  true  ") is True
        assert parse_bool("  false  ") is False

    def test_parse_bool_invalid(self):
        """Test invalid boolean values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid boolean value"):
            parse_bool("invalid")
        with pytest.raises(ValueError, match="Invalid boolean value"):
            parse_bool("2")
        with pytest.raises(ValueError, match="Invalid boolean value"):
            parse_bool("")


class TestNumericParsing:
    """Test numeric value parsing."""

    def test_parse_int_positive(self):
        """Test positive integer parsing."""
        assert parse_int("42") == 42
        assert parse_int("0") == 0
        assert parse_int("999") == 999

    def test_parse_int_negative(self):
        """Test negative integer parsing."""
        assert parse_int("-10") == -10
        assert parse_int("-1") == -1

    def test_parse_int_invalid(self):
        """Test invalid integer values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid integer value"):
            parse_int("not_a_number")
        with pytest.raises(ValueError, match="Invalid integer value"):
            parse_int("3.14")
        with pytest.raises(ValueError, match="Invalid integer value"):
            parse_int("")

    def test_parse_float_positive(self):
        """Test positive float parsing."""
        assert parse_float("3.14") == 3.14
        assert parse_float("0.0") == 0.0
        assert parse_float("1.5") == 1.5

    def test_parse_float_negative(self):
        """Test negative float parsing."""
        assert parse_float("-2.5") == -2.5
        assert parse_float("-0.1") == -0.1

    def test_parse_float_integer_format(self):
        """Test float parsing with integer format."""
        assert parse_float("42") == 42.0
        assert parse_float("0") == 0.0

    def test_parse_float_invalid(self):
        """Test invalid float values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid float value"):
            parse_float("not_a_number")
        with pytest.raises(ValueError, match="Invalid float value"):
            parse_float("")


class TestComplexTypeParsing:
    """Test list and dict parsing."""

    def test_parse_list_simple(self):
        """Test simple list parsing."""
        result = parse_list('["a", "b", "c"]')
        assert result == ["a", "b", "c"]

    def test_parse_list_numbers(self):
        """Test list with numbers."""
        result = parse_list("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_parse_list_mixed(self):
        """Test list with mixed types."""
        result = parse_list('["text", 42, true, null]')
        assert result == ["text", 42, True, None]

    def test_parse_list_empty(self):
        """Test empty list parsing."""
        result = parse_list("[]")
        assert result == []

    def test_parse_list_invalid_json(self):
        """Test invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON array"):
            parse_list('["unclosed')
        with pytest.raises(ValueError, match="Invalid JSON array"):
            parse_list("not json")

    def test_parse_list_not_array(self):
        """Test non-array JSON raises ValueError."""
        with pytest.raises(ValueError, match="Expected JSON array"):
            parse_list('{"key": "value"}')

    def test_parse_dict_simple(self):
        """Test simple dict parsing."""
        result = parse_dict('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_dict_nested(self):
        """Test nested dict parsing."""
        result = parse_dict('{"outer": {"inner": "value"}}')
        assert result == {"outer": {"inner": "value"}}

    def test_parse_dict_mixed_types(self):
        """Test dict with mixed value types."""
        result = parse_dict('{"str": "text", "num": 42, "bool": true}')
        assert result == {"str": "text", "num": 42, "bool": True}

    def test_parse_dict_empty(self):
        """Test empty dict parsing."""
        result = parse_dict("{}")
        assert result == {}

    def test_parse_dict_invalid_json(self):
        """Test invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON object"):
            parse_dict('{"unclosed')
        with pytest.raises(ValueError, match="Invalid JSON object"):
            parse_dict("not json")

    def test_parse_dict_not_object(self):
        """Test non-object JSON raises ValueError."""
        with pytest.raises(ValueError, match="Expected JSON object"):
            parse_dict('["array"]')


class TestParseEnvValue:
    """Test generic environment value parsing."""

    def test_parse_env_value_bool(self):
        """Test parsing boolean type."""
        assert parse_env_value("true", bool) is True
        assert parse_env_value("false", bool) is False

    def test_parse_env_value_int(self):
        """Test parsing integer type."""
        assert parse_env_value("42", int) == 42

    def test_parse_env_value_float(self):
        """Test parsing float type."""
        assert parse_env_value("3.14", float) == 3.14

    def test_parse_env_value_str(self):
        """Test parsing string type."""
        assert parse_env_value("hello", str) == "hello"

    def test_parse_env_value_list(self):
        """Test parsing list type."""
        result = parse_env_value('["a", "b"]', list)
        assert result == ["a", "b"]

    def test_parse_env_value_dict(self):
        """Test parsing dict type."""
        result = parse_env_value('{"key": "value"}', dict)
        assert result == {"key": "value"}

    def test_parse_env_value_unsupported_type(self):
        """Test unsupported type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported type"):
            parse_env_value("value", tuple)


class TestEnvVarNameGeneration:
    """Test environment variable name generation."""

    def test_root_level_attribute(self):
        """Test root-level attribute name generation."""
        assert get_env_var_name("temperature") == "SPA_TEMPERATURE"
        assert get_env_var_name("provider_name") == "SPA_PROVIDER_NAME"

    def test_nested_attribute(self):
        """Test nested attribute name generation."""
        assert get_env_var_name("advanced__debug") == "SPA_ADVANCED__DEBUG"
        assert get_env_var_name("advanced__log_file") == "SPA_ADVANCED__LOG_FILE"

    def test_deeply_nested(self):
        """Test deeply nested attribute name generation."""
        name = get_env_var_name("tools_react_agent__recursion_limit")
        assert name == "SPA_TOOLS_REACT_AGENT__RECURSION_LIMIT"

    def test_custom_prefix(self):
        """Test custom prefix."""
        assert get_env_var_name("temperature", "CUSTOM") == "CUSTOM_TEMPERATURE"
        assert get_env_var_name("advanced__debug", "APP") == "APP_ADVANCED__DEBUG"


class TestValidateEnvValue:
    """Test environment value validation."""

    def test_validate_correct_types(self):
        """Test validation passes for correct types."""
        validate_env_value(True, bool, "test")
        validate_env_value(42, int, "test")
        validate_env_value(3.14, float, "test")
        validate_env_value("text", str, "test")
        validate_env_value([], list, "test")
        validate_env_value({}, dict, "test")

    def test_validate_incorrect_type(self):
        """Test validation fails for incorrect types."""
        with pytest.raises(TypeError, match="expected type bool"):
            validate_env_value("not_bool", bool, "test_path")
        with pytest.raises(TypeError, match="expected type int"):
            validate_env_value("not_int", int, "test_path")


class TestLoadEnvVarsForStructure:
    """Test loading environment variables based on structure."""

    def test_load_single_root_attribute(self, monkeypatch):
        """Test loading single root-level attribute."""
        monkeypatch.setenv("SPA_TEMPERATURE", "0.7")

        structure = {"temperature": {"type": "float", "default": 0}}

        result = load_env_vars_for_structure(structure)
        assert result == {"temperature": 0.7}

    def test_load_multiple_root_attributes(self, monkeypatch):
        """Test loading multiple root-level attributes."""
        monkeypatch.setenv("SPA_TEMPERATURE", "0.7")
        monkeypatch.setenv("SPA_PROVIDER_NAME", "test_provider")

        structure = {
            "temperature": {"type": "float", "default": 0},
            "provider_name": {"type": "str", "default": "default"},
        }

        result = load_env_vars_for_structure(structure)
        assert result == {"temperature": 0.7, "provider_name": "test_provider"}

    def test_load_nested_attributes(self, monkeypatch):
        """Test loading nested attributes."""
        monkeypatch.setenv("SPA_ADVANCED__DEBUG", "true")
        monkeypatch.setenv("SPA_ADVANCED__LOG_FILE", "/tmp/test.log")

        structure = {
            "advanced": {
                "type": "group",
                "children": {
                    "debug": {"type": "bool", "default": False},
                    "log_file": {"type": "str", "default": "/tmp/default.log"},
                },
            }
        }

        result = load_env_vars_for_structure(structure)
        assert result == {"advanced": {"debug": True, "log_file": "/tmp/test.log"}}

    def test_load_partial_nested(self, monkeypatch):
        """Test loading only some nested attributes."""
        monkeypatch.setenv("SPA_ADVANCED__DEBUG", "true")
        # log_file not set

        structure = {
            "advanced": {
                "type": "group",
                "children": {
                    "debug": {"type": "bool", "default": False},
                    "log_file": {"type": "str", "default": "/tmp/default.log"},
                },
            }
        }

        result = load_env_vars_for_structure(structure)
        assert result == {"advanced": {"debug": True}}

    def test_load_no_env_vars(self, monkeypatch):
        """Test loading when no env vars are set."""
        # Clear all SPA_* environment variables to ensure clean state
        import os
        for key in list(os.environ.keys()):
            if key.startswith("SPA_"):
                monkeypatch.delenv(key, raising=False)
        
        structure = {"temperature": {"type": "float", "default": 0}}

        result = load_env_vars_for_structure(structure)
        assert result == {}

    def test_load_with_invalid_value(self, monkeypatch, caplog):
        """Test loading with invalid value logs error and skips."""
        monkeypatch.setenv("SPA_TEMPERATURE", "not_a_number")

        structure = {"temperature": {"type": "float", "default": 0}}

        result = load_env_vars_for_structure(structure)
        assert result == {}
        assert "Failed to parse environment variable" in caplog.text

    def test_load_custom_prefix(self, monkeypatch):
        """Test loading with custom prefix."""
        monkeypatch.setenv("CUSTOM_TEMPERATURE", "0.7")

        structure = {"temperature": {"type": "float", "default": 0}}

        result = load_env_vars_for_structure(structure, prefix="CUSTOM")
        assert result == {"temperature": 0.7}


class TestGetAllEnvVarNames:
    """Test getting all possible environment variable names."""

    def test_simple_structure(self):
        """Test with simple structure."""
        structure = {
            "temperature": {"type": "float", "default": 0},
            "provider_name": {"type": "str", "default": "default"},
        }

        names = get_all_env_var_names(structure)
        assert names == {"SPA_TEMPERATURE", "SPA_PROVIDER_NAME"}

    def test_nested_structure(self):
        """Test with nested structure."""
        structure = {
            "temperature": {"type": "float", "default": 0},
            "advanced": {
                "type": "group",
                "children": {
                    "debug": {"type": "bool", "default": False},
                    "log_file": {"type": "str", "default": "/tmp/default.log"},
                },
            },
        }

        names = get_all_env_var_names(structure)
        assert names == {
            "SPA_TEMPERATURE",
            "SPA_ADVANCED__DEBUG",
            "SPA_ADVANCED__LOG_FILE",
        }

    def test_deeply_nested_structure(self):
        """Test with deeply nested structure."""
        structure = {
            "tools_react_agent": {
                "type": "group",
                "children": {"recursion_limit": {"type": "int", "default": 20}},
            }
        }

        names = get_all_env_var_names(structure)
        assert names == {"SPA_TOOLS_REACT_AGENT__RECURSION_LIMIT"}

    def test_custom_prefix(self):
        """Test with custom prefix."""
        structure = {"temperature": {"type": "float", "default": 0}}

        names = get_all_env_var_names(structure, prefix="CUSTOM")
        assert names == {"CUSTOM_TEMPERATURE"}


# Made with Bob
