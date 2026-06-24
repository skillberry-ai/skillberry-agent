"""
Shared LangGraph nodes and utilities for MCP-based agents.

This module contains common LangGraph node implementations and state definitions
used by both the skillberry-agent and tau2-bench agents.
"""

import json
import logging
import re
from typing import (
    Any,
    Annotated,
    Dict,
    List,
    Optional,
    Sequence,
    TypedDict,
)

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


logger = logging.getLogger(__name__)


class ReactToolsCallingAgentState(TypedDict):
    """State definition for React-style tool-calling agents."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    llm: LanguageModelInput


def parse_tool_call_from_content(content: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse tool call information from message content.
    
    Extracts JSON-formatted tool calls from text content and normalizes them
    to a standard format. Supports multiple field name variations for backward
    compatibility.
    
    Args:
        content: The message content to parse
        
    Returns:
        List of tool call dictionaries, or None if no valid tool call found
    """
    match = re.search(r"\{.*\}", content)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        
        # Support multiple field name variations for backward compatibility
        # Try "parameters" first (OpenAI standard), then "arguments" (common alternative)
        args = parsed.get("parameters")
        if args is None:
            args = parsed.get("arguments", {})
        
        # Support both "name" and "function" fields for tool name
        name = parsed.get("name")
        if not name:
            name = parsed.get("function", "")
        
        # Validate that we have a non-empty function name
        if not name:
            logger.warning(f"parse_tool_call_from_content: no valid function name found in parsed content: {parsed}")
            return None
        
        return [
            {
                "type": parsed.get("type", "function"),
                "name": name,
                "args": args,
                "id": parsed.get("id", "0"),
            }
        ]
    except json.JSONDecodeError as e:
        logger.error(f"parse_tool_call_from_content: json.JSONDecodeError: {e}")
        return None


