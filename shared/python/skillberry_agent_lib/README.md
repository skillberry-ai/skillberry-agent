# Skillberry Agent Library

A Python library for integrating AI agents with the Skillberry ecosystem, providing access to the Skillberry Tools Store, trajectory tracking, and agent orchestration capabilities powered by MCP.

## 🚀 Quick Start

### Installation

```bash
pip install -e .
```

### Importing a Skill to the Store

Before running agents, you need to import a skill into the Skillberry Store. This library includes an example calculator skill in `contrib/examples/skills/calculate/`.

**Import the calculator skill:**

```bash
# Make sure Skillberry Store is running on http://localhost:8000
# Run from the skillberry_agent_lib directory
cd shared/python/skillberry_agent_lib
curl -X POST http://localhost:8000/skills/import-anthropic \
  -F "source_type=folder" \
  -F "folder_path=$(pwd)/contrib/examples/skills/calculate" \
  -F "snippet_mode=file"
```

**Verify the import:**

```bash
# Get the calculator skill details
curl -s "http://localhost:8000/skills/calculate" | python -m json.tool
```

Once imported, the skill will be available for use in your agents.


### Complete Minimal Example

For a complete, working end-to-end example, see:

**[`contrib/examples/minimal_agent.py`](contrib/examples/minimal_agent.py)**

This script demonstrates all 8 steps to build a production-ready agent:
1. Resolve skill and create VMCP server
2. Get tools from MCP server
3. Initialize and bind LLM with tools
4. Create and compile React workflow
5. Build chat messages with MCP prompts injection
6. Invoke graph with configuration
7. Handle final response
8. Cleanup with error handling

