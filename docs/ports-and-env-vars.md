# Service Ports, LLM Configurations and Environment Variable Overrides

This document lists the environment variables that can be used to configure the Skillberry Agent.

## LLM Provider Configuration

The agent uses the `llm-client` library which supports multiple LLM providers. Configure the provider using environment variables.

### Provider Selection

Set the provider name in your configuration (e.g., `litellm.rits.output_val`, `watsonx.output_val`). The provider determines which environment variables are required.

### Common Environment Variables

| Variable Name              | Default value | Required For | Description |
|----------------------------|---------------|--------------|-------------|
| RITS_API_KEY               | None          | RITS providers | API key for IBM RITS service (https://github.ibm.com/rits/rits/) |
| IBM_THIRD_PARTY_API_KEY    | None          | IBM providers | API key for IBM third-party services (fallback for RITS_API_KEY) |
| WATSONX_APIKEY             | None          | WatsonX providers | API key for IBM WatsonX service (https://www.ibm.com/products/watsonx) |
| WATSONX_PROJECT_ID         | None          | WatsonX providers | Project ID for IBM WatsonX service |
| WATSONX_URL                | None          | WatsonX providers | Endpoint URL for IBM WatsonX service |

### Provider-Specific Environment Variables

#### RITS Providers (`litellm.rits`, `litellm.rits.output_val`)
- **Required:** `RITS_API_KEY`
- **Optional:** `RITS_API_URL` - Custom RITS API endpoint

#### IBM LiteLLM Providers (`litellm.ibm`, `litellm.ibm.output_val`)
- **Required:** `IBM_THIRD_PARTY_API_KEY`
- **Optional:** `IBM_LITELLM_API_BASE` - Custom IBM LiteLLM endpoint

#### WatsonX Providers (`watsonx`, `watsonx.output_val`, `litellm.watsonx`, `litellm.watsonx.output_val`)
- **Required:** `WATSONX_APIKEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`

#### Ollama Providers (`litellm.ollama`, `litellm.ollama.output_val`)
- **Optional:** `OLLAMA_API_URL` - Ollama endpoint (default: `http://localhost:11434`)

#### OpenAI/Azure Providers (`openai.sync`, `azure.sync`, etc.)
- **Required:** Provider-specific API keys (e.g., `OPENAI_API_KEY`, `AZURE_OPENAI_API_KEY`)
- **Optional:** Custom endpoints via configuration

### Supported Providers

The following providers are available through llm-client:

| Provider Name | Description | Structured Output |
|---------------|-------------|-------------------|
| `litellm.rits` | RITS proxy via LiteLLM | No |
| `litellm.rits.output_val` | RITS proxy with validation | Yes |
| `litellm.ibm` | IBM third-party proxy | No |
| `litellm.ibm.output_val` | IBM proxy with validation | Yes |
| `litellm.ollama` | Ollama local models | No |
| `litellm.ollama.output_val` | Ollama with validation | Yes |
| `litellm.watsonx` | WatsonX via LiteLLM | No |
| `litellm.watsonx.output_val` | WatsonX via LiteLLM with validation | Yes |
| `watsonx` | Direct WatsonX | No |
| `watsonx.output_val` | Direct WatsonX with validation | Yes |
| `openai.sync` | OpenAI sync client | No |
| `openai.sync.output_val` | OpenAI with validation | Yes |
| `azure.sync` | Azure OpenAI sync | No |
| `azure.sync.output_val` | Azure OpenAI with validation | Yes |

**Note:** Providers with `.output_val` suffix support structured output validation with automatic retry on validation failures.

> Environment variables must be set in your deployment configuration. The agent will fail to start if required variables for the selected provider are missing.

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

