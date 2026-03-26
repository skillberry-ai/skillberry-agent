# Skillberry Proxy-Agent (SPA)

A proxy-agent service that orchestrates intelligent interactions between customer agents and the Skillberry ecosystem. The Skillberry Proxy-Agent acts as the central coordinator for LLM communication, skill resolution, and response optimization. Seamlessly integrates with Skillberry Store for dynamic tool discovery and execution through MCP protocols. Accessed via OpenAI-compatible endpoints (e.g., chat completions API) for seamless integration with existing AI applications.

## Features ✨

- **Proxy-Agent Orchestration**: Central coordinator managing interactions between customer agents and Skillberry Store
- **LLM Integration**: Seamless communication with language models via standardized API endpoints
- **Intelligent Skill Resolution**: Three-tier strategy (UUID → Name → Chat History) for automatic tool discovery
- **Skills Semantic Search**: Dynamic tool discovery through semantic search capabilities
- **MCP Tools Management**: Access and orchestration of relevant skills through MCP API tools and prompts
- **Response Optimization**: Enhanced and optimized responses before delivery to customer agents
- **Trajectory Tracking**: Complete audit trail of agent decisions and tool usage for continuous improvement
- **Automatic Drift Detection**: Monitors and identifies deviations in agent behavior patterns
- **VMCP Server Management**: Thread-safe virtual MCP server lifecycle per session
- **Reduce AI Systems TCO**: Offloading computational processes to CPU-based deterministic tools
- **Operational API**: OpenAI-compatible chat completion endpoints for seamless integration
- **Configuration Management**: Flexible configuration of tools store backend and LLM providers

## Quickstart 🚀

❗Ensure that the [skillberry-store](https://github.ibm.com/skillberry/skillberry-store) is running.

### Run the service with Docker or Podman 🐳

```bash
make docker_run
```

>*Note:* Use `make help` to view a list of additional available operations.

### Interact with the service API (via OpenAPI) 📜

Open a browser against `http://127.0.0.1:7000/docs`.

## Prerequisites 🛠️

- Export or use `.env` file to set `RITS_API_KEY` for accessing LLMs via RITS:

```bash
export RITS_API_KEY=********************************
```

- Alternatively, set `WATSONX_APIKEY`, `WATSONX_PROJECT_ID` and `WATSONX_URL` for accessing LLMs via WatsonX

```bash
export WATSONX_APIKEY=********************************
export WATSONX_PROJECT_ID=********************************
export WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

## Local Setup and Running the Service 🧰

```bash
cd ~
git clone git@github.ibm.com:skillberry/skillberry-agent.git
cd skillberry-agent
make run
```

### Interact with the configuration API 📜

Open a browser against `http://127.0.0.1:7001`.

## Configuration 🎛️

### Agent Behavior

Configure agent behavior using environment variables:

**Skill Selection** (choose one):
```bash
# Option 1: Direct skill UUID (highest priority)
export SKILL_UUID=abc-123-def-456

# Option 2: Skill name (resolves to UUID automatically)
export SKILL_NAME=weather-tool

# Option 3: Automatic discovery from conversation (fallback)
# No configuration needed - agent extracts from chat history
```

**Optional Settings**:
```bash
# Enable thinking logs in responses (useful for debugging)
export ENABLE_THINK_LOGS=true
```

### API Endpoints

| Endpoint | Purpose | Port |
|----------|---------|------|
| `/chat/completions` | OpenAI-compatible chat completion | 7000 |
| `/v1/chat/completions` | Alternative endpoint path | 7000 |
| `/prompt` | Simplified prompt endpoint | 7000 |
| Configuration API | Manage configurations | 7001 |

---

## 📚 Additional documentation can be found at [docs](docs).

* Library usage and API reference: [skillberry-agent-lib README](shared/python/skillberry_agent_lib/README.md)
* Port and environment variable details: [docs/ports-and-env-vars.md](docs/ports-and-env-vars.md)
