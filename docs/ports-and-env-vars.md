# Service Ports, LLM Configurations and Environment Variable Overrides

This document lists the environment variables that can be used to configure the Skillberry Agent.

## LLM Provider Configuration

The agent uses the [`llm-switchboard`](https://github.com/skillberry-ai/llm-switchboard) library which supports multiple LLM providers.

### Provider Selection

Set the provider name in your configuration (e.g., `openai.sync`). The provider determines which environment variables are required.

For detailed information about supported providers and their environment variables, see the [llm-switchboard documentation](https://github.com/skillberry-ai/llm-switchboard#providers).

**Notes:**
- Providers with `.output_val` suffix support structured output validation with automatic retry on validation failures.
- All provider-specific configuration is done via environment variables.
- The agent will fail to start if required variables for the selected provider are missing.
- Use the Configuration UI (port 7001) to set provider name and model name.

## Skill Configuration

These environment variables configure which skill the agent should use for task execution.

| Variable Name | Default value | Priority | Description |
|---------------|---------------|----------|-------------|
| SKILL_UUID    | None          | Highest  | Direct skill UUID. When set, this skill will be used without any lookup or resolution. |
| SKILL_NAME    | None          | Medium   | Skill name to resolve to UUID via API. Used when SKILL_UUID is not set. |

### Skill Resolution Strategy

The agent uses a three-tier strategy to resolve which skill to use:

1. **SKILL_UUID** (Highest Priority): If set, the agent uses this UUID directly without any validation or lookup.
   ```bash
   export SKILL_UUID="abc-123-def-456"
   ```

2. **SKILL_NAME** (Medium Priority): If SKILL_UUID is not set, the agent resolves the skill name to a UUID via the Skillberry API.
   ```bash
   export SKILL_NAME="airline_booking"
   ```

## Agent Tools and Prompts Configuration

These environment variables control agent tool and prompt behavior.

| Variable Name         | Default value | Type    | Description |
|----------------------|---------------|---------|-------------|
| USE_AGENT_TOOLS      | true          | boolean | When set to `true`, enables the use of tools provided in chat requests within the agentic workflow. When `false`, tools from requests are ignored. |
| USE_AGENT_PROMPTS    | true          | boolean | When set to `true`, preserves system messages (agent prompts) from chat requests. When `false`, system messages are filtered out before processing. |
| MCP_PROMPTS_POSITION | postfix       | string  | Controls where MCP prompts are injected relative to system messages. Accepted values: `prefix` or `postfix`. |

**Accepted Values:**
- Enable: `true`, `1`, `yes` (case-insensitive)
- Disable: `false`, `0`, `no` (case-insensitive)

**Note:** Agent prompts are system messages included in the chat request. When enabled, they are preserved according to `USE_AGENT_PROMPTS`. MCP prompts (from the skill server) are injected relative to these agent prompts based on `MCP_PROMPTS_POSITION].

## Debug and Logging Configuration

These environment variables control debug output and logging behavior.

| Variable Name      | Default value | Type    | Description |
|-------------------|---------------|---------|-------------|
| ENABLE_THINK_LOGS | false         | boolean | When set to `true`, includes thinking process logs in AI responses wrapped in `<think>` tags. Useful for debugging and understanding the agent's decision-making process. |

**Accepted Values:**
- Enable: `true`, `1`, `yes` (case-insensitive)
- Disable: `false`, `0`, `no`, or unset (case-insensitive)



## Configuration via Environment Variables

The Skillberry Proxy Agent supports comprehensive configuration through environment variables. All configuration attributes defined in `config/config_structure.py` can be overridden using environment variables.

### Environment Variable Naming Convention

Environment variables follow a consistent naming pattern:
- **Prefix:** `SPA_` (Skillberry Proxy Agent)
- **Nested attributes:** Use double underscore `__` to separate levels
- **Case:** UPPERCASE

**Examples:**
- `tools_service_base_url` → `SPA_TOOLS_SERVICE_BASE_URL`
- `advanced/debug` → `SPA_ADVANCED__DEBUG`
- `tools_react_agent/recursion_limit` → `SPA_TOOLS_REACT_AGENT__RECURSION_LIMIT`

### Configuration Priority

Configuration values are resolved in the following order (highest to lowest priority):

1. **System environment variables** - Set in your shell or deployment environment
2. **`.env` file** - Local configuration file (not committed to git)
3. **Config file** - `/tmp/tool-agent-config.json` or specified config file
4. **Code defaults** - Default values defined in `config_structure.py`

### Using .env Files

For local development, you can use a `.env` file to set environment variables:

1. Copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your values:
   ```bash
   SPA_PROVIDER_NAME=litellm.rits.output_val
   SPA_MODEL_NAME=openai/gpt-oss-120b
   SPA_ADVANCED__DEBUG=false
   ```

3. The `.env` file is automatically loaded on startup

**Important:**
- `.env` files are excluded from git (via `.gitignore`)
- System environment variables override `.env` file values
- Never commit `.env` files with secrets

### Automatic Configuration Discovery

When you add new attributes to `config_structure.py`, they automatically support environment variable configuration:

1. Add the attribute to `CONFIG_STRUCTURE` in `config/config_structure.py`
2. The corresponding environment variable name is automatically generated
3. No additional code changes needed

**Example:**
```python
# In config_structure.py
"new_feature": {
    "type": "group",
    "children": {
        "enabled": {"type": "bool", "default": False},
        "timeout": {"type": "int", "default": 30}
    }
}
```

Automatically supports:
- `SPA_NEW_FEATURE__ENABLED=true`
- `SPA_NEW_FEATURE__TIMEOUT=60`

### Type Conversion

Environment variables are automatically converted to the correct type:

- **Boolean:** `true`, `false`, `1`, `0`, `yes`, `no`, `on`, `off`, `enabled`, `disabled` (case-insensitive)
- **Integer:** Numeric strings (e.g., `"42"` → `42`)
- **Float:** Decimal strings (e.g., `"3.14"` → `3.14`)
- **String:** Used as-is
- **List:** Comma-separated values (e.g., `"a,b,c"` → `["a", "b", "c"]`)
- **Dict:** JSON strings (e.g., `'{"key": "value"}'`)

### Configuration UI Interaction

When using the Configuration UI:
- Changes made via UI take effect immediately in the current session
- Changes are saved to the config file
- On restart, environment variables override the config file again
- This allows temporary testing while maintaining env var control

For complete examples and all available configuration options, see `.env.example` in the project root.