**Prerequisites:**
- [Skillberry Tools Store](https://github.com/skillberry-ai/skillberry-store) running (default: `http://localhost:8000`)
- LLM API credentials configured via [llm-switchboard](https://github.com/skillberry-ai/llm-switchboard) (e.g., `OPENAI_API_KEY`)
- A skill available in the Skillberry Store (e.g., 'calculator') - [see how to import a skill](#importing-a-skill-to-the-store)

**Run the example:**
```bash
cd shared/python/skillberry_agent_lib
python contrib/examples/minimal_agent.py
```

The example includes:
- Complete LLM initialization using [llm-switchboard](https://github.com/skillberry-ai/llm-switchboard)
- MCP prompts injection for skill-specific instructions
- Tool logging for debugging
- Trajectory tracking
- Proper error handling and cleanup

## 📚 Table of Contents

- [Overview](#overview)
- [Building Your First Agent](#building-your-first-agent)
- [Core Components](#core-components)
- [Complete Agent Example](#complete-minimal-example)
- [Advanced Topics](#advanced-topics)
- [Development](#development)

## Overview

The Skillberry Agent Library provides essential building blocks for creating intelligent agents that can:

- **Access Skillberry Tools**: Search and utilize tools from the Skillberry Tools Store
- **Track Reasoning Trajectories**: Record and manage agent decision-making steps
- **Build with LangGraph**: Leverage pre-built nodes and state definitions for agent graphs
- **Handle Messages**: Work with structured message types (System, User, Assistant, Tool)
- **Integrate with MCP Servers**: Connect to Model Context Protocol servers for tool execution

### Key Features ✨

- **Skillberry Tools Store Integration** - Direct access to the Skillberry ecosystem
- **Trajectory Management** - Track agent reasoning and tool usage
- **LangGraph Ready** - Pre-built nodes and state definitions
- **Thread-Safe Operations** - Built for concurrent environments (FastAPI, multi-threaded apps)
- **Type-Safe** - Full Pydantic models with type hints
- **Flexible Context** - Environment-based context management
- **MCP Integration** - Powered by Model Context Protocol for tool execution (MCP tools) and contextual instructions (MCP prompts)

## Building Your First Agent

Follow these 8 steps to build a production-ready agent:

### Step 1: Resolve skill and create VMCP server

```python
import os
from skillberry_agent_lib import resolve_skill_uuid, get_or_create_vmcp_server
from skillberry_agent_lib.data_model.virtual_mcp_server import VirtualMcpServer

# Define your agent's context
agent_context = {
    "env_id": "agent-session-001",
    "task_id": "task-123",
}

# Set skill configuration via environment variables (recommended)
os.environ['SKILL_NAME'] = 'weather-tool'
# Or use: os.environ['SKILL_UUID'] = 'your-skill-uuid'

# Resolve skill UUID using the configured environment variables
# You can also pass chat_history for automatic discovery
chat_history = []  # Your chat messages
resolved_uuid = resolve_skill_uuid(
    skill_uuid=os.environ.get('SKILL_UUID'),
    skill_name=os.environ.get('SKILL_NAME'),
    chat_history=chat_history
)

# Create VMCP server with resolved skill UUID
vmcp_data = get_or_create_vmcp_server(
    agent_context,
    skill_uuid=resolved_uuid,
)

# Create VirtualMcpServer instance
server = VirtualMcpServer(**vmcp_data)
port = server.port

print(f"Created VMCP server: {server.name} on port {port} with {len(server.tools)} tools")
```

### Step 2: Get tools from the MCP server with interceptor

```python
from skillberry_agent_lib import get_mcp_tools

# Get tools with automatic trajectory tracking
tools = get_mcp_tools(
    port=port,
    server_name=server.name,
    skillberry_context=agent_context,
)

print(f"Loaded {len(tools)} MCP tools")
```

### Step 3: Bind tools to LLM

```python
# Assuming you have an LLM instance that's already LangChain-compatible
# (e.g., from your application's LLM initialization)
# For LLM setup examples, see the Complete Minimal Example section

# Bind tools to LLM
if tools:
    llm_with_tools = llm.bind_tools(tools=tools, tool_choice="auto")
    print("Tools bound to LLM")
else:
    llm_with_tools = llm
    print("No tools available, using LLM without tools")
```

**Note:** For LLM initialization patterns using `llm-switchboard`, see the [Complete Minimal Example](#complete-minimal-example) which shows how to create a LangChain-compatible LLM adapter.

### Step 4: Create and compile the React workflow

```python
from skillberry_agent_lib.langgraph_nodes import create_react_tools_workflow
import logging

# Optional: Set up logging for tool execution debugging
logger = logging.getLogger(__name__)

# Create workflow using the library's helper
workflow = create_react_tools_workflow(
    tools=tools,
    enable_tool_logging=True,              # Enable detailed tool execution logs
    tool_logger=logger,                    # Pass logger for debugging
    normalize_anthropic_to_openai=False,   # Set to True only if using Anthropic provider
)

# Compile the graph
graph = workflow.compile()
```

**Parameters:**
- `tools`: List of LangChain tools from MCP server
- `enable_tool_logging`: Set to `True` to see detailed tool execution logs (useful for debugging)
- `tool_logger`: Logger instance for tool execution logs
- `normalize_anthropic_to_openai`: Set to `True` to convert Anthropic's list-based content format to OpenAI's string format

### Step 5: Build chat messages with MCP prompts injection

MCP prompts are skill-specific instructions that guide the agent's behavior. The `build_chat_messages()` function automatically injects these prompts from the MCP server into your chat history.

```python
from skillberry_agent_lib import build_chat_messages

# Prepare your chat history (can include system messages, user messages, etc.)
chat_history = [
    {"role": "user", "content": "What's the weather in San Francisco?"}
]

# Build messages with MCP prompts injection
# This automatically adds skill-specific instructions to system messages
llm_messages = build_chat_messages(
    chat_history=chat_history,
    mcp_port=port,
    mcp_server_name=server.name,
    skillberry_context=agent_context,
    mcp_prompts_position='postfix'  # 'prefix' or 'postfix' - where to inject MCP prompts
)

print(f"Prepared {len(llm_messages)} messages for the agent")
```

**MCP Prompts Position:**
- `'prefix'`: Inject MCP prompts BEFORE your system messages (MCP instructions take precedence)
- `'postfix'`: Inject MCP prompts AFTER your system messages (your instructions take precedence)
- Default: `'postfix'`

**Why This Matters:**
MCP prompts contain domain-specific knowledge and instructions from the skill. Without this step, your agent won't have the contextual information needed to use tools effectively.

### Step 6: Invoke the graph with configuration

```python
import asyncio

async def run_agent():
    """Run the agent with proper configuration"""
    final_message = None
    
    async for state in graph.astream(
        {
            "messages": llm_messages,
            "llm": llm_with_tools,
        },
        {
            "recursion_limit": 20,        # Maximum iterations for the agent
            "max_execution_time": 120     # Timeout in seconds
        },
        stream_mode="values",
    ):
        message = state["messages"][-1]
        print(f"Step: {message.type}")
        final_message = message
    
    return final_message

# Execute the agent
final_message = asyncio.run(run_agent())
print(f"\n✅ Final Response: {final_message.content}")
```

**Configuration Parameters:**
- `recursion_limit`: Maximum number of iterations the agent can perform (default: 20)
- `max_execution_time`: Maximum execution time in seconds (default: 120)
- `stream_mode`: Set to `"values"` to stream state updates

### Step 7: Handle final response

The final message may contain either text content or tool calls that need to be executed by your application.

```python
# Check if the response contains tool calls
if hasattr(final_message, 'tool_calls') and final_message.tool_calls:
    print(f"Agent returned {len(final_message.tool_calls)} tool calls")
    for tool_call in final_message.tool_calls:
        print(f"  Tool: {tool_call.get('name')}")
        print(f"  Args: {tool_call.get('args')}")
    # Return the AIMessage object to preserve tool_calls
    response = final_message
else:
    # No tool calls - extract text content
    response = final_message.content
    print(f"Agent response: {response}")
```

**Note:** Tools are executed automatically by the workflow. The final response will contain either text content or tool calls that were made during execution.

### Step 8: Cleanup with error handling

Always clean up resources when done, with proper error handling for production use.

```python
from skillberry_agent_lib import TrajectoryManager, remove_vmcp_server

# Initialize trajectory manager
trajectory_manager = TrajectoryManager()

# Get the trajectory (optional - for debugging/logging)
try:
    trajectory = trajectory_manager.get_trajectory(agent_context)
    print(f"\n📊 Agent Trajectory ({len(trajectory)} steps):")
    for i, msg in enumerate(trajectory, 1):
        print(f"  Step {i}: {msg.role}")
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for call in msg.tool_calls:
                print(f"    Tool: {call.name}")
except Exception as e:
    print(f"Warning: Failed to retrieve trajectory: {e}")

# Cleanup VMCP server (removes from both local registry and Tools Service)
try:
    removed = remove_vmcp_server(agent_context)
    if removed:
        print("✅ VMCP server removed successfully")
    else:
        print("⚠️ VMCP server not found (may have been already removed)")
except Exception as e:
    print(f"⚠️ Failed to remove VMCP server: {e}")

# Cleanup trajectory
try:
    trajectory_manager.remove_trajectory(agent_context)
    print("✅ Trajectory cleaned up")
except Exception as e:
    print(f"⚠️ Failed to clean up trajectory: {e}")

print("\n✨ Agent execution complete!")
```

**Best Practice:** Always use try-except blocks for cleanup operations in production code. This ensures your application continues running even if cleanup fails.

## API Reference

For detailed API documentation, see the complete working example in [`contrib/examples/minimal_agent.py`](contrib/examples/minimal_agent.py) which demonstrates all components in action.

**Quick Reference:**

| Component | Purpose | Key Function |
|-----------|---------|--------------|
| **Skill Manager** | Resolve skill UUIDs | `resolve_skill_uuid()` |
| **VMCP Server Manager** | Manage virtual MCP servers | `get_or_create_vmcp_server()` |
| **MCP Interceptor** | Track tool calls | `get_mcp_tools()` |
| **Prompt Manager** | Build messages with MCP prompts | `build_chat_messages()` |
| **Trajectory Manager** | Track agent reasoning | `TrajectoryManager` |
| **LangGraph Nodes** | Build React workflows | `create_react_tools_workflow()` |
| **Message Models** | Structured messages | `SystemMessage`, `UserMessage`, etc. |
| **Skillberry Store** | Tools Store client | `SkillberryStore` |

## Advanced Topics

| Topic | Description |
|-------|-------------|
| [Thread Safety](#thread-safety) | Concurrent agent execution |
| [Context Management](#context-management) | Best practices for contexts |
| [Think Logs](#think-logs-feature) | Enable agent reasoning visibility |
| [Anthropic Normalization](#anthropic-content-normalization) | Handle Anthropic content format |

### Thread Safety

All core components are thread-safe:

```python
import threading
from skillberry_agent_lib import TrajectoryManager

manager = TrajectoryManager()

def agent_task(agent_id):
    context = {"env_id": f"agent-{agent_id}"}
    # Safe to use concurrently
    manager.add_message(context, message)

# Run multiple agents concurrently
threads = [
    threading.Thread(target=agent_task, args=(i,))
    for i in range(10)
]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

### Context Management

Best practices for managing agent contexts:

```python
from datetime import datetime
from skillberry_agent_lib import TrajectoryManager, remove_vmcp_server

trajectory_manager = TrajectoryManager()

# Use descriptive env_ids
context = {
    "env_id": f"user-{user_id}-session-{session_id}",
    "task_id": task_id,
    "metadata": {
        "user_name": user_name,
        "timestamp": datetime.now().isoformat(),
    }
}

# Clean up when done
try:
    # ... agent execution ...
    pass
finally:
    trajectory_manager.remove_trajectory(context)
    remove_vmcp_server(context)
```

### Think Logs Feature

Enable thinking logs to see agent reasoning:

```python
import os

# Enable think logs in responses
os.environ['ENABLE_THINK_LOGS'] = 'true'

# Response will include <think>...</think> tags with reasoning
```

**Use Cases**:
- Debugging agent decision-making
- Understanding tool selection logic
- Monitoring agent behavior in production

### Anthropic Content Normalization

Handle Anthropic's list-based content format:

```python
from skillberry_agent_lib.langgraph_nodes import create_react_tools_workflow

workflow = create_react_tools_workflow(
    tools=tools,
    normalize_anthropic_to_openai=True,  # Enable normalization
)
```

**What it does**:
- Converts `[{'text': 'Hello', 'type': 'text'}]` → `"Hello"`
- Ensures compatibility with OpenAI-style message handling
- Automatically applied before LLM invocation

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/skillberry-ai/skillberry-agent.git
cd skillberry-agent/shared/python/skillberry_agent_lib

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the library in editable mode
pip install -e .

# Install development dependencies
pip install pytest pytest-cov mypy flake8
```

### Verify Installation

```bash
# Test that the library imports correctly
python -c "import skillberry_agent_lib; print('Import successful')"
```

### Running Tests

```bash
pytest
```


