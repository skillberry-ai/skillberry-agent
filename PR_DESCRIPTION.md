# Fix VirtualMcpServer validation and tool message format

## Problem
Two issues were causing errors in the MCP tools workflow:

1. **Pydantic validation error** when creating `VirtualMcpServer`:
   ```
   1 validation error for VirtualMcpServer
   tools
     Field required [type=missing]
   ```

2. **400 Bad Request** from lite-rits proxy:
   ```
   litellm.BadRequestError: OpenAIException - 1 validation error for Message
   content.0
     Input should be a valid dictionary or instance of Content
     [type=model_type, input_value=[{'text': '...', 'type': 'text'}]]
   ```

## Root Causes

1. **VirtualMcpServer model**: The `tools` field was required but API responses didn't include it
2. **Tool message format**: LangGraph's `ToolNode` produces content as `[{'text': '...', 'type': 'text'}]` but OpenAI API expects plain strings

## Solution

### 1. VirtualMcpServer Fix
**File:** `data_model/virtual_mcp_server.py`

Made `tools` field optional with default empty list:
```python
tools: List[str] = Field(default_factory=list, ...)
```

### 2. Tool Message Format Fix
**File:** `agents/mcp_tools.py`

Added async wrapper around `ToolNode` to convert list-format content to strings:
```python
async def convert_tool_messages_node(state):
    result = await original_tool_node.ainvoke(state)
    for msg in result.get("messages", []):
        if isinstance(msg.content, list):
            msg.content = msg.content[0]['text']
    return {"messages": messages}
```

## Testing
- ✅ VirtualMcpServer creation no longer fails
- ✅ 400 Bad Request errors resolved
- ⚠️ Note: 500 errors from RITS backend may still occur due to content structure issues (separate from this fix)

## Changes
- `data_model/virtual_mcp_server.py` - Made tools field optional
- `agents/mcp_tools.py` - Added tool message format conversion