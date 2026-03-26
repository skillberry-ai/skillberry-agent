# Skillberry Agent Library

A Python library for integrating AI agents with the Skillberry ecosystem, providing access to the Skillberry Tools Store, trajectory tracking, and agent orchestration capabilities powered by MCP.

## 🚀 Quick Start

### Installation

```bash
# Using pip
pip install skillberry-agent-lib
```

### Importing a Skill to the Store

Before running agents, you need to import a skill into the Skillberry Store. This library includes an example calculator skill in `contrib/examples/skills/calculate/`.

**Import the calculator skill:**

```bash
# Make sure Skillberry Store is running on http://localhost:8000
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

Here's a trivial but complete agent that demonstrates the full integration:

**Prerequisites:**
- Skillberry Tools Store running (default: `http://localhost:8000`)
- LLM API credentials configured
- A skill available in the Skillberry Store (e.g., 'calculator') - [see how to import a skill](#importing-a-skill-to-the-store)

```python
import asyncio
import os
import logging
from skillberry_agent_lib import (
    resolve_skill_uuid,
    get_or_create_vmcp_server,
    get_mcp_tools,
    TrajectoryManager,
    remove_vmcp_server,
)
from skillberry_agent_lib.data_model.virtual_mcp_server import VirtualMcpServer
from skillberry_agent_lib.langgraph_nodes import create_react_tools_workflow
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Enable logging to see shared lib component logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_simple_agent():
    # 1. Setup
    context = {"env_id": "simple-agent-001"}
    trajectory_manager = TrajectoryManager()
    
    # Initialize LLM (using OpenAI as example)
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("OPENAI_API_KEY environment variable not set")
        return
    
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.0,
        max_retries=2,
        api_key=openai_api_key,
    )
    
    # 2. Configure skill from Skillberry Store
    os.environ['SKILL_NAME'] = 'calculator'
    skill_uuid = resolve_skill_uuid(
        skill_uuid=os.environ.get('SKILL_UUID'),
        skill_name=os.environ.get('SKILL_NAME'),
        chat_history=[]
    )
    
    if not skill_uuid:
        print("Failed to resolve skill UUID")
        return
    
    # 3. Create VMCP server and get tools
    vmcp_data = get_or_create_vmcp_server(context, skill_uuid=skill_uuid)
    server = VirtualMcpServer(**vmcp_data)
    tools = get_mcp_tools(server.port, server.name, context)
    
    print(f"Loaded {len(tools)} tools from Skillberry Store")
    
    # 4. Build and run agent with logging enabled
    llm_with_tools = llm.bind_tools(tools) if tools else llm
    workflow = create_react_tools_workflow(
        tools=tools,
        enable_tool_logging=True,  # Enable detailed tool execution logs
        tool_logger=logger,         # Pass logger for debugging
        normalize_anthropic_to_openai=True,  # Normalize message format for compatibility
    )
    graph = workflow.compile()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. Always try to use available tools to answer user questions when applicable."),
        ("human", "{input}"),
    ])
    messages = prompt.invoke({"input": "Calculate the result of this mathematical expression: 25 * 4"})
    
    # 5. Execute and get result
    final_message = None
    async for state in graph.astream(
        {"messages": messages.to_messages(), "llm": llm_with_tools},
        stream_mode="values"
    ):
        final_message = state["messages"][-1]
    
    # 6. Review trajectory and cleanup
    trajectory = trajectory_manager.get_trajectory(context)
    print(f"\nAgent completed with {len(trajectory)} steps")
    if final_message:
        print(f"Result: {final_message.content}")
    
    remove_vmcp_server(context)
    trajectory_manager.remove_trajectory(context)

# Run the agent
if __name__ == "__main__":
    asyncio.run(run_simple_agent())
```

This example shows the complete flow: **Skillberry Store** → resolve skill → create VMCP server → get tools → build agent with logging → execute → cleanup.

**Key features demonstrated:**
- Skillberry Tools Store integration
- LLM configuration
- Tool logging for debugging (`enable_tool_logging=True`)
- Trajectory tracking
- Proper cleanup

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
- **MCP Integration** - Powered by Model Context Protocol for tool execution

## Building Your First Agent

Follow these 7 steps to build a production-ready agent:

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
from langchain_openai import ChatOpenAI

# Initialize LLM
llm = ChatOpenAI(model="gpt-4")

# Bind tools to LLM
if tools:
    llm_with_tools = llm.bind_tools(tools=tools, tool_choice="auto")
    print("Tools bound to LLM")
else:
    llm_with_tools = llm
    print("No tools available, using LLM without tools")
```

### Step 4: Create and compile the React workflow

```python
from skillberry_agent_lib.langgraph_nodes import create_react_tools_workflow

# Create workflow using the library's helper
workflow = create_react_tools_workflow(
    tools=tools,
    enable_tool_logging=False,
    normalize_anthropic_to_openai=True,
)

# Compile the graph
graph = workflow.compile()
```

### Step 5: Prepare chat messages

```python
from langchain_core.prompts import ChatPromptTemplate

# Create chat prompt template
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant with access to tools."),
    ("human", "{input}"),
])

