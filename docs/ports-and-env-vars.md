# Service Ports, LLM Configurations and Environment Variable Overrides

This document lists the environment variables that can be used to configure the Skillberry Agent.

## LLM Provider Configuration

These environment variables configure the LLM provider used by the agent.

| Service Name              | Default value     | Environment Variables Override | Notes
|---------------------------|-------------------|--------------------------------|-----------------------------------------------------------------------------------|
| RITS service API key      | None              | RITS_API_KEY                   | To use IBM RITS service as LLM Provider (https://github.ibm.com/rits/rits/)       |
| Watsonx API key           | None              | WATSONX_API_KEY                | To use IBM WatsonX service as LLM Provider (https://www.ibm.com/products/watsonx) |
| Watsonx Project ID        | None              | WATSONX_PROJECT_ID             | To use IBM WatsonX service as LLM Provider (https://www.ibm.com/products/watsonx) |
| Watsonx URL               | None              | WATSONX_URL                    | To use IBM WatsonX service as LLM Provider (https://www.ibm.com/products/watsonx) |

> These values are mandatory to be set by setting the corresponding environment variables in your deployment configuration.

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

