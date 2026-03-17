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
    
    This node checks if the last message contains tool calls. If not, it attempts
    to parse tool calls from the message content. This handles cases where LLMs
    return tool calls as text instead of structured tool_calls.
    
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

    logger.info(f"ENTER normalize_tool_node with message type: {type(last_message)}")
    logger.info(f"normalize_tool_node message content: {content[:200] if content else 'empty'}...")

    # Could either be None or []
    if not tool_calls:
        parsed_tool_calls = parse_tool_call_from_content(content)
        if parsed_tool_calls:
            thinking_log += "parsed tool calls from content. "
            normalized = AIMessage(
                content="",
                tool_calls=parsed_tool_calls
            )
            logger.info(f"normalize_tool_node: parsed tool calls from content: {parsed_tool_calls}")
            logger.info(f"normalize_tool_node: replacing last message with normalized message")
            messages[-1] = normalized
        else:
            thinking_log += "no tool calls found leaving message unchanged. "
            logger.info("normalize_tool_node: no tool calls found in content, leaving message unchanged")
    else:
        thinking_log += "tool calls already present leaving message unchanged. "
        logger.info(f"normalize_tool_node: {len(tool_calls)} tool calls already present, leaving message unchanged")
        for idx, tc in enumerate(tool_calls):
            logger.info(f"Existing tool call {idx+1}: {tc}")

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
        logger.info(f"Normalizing Anthropic content to OpenAI format before LLM invocation")
        messages = normalize_anthropic_content_to_openai(messages)

    response = state["llm"].invoke(messages, config)
    return {"messages": [response]}


def create_react_tools_workflow(
    tools: List[Any],
    enable_tool_logging: bool = False,
    tool_logger: Optional[logging.Logger] = None,
    normalize_anthropic_to_openai: bool = False,
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
    
    Returns:
        Configured StateGraph workflow (not yet compiled)
        
    Example:
        >>> workflow = create_react_tools_workflow(
        ...     tools=my_tools,
        ...     enable_tool_logging=True,
        ...     tool_logger=logger,
        ...     normalize_anthropic_to_openai=True
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
    
    # Create tool node with optional logging wrapper
    if enable_tool_logging and tool_logger:
        original_tool_node = ToolNode(tools)
        
        async def logged_tool_node(state):
            tool_logger.info(f"[MCP DEBUG] ToolNode invoked with state: {state}")
            messages = state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                tool_calls = getattr(last_msg, "tool_calls", [])
                tool_logger.info(f"[MCP DEBUG] Processing {len(tool_calls)} tool calls")
                for idx, tc in enumerate(tool_calls):
                    tool_logger.info(f"[MCP DEBUG] Tool call {idx+1}: name='{tc.get('name')}', args={tc.get('args')}, id='{tc.get('id')}'")
            
            result = await original_tool_node.ainvoke(state)
            
            # Log tool results
            result_messages = result.get("messages", [])
            tool_logger.info(f"[MCP DEBUG] ToolNode returned {len(result_messages)} messages")
            for idx, msg in enumerate(result_messages):
                if hasattr(msg, "content"):
                    tool_logger.info(f"[MCP DEBUG] Tool result {idx+1}: content='{msg.content[:200]}...' (truncated)")
                    tool_logger.info(f"[MCP DEBUG] Tool result {idx+1} full content: {msg.content}")
            
            return result
        
        workflow.add_node("tools", logged_tool_node)
    else:
        workflow.add_node(ToolNode(tools))
    
    workflow.add_edge("llm", "normalize")
    workflow.add_edge("tools", "llm")
    workflow.add_conditional_edges(
        "normalize",
        tools_condition,
    )
    
    return workflow


# Made with Bob