# Prepare messages
chat_messages = chat_prompt.invoke({"input": "What's the weather in San Francisco?"})
llm_messages = chat_messages.to_messages()
```

### Step 6: Invoke the graph and stream results

```python
import asyncio

# Run the agent with streaming
async def run_agent():
    """Run the agent and stream results"""
    final_message = None
    
    async for state in graph.astream(
        {
            "messages": llm_messages,
            "llm": llm_with_tools,
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

### Step 7: Build final response

```python
from skillberry_agent_lib import TrajectoryManager, remove_vmcp_server

# Initialize trajectory manager
trajectory_manager = TrajectoryManager()

# Get the trajectory
trajectory = trajectory_manager.get_trajectory(agent_context)
print(f"\n📊 Agent Trajectory ({len(trajectory)} steps):")
for i, msg in enumerate(trajectory, 1):
    print(f"  Step {i}: {msg.role}")
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        for call in msg.tool_calls:
            print(f"    Tool: {call.name}")

# Cleanup when done
remove_vmcp_server(agent_context)  # Removes from both registry and Tools Service
trajectory_manager.remove_trajectory(agent_context)
print("\n✨ Agent execution complete!")
```

## Core Components

| Component | Purpose | Key Function |
|-----------|---------|--------------|
| **Skill Manager** | Resolve skill UUIDs | `resolve_skill_uuid()` |
| **VMCP Server Manager** | Manage virtual MCP servers | `get_or_create_vmcp_server()` |
| **MCP Interceptor** | Track tool calls | `get_mcp_tools()` |
| **Trajectory Manager** | Track agent reasoning | `TrajectoryManager` |
| **LangGraph Nodes** | Build React workflows | `create_react_tools_workflow()` |
| **Message Models** | Structured messages | `SystemMessage`, `UserMessage`, etc. |
| **Skillberry API** | Tools Store client | `SkillberryAPI` |

### 1. Skill Manager

Centralized skill resolution with multiple strategies:

```python
from skillberry_agent_lib import resolve_skill_uuid
import os

# Set environment variables for skill configuration
os.environ['SKILL_UUID'] = 'abc-123-def-456'  # Highest priority
# Or: os.environ['SKILL_NAME'] = 'weather-tool'  # Medium priority

# Resolve skill UUID using multiple strategies
chat_history = []  # Your chat messages
resolved_uuid = resolve_skill_uuid(
    skill_uuid=os.environ.get('SKILL_UUID'),
    skill_name=os.environ.get('SKILL_NAME'),
    chat_history=chat_history
)

print(f"Resolved skill UUID: {resolved_uuid}")
```

**Resolution Strategy (Priority Order):**
1. **SKILL_UUID** env var - Direct UUID (highest priority)
2. **SKILL_NAME** env var - Resolves name to UUID via API (medium priority)
3. **Chat History** - Extracts search term and finds matching skill (lowest priority)

**Key Features:**
- Environment variable-based configuration
- Three-tier fallback strategy
- Automatic skill discovery from conversation context
- Graceful degradation when resolution fails

### 2. Message Models

Structured message types for agent communication:

```python
from skillberry_agent_lib import (
    SystemMessage,
    UserMessage,
    AssistantMessage,
    ToolMessage,
    ToolCall,
)

# System message
system = SystemMessage(
    role="system",
    content="You are an expert assistant.",
)

# User message
user = UserMessage(
    role="user",
    content="What's the weather?",
)

# Assistant with tool call
assistant = AssistantMessage(
    role="assistant",
    tool_calls=[
        ToolCall(
            id="call_abc",
            name="get_weather",
            arguments={"location": "New York"},
            requestor="assistant",  # Tracks who requested the tool
        )
    ],
)

# Tool result
tool_result = ToolMessage(
    role="tool",
    id="call_abc",
    content="Temperature: 72°F, Sunny",
    requestor="assistant",  # Matches the tool call requestor
)
```

**ToolCall Features:**
- `id`: Unique identifier for the tool call
- `name`: Tool name to execute
- `arguments`: Tool parameters as a dictionary
- `requestor`: Tracks whether "user" or "assistant" initiated the call

**Message Validation:**
- Messages automatically validate that they have either `content` or `tool_calls`
- Invalid messages log errors and add placeholder content to prevent downstream issues
- All messages support optional `cost`, `usage`, and `raw_data` fields for tracking

**MultiToolMessage:**
For handling multiple tool responses in a single message:

```python
from skillberry_agent_lib.data_model.messages import MultiToolMessage, ToolMessage

multi_tool = MultiToolMessage(
    role="tool",
    tool_messages=[
        ToolMessage(id="call_1", content="Result 1", requestor="assistant"),
        ToolMessage(id="call_2", content="Result 2", requestor="assistant"),
    ]
)
```

### 3. Trajectory Manager

Thread-safe trajectory tracking for agent reasoning:

```python
from skillberry_agent_lib import TrajectoryManager

manager = TrajectoryManager()

# Add messages to trajectory
context = {"env_id": "session-123"}
manager.add_message(context, assistant_message)
manager.add_message(context, tool_message)

# Retrieve trajectory
trajectory = manager.get_trajectory(context)

# Clean up when done
manager.remove_trajectory(context)
```

**Key Features:**
- Thread-safe operations with locks
- Per-environment trajectory storage
- Automatic trajectory creation
- Copy-on-read to prevent external modification

### 4. Skillberry API Client

Interface to the Skillberry Tools Store:

```python
from skillberry_agent_lib import SkillberryAPI
api = SkillberryAPI(base_url="http://localhost:8000")


# Check connectivity
if api.check_communication():
    print("Connected to Skillberry Store")

# Search for skills
results = api.search_skills(
    search_term="weather",
    max_number_of_results=10,
    similarity_threshold=0.8,
)

for skill in results:
    print(f"Skill: {skill['name']}")
    print(f"UUID: {skill['uuid']}")
```

### 5. VMCP Server Manager

Manage Virtual MCP servers with pre-resolved skill UUIDs:

```python
import os
from skillberry_agent_lib import (
    resolve_skill_uuid,
    get_or_create_vmcp_server,
    remove_vmcp_server,
    clear_vmcp_servers,
)

context = {"env_id": "agent-001"}

# Set skill via environment variable
os.environ['SKILL_UUID'] = 'uuid-123'

# Resolve skill UUID
chat_history = []
resolved_uuid = resolve_skill_uuid(
    skill_uuid=os.environ.get('SKILL_UUID'),
    skill_name=os.environ.get('SKILL_NAME'),
    chat_history=chat_history
)

# Create server with resolved UUID
server = get_or_create_vmcp_server(
    skillberry_context=context,
    skill_uuid=resolved_uuid,
)

# Remove specific server (removes from both local registry and Tools Service)
# Returns True if removed from registry, False if not found
removed = remove_vmcp_server(context)

# Clear all servers (only clears local registry)
clear_vmcp_servers()
```

**Thread Safety:**
- Registry protected by locks
- Placeholder mechanism prevents race conditions
- Safe for concurrent FastAPI requests

**Cleanup Behavior:**
- `remove_vmcp_server(context)` removes from both local registry AND Skillberry Tools Service
- `clear_vmcp_servers()` only clears local registry (use for testing/cleanup)

### 6. MCP Interceptor

Intercept and track MCP tool calls:

```python
from skillberry_agent_lib import create_tool_interceptor, get_mcp_tools

context = {"env_id": "agent-001"}

# Create interceptor
interceptor = create_tool_interceptor(context)

# Get tools with automatic trajectory tracking
tools = get_mcp_tools(
    skillberry_context=context,
    skill_name="data-processor",
)

# Tools now automatically log to trajectory when called
```

**What it does:**
- Extracts tool requests into AssistantMessage
- Converts tool results into ToolMessage
- Automatically adds to trajectory
- Generates unique tool_call_id

### 7. LangGraph Integration

Pre-built components for LangGraph agents:

```python
import asyncio
from skillberry_agent_lib.langgraph_nodes import (
    create_react_tools_workflow,
    ReactToolsCallingAgentState,
)
from langchain_core.prompts import ChatPromptTemplate

# Create workflow with factory function
workflow = create_react_tools_workflow(
    tools=tools,
    normalize_anthropic_to_openai=True,
)
graph = workflow.compile()

# Prepare messages
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant."),
    ("human", "{input}"),
])
messages = prompt.invoke({"input": "What's the weather?"})

# Invoke the graph
async def run_agent():
    final_message = None
    async for state in graph.astream(
        {
            "messages": messages.to_messages(),
            "llm": llm_with_tools
        },
        {
            "recursion_limit": 50,
            "max_execution_time": 120
        },
        stream_mode="values",
    ):
        final_message = state["messages"][-1]
    return final_message

result = asyncio.run(run_agent())
print(f"Response: {result.content}")
```
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
git clone https://github.ibm.com/skillberry/skillberry-agent.git
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

### Type Checking

```bash
mypy skillberry_agent_lib
```

### Code Style

```bash
flake8 skillberry_agent_lib
```

## 📋 Requirements

- Python >= 3.8
- pydantic >= 2.11.3
- requests >= 2.32.3
- typing-extensions >= 4.13.2
- langchain >= 0.3.25
- langchain-core >= 0.3.59
- langgraph >= 0.4.3
- langchain-mcp-adapters >= 0.2.1