def normalize_anthropic_content_to_openai(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    Convert Anthropic-style message content to OpenAI-compatible format.
    
    Anthropic's API returns message content as a list of content blocks:
        [{'text': 'Hello world', 'type': 'text'}, ...]
    
    OpenAI's API expects simple string content:
        "Hello world"
    
    This function transforms Anthropic-style list-based content into OpenAI-compatible
    string content by extracting and joining all text blocks.
    
    Args:
        messages: List of LangChain BaseMessage objects to normalize
        
    Returns:
        List of normalized messages with string content instead of list content
        
    Example:
        >>> from langchain_core.messages import HumanMessage
        >>> msg = HumanMessage(content=[{'text': 'Hello', 'type': 'text'}])
        >>> normalized = normalize_anthropic_content_to_openai([msg])
        >>> normalized[0].content
        'Hello'
    """
    normalized = []
    for msg in messages:
        if hasattr(msg, 'content') and isinstance(msg.content, list):
            # Extract text from [{'text': '...', 'type': 'text'}] format
            text_parts = []
            for item in msg.content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text_parts.append(item.get('text', ''))
            # Create new message with string content
            if hasattr(msg, 'model_copy'):
                # Pydantic v2
                normalized_msg = msg.model_copy(update={'content': ' '.join(text_parts)})
            elif hasattr(msg, 'copy'):
                # Pydantic v1
                normalized_msg = msg.copy(update={'content': ' '.join(text_parts)})
            else:
                # Fallback: create new message of same type
                normalized_msg = type(msg)(content=' '.join(text_parts), **{k: v for k, v in msg.__dict__.items() if k != 'content'})
            normalized.append(normalized_msg)
        else:
            normalized.append(msg)
    return normalized


def normalize_tool_node(state: ReactToolsCallingAgentState) -> Dict[str, Any]:
    """
    Normalize tool calls in the last message of the state.
    
    This node performs two normalization tasks:
    1. If tool_calls are missing: Attempts to parse tool calls from message content
       (handles cases where LLMs return tool calls as text instead of structured data)
    2. If tool_calls are present: Clears the content field to avoid redundant JSON
       (tool call information is already in the structured tool_calls field)
    
    Args:
        state: The current agent state
        
    Returns:
        Dictionary with updated messages and thinking_log
    """
    thinking_log = ""
    if not state or "messages" not in state or not state["messages"]:
        thinking_log += "empty state nothing to normalize. "
        logger.info("normalize_tool_node: empty state nothing to normalize.")
        return {"messages": state.get("messages", []), "thinking_log": thinking_log}

    # shallow copy
    messages = state["messages"][:]
    last_message = messages[-1]

    # Extract content and tool_calls first
    tool_calls = getattr(last_message, "tool_calls", None)
    content = getattr(last_message, "content", "")

    logger.debug(f"ENTER normalize_tool_node with message type: {type(last_message)}")
    logger.debug(f"normalize_tool_node message content: {content[:200] if content else 'empty'}...")
    logger.debug(f"normalize_tool_node tool_calls value: {tool_calls}")
    logger.debug(f"normalize_tool_node tool_calls type: {type(tool_calls)}")
    logger.debug(f"normalize_tool_node tool_calls bool evaluation: {bool(tool_calls)}")
    
    # Log the full message attributes for debugging
    logger.debug(f"normalize_tool_node last_message attributes: {dir(last_message)}")
    if hasattr(last_message, 'additional_kwargs'):
        logger.debug(f"normalize_tool_node additional_kwargs: {last_message.additional_kwargs}")
    if hasattr(last_message, 'response_metadata'):
        logger.debug(f"normalize_tool_node response_metadata: {last_message.response_metadata}")

    # Could either be None or []
    if not tool_calls:
        parsed_tool_calls = parse_tool_call_from_content(content)
        if parsed_tool_calls:
            thinking_log += "parsed tool calls from content. "
            # Create new message preserving original attributes using model_copy
            normalized = last_message.model_copy(update={
                "content": "",
                "tool_calls": parsed_tool_calls
            })
            messages[-1] = normalized
            logger.debug(f"normalize_tool_node: parsed tool calls from content: {parsed_tool_calls}")
            logger.debug(f"normalize_tool_node: replaced message with normalized version")
        else:
            thinking_log += "no tool calls found leaving message unchanged. "
            logger.debug("normalize_tool_node: no tool calls found in content, leaving message unchanged")
    else:
        thinking_log += "tool calls already present, clearing content. "
        logger.debug(f"normalize_tool_node: {len(tool_calls)} tool calls already present, clearing content")
        for idx, tc in enumerate(tool_calls):
            logger.debug(f"Existing tool call {idx+1}: {tc}")
        
        # Clear content when tool calls are present to avoid redundant JSON
        if content:
            # Create new message with cleared content, preserving all other attributes using model_copy
            normalized = last_message.model_copy(update={"content": ""})
            messages[-1] = normalized
            logger.debug(f"normalize_tool_node: cleared content from tool-calling message")

    return {"messages": messages, "thinking_log": thinking_log}


def call_llm_model_node(
    state: ReactToolsCallingAgentState,
    config: RunnableConfig,
    normalize_anthropic_to_openai: bool = False
) -> Dict:
    """
    Call the LLM model with all messages in the state.
    
    This node invokes the LLM with the current message history and returns
    the response to be added to the message list.
    
    Args:
        state: The current agent state containing messages and llm
        config: The runnable configuration
        normalize_anthropic_to_openai: If True, converts Anthropic-style list content
                                       to OpenAI-compatible string format before LLM
                                       invocation (default: False)
        
    Returns:
        Dictionary with the LLM response message
    """
    messages = state["messages"]
    last_message = state["messages"][-1]

    logger.info(f"=====> Calling LLM to generate response (call_llm_model_node)")
    logger.info(f"Number of messages in state: {len(messages)}")
    logger.info(f"Latest message type: {type(last_message)}")
    logger.info(f"Latest message content: {getattr(last_message, 'content', 'no content')[:200]}...")
    
    # Normalize Anthropic content to OpenAI format if requested
    if normalize_anthropic_to_openai:
        logger.debug(f"Normalizing Anthropic content to OpenAI format before LLM invocation")
        messages = normalize_anthropic_content_to_openai(messages)

    # Log all messages being passed to the LLM
    logger.debug(f"Number of messages being passed to LLM: {len(messages)}")
    for i, msg in enumerate(messages):
        logger.debug(f"Message {i+1}: type={type(msg).__name__}, role={getattr(msg, 'type', 'N/A')}, content_preview={str(msg.content)[:500]}...")


    response = state["llm"].invoke(messages, config)
    
    # Log the LLM response details
    logger.info(f"=====> LLM response received (call_llm_model_node)")
    logger.info(f"Response type: {type(response)}")
    logger.debug(f"Response content: {getattr(response, 'content', 'no content')[:500]}...")
    logger.debug(f"Response has tool_calls attribute: {hasattr(response, 'tool_calls')}")
    if hasattr(response, 'tool_calls'):
        tool_calls = getattr(response, 'tool_calls', None)
        logger.debug(f"Response tool_calls value: {tool_calls}")
        logger.debug(f"Response tool_calls type: {type(tool_calls)}")
        logger.debug(f"Response tool_calls length: {len(tool_calls) if tool_calls else 0}")
        if tool_calls:
            for idx, tc in enumerate(tool_calls):
                logger.debug(f"Tool call {idx+1}: {tc}")
    if hasattr(response, 'additional_kwargs'):
        logger.debug(f"Response additional_kwargs: {response.additional_kwargs}")
    if hasattr(response, 'response_metadata'):
        logger.debug(f"Response response_metadata: {response.response_metadata}")
    
    return {"messages": [response]}


def create_react_tools_workflow(
    tools: List[Any],
    enable_tool_logging: bool = False,
    tool_logger: Optional[logging.Logger] = None,
    normalize_anthropic_to_openai: bool = False,
    agent_executable_tool_names: Optional[List[str]] = None,
) -> StateGraph:
    """
    Create a standard ReAct tools calling workflow graph.
    
    This function creates a LangGraph workflow with the standard structure:
    - Entry point: "llm"
    - Nodes: "llm", "normalize", "tools"
    - Edges: "llm" → "normalize", "tools" → "llm"
    - Conditional edges from "normalize" based on tools_condition
    
    The workflow uses the standard node implementations from this module:
    - call_llm_model_node: Invokes the LLM with message history
    - normalize_tool_node: Normalizes tool calls in messages
    - tools_condition: Routes based on whether tools should be called
    
    Args:
        tools: List of tools to use in the workflow
        enable_tool_logging: Whether to wrap ToolNode with debug logging (default: False)
        tool_logger: Logger instance (required if enable_tool_logging=True)
        normalize_anthropic_to_openai: If True, converts Anthropic-style list content
                                       to OpenAI-compatible string format in
                                       call_llm_model_node (default: False)
        agent_executable_tool_names: List of tool names that should be executed by the agent (not by the workflow).
                                     When the LLM calls these tools, the workflow will return the
                                     AIMessage with tool_calls instead of executing them.
                                     This is useful for tools that must be executed by external systems.
    
    Returns:
        Configured StateGraph workflow (not yet compiled)
        
    Example:
        >>> workflow = create_react_tools_workflow(
        ...     tools=my_tools,
        ...     enable_tool_logging=True,
        ...     tool_logger=logger,
        ...     normalize_anthropic_to_openai=True,
        ...     agent_executable_tool_names=['tool1', 'tool2']
        ... )
        >>> graph = workflow.compile()
    """
    workflow = StateGraph(ReactToolsCallingAgentState)
    workflow.set_entry_point("llm")
    
    # Wrap call_llm_model_node to pass normalize_anthropic_to_openai parameter
    def llm_node_wrapper(state, config):
        return call_llm_model_node(state, config, normalize_anthropic_to_openai=normalize_anthropic_to_openai)
    
    workflow.add_node("llm", llm_node_wrapper)
    workflow.add_node("normalize", normalize_tool_node)
    
    # Create tool node with optional interception for agent-executable tools
    original_tool_node = ToolNode(tools)
    agent_executable_tool_names_set = set(agent_executable_tool_names) if agent_executable_tool_names else set()
    
    async def custom_tool_node(state):
        """
        Custom tool node that:
        1. Checks if tool call is for an agent-executable tool
        2. If yes, returns empty messages (workflow will end with AIMessage containing tool_calls)
        3. If no, executes the tool normally
        """
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}
        
        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        
        if not tool_calls:
            return {"messages": []}
        
        # Check if any tool call is for an agent-executable tool
        has_agent_executable = False
        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            if tool_name in agent_executable_tool_names_set:
                has_agent_executable = True
                if enable_tool_logging and tool_logger:
                    tool_logger.info(f"[MCP DEBUG] Tool '{tool_name}' is agent-executable - returning to caller for execution")
                else:
                    logger.info(f"Tool '{tool_name}' is agent-executable - returning to caller for execution")
        
        if has_agent_executable:
            # Don't execute - return empty to end workflow with AIMessage containing tool_calls
            return {"messages": []}
        
        # All tools are executable - proceed with execution
        if enable_tool_logging and tool_logger:
            tool_logger.debug(f"[MCP DEBUG] ToolNode invoked with state: {state}")
            tool_logger.debug(f"[MCP DEBUG] Processing {len(tool_calls)} tool calls")
            for idx, tc in enumerate(tool_calls):
                tool_logger.debug(f"[MCP DEBUG] Tool call {idx+1}: name='{tc.get('name')}', args={tc.get('args')}, id='{tc.get('id')}'")
            
            result = await original_tool_node.ainvoke(state)
            
            # Log tool results
            result_messages = result.get("messages", [])
            tool_logger.debug(f"[MCP DEBUG] ToolNode returned {len(result_messages)} messages")
            for idx, msg in enumerate(result_messages):
                if hasattr(msg, "content"):
                    tool_logger.debug(f"[MCP DEBUG] Tool result {idx+1}: content='{msg.content[:200]}...' (truncated)")
                    tool_logger.debug(f"[MCP DEBUG] Tool result {idx+1} full content: {msg.content}")
            
            return result
        else:
            return await original_tool_node.ainvoke(state)
    
    # Create a wrapper that tracks if tools were executed
    tool_execution_state = {"executed": False}
    
    async def tracked_custom_tool_node(state):
        """Wrapper that tracks whether tools were actually executed."""
        result = await custom_tool_node(state)
        # If result has messages, tools were executed
        tool_execution_state["executed"] = len(result.get("messages", [])) > 0
        return result
    
    workflow.add_node("tools", tracked_custom_tool_node)
    
    workflow.add_edge("llm", "normalize")
    
    # Conditional edge from tools: if non-executable tool was encountered, END; otherwise go back to llm
    def should_continue_after_tools(state):
        """Check if we should continue or end after tool execution."""
        if tool_execution_state["executed"]:
            # Tools were executed - continue to llm
            tool_execution_state["executed"] = False  # Reset for next iteration
            return "llm"
        else:
            # Non-executable tool encountered - END the workflow
            return "end"
    
    workflow.add_conditional_edges(
        "tools",
        should_continue_after_tools,
        {
            "llm": "llm",
            "end": "__end__"
        }
    )
    
    workflow.add_conditional_edges(
        "normalize",
        tools_condition,
    )
    
    return workflow


# Made with Bob
