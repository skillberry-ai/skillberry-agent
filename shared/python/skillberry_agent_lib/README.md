# Skillberry Agent Library

A comprehensive Python library for building AI agents with MCP (Model Context Protocol) integration, trajectory tracking, and Skillberry Tools Store connectivity.

## 🚀 Quick Start

### Installation

```bash
# Using pip
pip install skillberry-agent-lib

# Using poetry
poetry add skillberry-agent-lib
```

### Basic Usage

```python
from skillberry_agent_lib import (
    TrajectoryManager,
    SkillberryAPI,
    create_vmcp_server,
    SystemMessage,
    UserMessage,
)

# Initialize core components
trajectory_manager = TrajectoryManager()
api_client = SkillberryAPI(base_url="http://localhost:8000")

# Create a context for your agent
context = {"env_id": "my-agent-session-123"}

# Start building your agent!
```

## 📚 Table of Contents

- [Overview](#overview)
- [Building Your First Agent](#building-your-first-agent)
- [Core Components](#core-components)
- [Complete Agent Example](#complete-agent-example)
- [Advanced Topics](#advanced-topics)
- [Development](#development)

## 🎯 Overview

The Skillberry Agent Library provides essential building blocks for creating intelligent agents that can:

- **Track Reasoning Trajectories**: Record and manage agent decision-making steps
- **Integrate with MCP Servers**: Connect to Model Context Protocol servers for tool execution
- **Access Skillberry Tools**: Search and utilize tools from the Skillberry Tools Store
- **Handle Messages**: Work with structured message types (System, User, Assistant, Tool)
- **Build with LangGraph**: Leverage pre-built nodes and state definitions for agent graphs

### Key Features

✅ **Thread-Safe Operations** - Built for concurrent environments (FastAPI, multi-threaded apps)  
✅ **Type-Safe** - Full Pydantic models with type hints  
✅ **MCP Integration** - First-class support for Model Context Protocol  
✅ **Trajectory Management** - Track agent reasoning and tool usage  
✅ **LangGraph Ready** - Pre-built nodes and state definitions  
✅ **Flexible Context** - Environment-based context management  

## 🏗️ Building Your First Agent

Follow these 7 steps to build a production-ready agent:

### Step 1: Create or get VMCP server with unified skill resolution

```python
from skillberry_agent_lib import create_vmcp_server
from skillberry_agent_lib.data_model.virtual_mcp_server import VirtualMcpServer

# Define your agent's context
agent_context = {
    "env_id": "agent-session-001",
    "task_id": "task-123",
}

# Create VMCP server (handles skill resolution internally)
vmcp_data = create_vmcp_server(
    agent_context,
    skill_uuid=None,  # Direct UUID (highest priority)
    skill_name="weather-tool",  # Skill name (medium priority)
    skill_search_term=None,  # Search term (lowest priority)
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

# Run the agent

```python
llm = ChatOpenAI(model="gpt-4")
result = agent_app.invoke({
    "messages": [HumanMessage(content="Help me analyze this data")],
    "llm": llm,
})

print(f"Agent response: {result['messages'][-1].content}")
```

### Step 6: Retrieve and Analyze Trajectory

```python
# Get the full trajectory for analysis
trajectory = trajectory_manager.get_trajectory(agent_context)

print(f"\nAgent Trajectory ({len(trajectory)} steps):")
for msg in trajectory:
    print(f"Turn {msg.turn_idx}: {msg.role}")
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        for call in msg.tool_calls:
            print(f"  Tool: {call.name} - Args: {call.arguments}")
    if hasattr(msg, 'content') and msg.content:
        print(f"  Content: {msg.content[:100]}...")

# Clean up when done
remove_vmcp_server(agent_context)  # Removes from both registry and Tools Service
trajectory_manager.remove_trajectory(agent_context)
```

## 🧩 Core Components

### 1. Message Models

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
        )
    ],
)

# Tool result
tool_result = ToolMessage(
    role="tool",
    tool_call_id="call_abc",
    content="Temperature: 72°F, Sunny",
)
```

### 2. Trajectory Manager

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

### 3. Skillberry API Client

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

### 4. VMCP Server Manager

Manage Virtual MCP servers with unified skill resolution:

```python
from skillberry_agent_lib import (
    create_vmcp_server,
    list_vmcp_servers,
    remove_vmcp_server,
    clear_vmcp_servers,
)

context = {"env_id": "agent-001"}

# Create server (multiple resolution methods)
server1 = create_vmcp_server(
    skillberry_context=context,
    skill_uuid="uuid-123",  # Direct UUID (highest priority)
)

server2 = create_vmcp_server(
    skillberry_context=context,
    skill_name="weather-tool",  # By name (medium priority)
)

server3 = create_vmcp_server(
    skillberry_context=context,
    skill_search_term="weather",  # By search (lowest priority)
)

# List all servers
all_servers = list_vmcp_servers()

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

### 5. MCP Interceptor

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

### 6. LangGraph Integration

Pre-built components for LangGraph agents:

```python
from skillberry_agent_lib.langgraph_nodes import (
    ReactToolsCallingAgentState,
    parse_tool_call_from_content,
)
from langgraph.graph import StateGraph

# Use the pre-defined state
class MyAgentState(ReactToolsCallingAgentState):
    # Add custom fields if needed
    custom_data: str = ""

# Build your graph
graph = StateGraph(MyAgentState)

# Parse tool calls from content
tool_calls = parse_tool_call_from_content(
    '{"tool": "search", "args": {"query": "AI"}}'
)
```

## 💡 Complete Agent Example

Here's a full example of building an agent using the MCP tools method pattern:

```python
import asyncio
import logging
from skillberry_agent_lib import (
    TrajectoryManager,
    SkillberryAPI,
    create_vmcp_server,
    get_mcp_tools,
)
from skillberry_agent_lib.data_model.virtual_mcp_server import VirtualMcpServer
from skillberry_agent_lib.langgraph_nodes import create_react_tools_workflow
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# 1. Initialize components
trajectory_manager = TrajectoryManager()
api_client = SkillberryAPI(base_url="http://localhost:8000")
llm = ChatOpenAI(model="gpt-4")

# 2. Define agent context
agent_context = {
    "env_id": "weather-agent-001",
    "task_id": "get-weather-forecast",
}

# 3. Create chat prompt template
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful weather assistant with access to tools."),
    ("system", "If a tool returns an error, ask the user for clarification."),
    ("human", "{input}"),
])

# 4. Create VMCP server with unified skill resolution
try:
    vmcp_data = create_vmcp_server(
        skillberry_context=agent_context,
        skill_search_term="weather forecast",  # Can also use skill_uuid or skill_name
    )
    server = VirtualMcpServer(**vmcp_data)
    print(f"Created VMCP server: {server.name} on port {server.port} with tools: {server.tools}")
except ValueError as e:
    print(f"Failed to create VMCP server: {e}")
    exit(1)

# 5. Get MCP tools with automatic trajectory tracking
tools = get_mcp_tools(
    port=server.port,
    server_name=server.name,
    skillberry_context=agent_context,
)

print(f"Loaded {len(tools)} MCP tools with trajectory tracking")

# 6. Bind tools to LLM
if tools:
    llm_with_tools = llm.bind_tools(tools=tools, tool_choice="auto")
    print("Tools bound to LLM")
else:
    llm_with_tools = llm
    print("No tools available, using LLM without tools")

# 7. Create React workflow using the library's helper
workflow = create_react_tools_workflow(
    tools=tools,
    enable_tool_logging=False,
    normalize_anthropic_to_openai=True,
)

# 8. Compile the graph
graph = workflow.compile()

# 9. Prepare messages
chat_messages = chat_prompt.invoke({"input": "What's the weather in San Francisco?"})
llm_messages = chat_messages.to_messages()

# 10. Run the agent with streaming
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
try:
    final_message = asyncio.run(run_agent())
    print(f"\n✅ Final Response: {final_message.content}")
except Exception as e:
    print(f"❌ Error running agent: {e}")

# 11. Review trajectory
trajectory = trajectory_manager.get_trajectory(agent_context)
print(f"\n📊 Agent Trajectory ({len(trajectory)} steps):")
for i, msg in enumerate(trajectory, 1):
    print(f"\n  Step {i}: {msg.role}")
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        for call in msg.tool_calls:
            print(f"    Tool: {call.name}")
            print(f"    Args: {call.arguments}")
    if hasattr(msg, 'content') and msg.content:
        content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
        print(f"    Content: {content_preview}")

# 12. Cleanup - Remove VMCP server and trajectory
from skillberry_agent_lib import remove_vmcp_server

try:
    # Remove VMCP server (handles both local registry and Tools Service)
    removed = remove_vmcp_server(agent_context)
    if removed:
        print(f"\n🧹 Successfully removed VMCP server for context: {agent_context}")
    else:
        print(f"⚠️ VMCP server not found in local registry (may have been removed from Tools Service)")
    
    # Clean up trajectory
    trajectory_manager.remove_trajectory(agent_context)
    print(f"🧹 Cleaned up trajectory for context: {agent_context}")
    
except Exception as e:
    print(f"⚠️ Cleanup warning: {e}")

print("\n✨ Agent execution complete!")

# 9. Cleanup
trajectory_manager.remove_trajectory(agent_context)
```

## 🔧 Advanced Topics

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

## 🛠️ Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/skillberry/skillberry-agent-lib.git
cd skillberry-agent-lib

# Install with poetry
poetry install

# Or with pip in editable mode
pip install -e .
```

### Running Tests

```bash
# With poetry
poetry run pytest

# With pip
pytest
```

### Type Checking

```bash
# Run mypy
poetry run mypy skillberry_agent_lib
```

### Code Style

```bash
# Run flake8
poetry run flake8 skillberry_agent_lib
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
