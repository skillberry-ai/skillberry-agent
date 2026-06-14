from typing import Any, Optional, List, Dict
import json
import uuid

import logging
import time

import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from fast_api.git_version import __git_version__
from utils.utils import SKILLBERRY_CONTEXT, unflatten_keys
from llm.common import current_llm
from config.config_ui import config

# Define the API
api_server = FastAPI(
    title="Skillberry Tools Agent",
    description="Skillberry Tools Agent API",
    version=__git_version__,
)

logger = logging.getLogger(__name__)


# Load agentic graph implementation
from agents.agentic_graph import execute_agentic_graph, trajectory, disconnect

logger.info("Using agentic graph implementation")


class ChatMessage(BaseModel):
    role: str = Field(
        ...,
        description="Role of the message sender, e.g., 'system', 'user', or 'assistant'",
    )
    content: str = Field(..., description="Message content")

    # to BaseMessage
    def to_base_message(self):
        if self.role == "user":
            return HumanMessage(content=self.content)
        elif self.role == "assistant":
            return AIMessage(content=self.content)
        elif self.role == "system":
            return SystemMessage(content=self.content)
        else:
            # Fallback for unknown roles
            return HumanMessage(content=self.content)


# Tool definition models
class ToolFunction(BaseModel):
    name: str = Field(..., description="Function name")
    description: Optional[str] = Field(None, description="Function description")
    parameters: Optional[Dict[str, Any]] = Field(
        None, description="Function parameters schema"
    )


class Tool(BaseModel):
    type: str = Field("function", description="Tool type, typically 'function'")
    function: ToolFunction = Field(..., description="Function definition")


# Prompt request data model
class ChatRequest(BaseModel):
    model: str = Field(..., description="Model to use, e.g., 'granite'")
    messages: list[ChatMessage] = Field(..., description="List of messages for context")
    temperature: float = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: int = Field(
        8192, gt=0, description="Maximum number of tokens to generate"
    )
    tools: Optional[List[Tool]] = Field(
        None, description="List of tools/functions available to the model"
    )
    tool_choice: Optional[str] = Field(
        "auto",
        description="Tool choice strategy: 'auto', 'none', or specific tool name",
    )


# Helper functions for tool handling
def convert_tools_for_binding(tools: List[Tool]) -> List[Dict[str, Any]]:
    """
    Convert Pydantic Tool models to LangChain-compatible format.

    Args:
        tools: List of Tool objects from the request

    Returns:
        List of tool dictionaries in OpenAI format
    """
    tools_for_binding = []
    for tool in tools:
        tool_dict = {
            "type": "function",
            "function": {
                "name": tool.function.name,
                "description": tool.function.description or "",
                "parameters": tool.function.parameters or {},
            },
        }
        tools_for_binding.append(tool_dict)

    logging.info(f"Converted {len(tools_for_binding)} tools for binding")
    logging.info(f"Tool names: {[t['function']['name'] for t in tools_for_binding]}")

    return tools_for_binding


def build_response_with_tool_calls(llm_response: Any) -> Dict[str, Any]:
    """
    Build OpenAI-compatible response with proper tool call handling.

    Args:
        llm_response: Response from LLM (AIMessage or string)

    Returns:
        Dictionary with properly formatted message and finish_reason
    """
    # Check if response is an AIMessage object (has content attribute)
    if hasattr(llm_response, "content"):
        # AIMessage object - extract content and tool_calls
        logging.info(f"Processing AIMessage response")

        message_dict = {
            "role": "assistant",
            "content": llm_response.content or "",
        }

        # Add tool_calls if present
        if hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
            logging.info(
                f"Adding {len(llm_response.tool_calls)} tool calls to response"
            )
            message_dict["tool_calls"] = []

            for tool_call in llm_response.tool_calls:
                # Convert LangChain tool call format to OpenAI format
                tool_call_dict = {
                    "id": tool_call.get("id", f"call_{int(time.time())}"),
                    "type": "function",
                    "function": {
                        "name": tool_call.get("name", ""),
                        "arguments": json.dumps(
                            tool_call.get("args", {})
                        ),  # Must be valid JSON string
                    },
                }
                message_dict["tool_calls"].append(tool_call_dict)
                logging.info(
                    f"Tool call {tool_call.get('name')}: arguments={json.dumps(tool_call.get('args', {}))[:100]}"
                )

            finish_reason = "tool_calls"
        else:
            finish_reason = "stop"

        logging.info(
            f"Response content length: {len(message_dict['content'])}, finish_reason: {finish_reason}"
        )
    else:
        # String response (legacy agentic workflow format)
        message_dict = {
            "role": "assistant",
            "content": str(llm_response),
        }
        finish_reason = "stop"
        logging.info(f"Processing string response: {str(llm_response)[:100]}...")

    return {"message": message_dict, "finish_reason": finish_reason}


@api_server.post("/prompt", tags=["chat"])
def api_prompt(
    user_prompt: str,
    request: Request,
):
    try:
        user_message = ChatMessage(role="user", content=user_prompt)
        chat_request = ChatRequest(model="API_CALL", messages=[user_message])
        response = api_chat_completion(chat_request, request)
        return response
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_server.post("/chat/completions", tags=["chat"])
@api_server.post("/v1/chat/completions", tags=["chat"])
def api_chat_completion(chat_request: ChatRequest, request: Request):
    # Log the incoming ChatRequest
    logger.info(
        f"ChatRequest received - model: {chat_request.model}, temperature: {chat_request.temperature}, max_tokens: {chat_request.max_tokens}, messages count: {len(chat_request.messages)}"
    )
    logger.debug(f"ChatRequest full details: {chat_request.model_dump()}")

    headers = request.headers
    logging.debug("=" * 80)
    logging.debug(f"[REQUEST HEADERS] {headers}")
    logging.debug("=" * 80)

    skillberry_context = unflatten_keys(headers).get(SKILLBERRY_CONTEXT.lower())

    # Validate and provide default context if missing
    if skillberry_context is None:
        logging.warning("No Skillberry context headers provided, using default context")
        skillberry_context = {"env_id": "default"}
    elif "env_id" not in skillberry_context:
        logging.warning("Skillberry context missing env_id, adding default")
        skillberry_context["env_id"] = "default"

    logging.debug("=" * 80)
    logging.debug(f"[SKILLBERRY CONTEXT] {skillberry_context}")
    logging.debug("=" * 80)

    try:
        chat_messages = []
        if chat_request:
            for message in chat_request.messages:
                logging.debug(f"chat_messages to append: {message}")
                chat_messages.append(message.to_base_message())

        # Use the agentic workflow with chat request tools
        logging.info("Executing agentic workflow")

        # Convert tools if provided
        chat_request_tools = None
        if chat_request.tools:
            logging.info(
                f"Tools provided in request for agentic workflow: {len(chat_request.tools)} tools"
            )
            chat_request_tools = convert_tools_for_binding(chat_request.tools)

        final_response: str | Any = execute_agentic_graph(
            chat_messages=chat_messages,
            skillberry_context=skillberry_context,
            agent_tools=chat_request_tools,
        )

        if final_response is None:
            logging.error("execute_agentic_graph returned None")
            raise HTTPException(
                status_code=500,
                detail="Internal server error: execute_agentic_graph returned None",
            )

        # Handle response using helper function
        response_data = build_response_with_tool_calls(final_response)
        message_dict = response_data["message"]
        finish_reason = response_data["finish_reason"]

        # Generate unique ID for each response
        response_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

        response = {
            "id": response_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "skillberry",
            "choices": [
                {
                    "index": 0,
                    "message": message_dict,
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        }

        return response
    except requests.HTTPError as e:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_server.get("/trajectory")
def get_trajectory(request: Request):
    headers = request.headers
    logging.debug("=" * 80)
    logging.debug(f"[REQUEST HEADERS] {headers}")
    logging.debug("=" * 80)

    skillberry_context = unflatten_keys(headers).get(SKILLBERRY_CONTEXT.lower())

    # Validate and provide default context if missing
    if skillberry_context is None:
        logging.warning("No Skillberry context headers for /trajectory, using default")
        skillberry_context = {"env_id": "default"}
    elif "env_id" not in skillberry_context:
        skillberry_context["env_id"] = "default"

    logging.debug("=" * 80)
    logging.debug(f"[SKILLBERRY CONTEXT] {skillberry_context}")
    logging.debug("=" * 80)

    trajectory_result = trajectory(skillberry_context)
    return {"trajectory": trajectory_result}


@api_server.post("/disconnect")
def api_disconnect(request: Request):
    headers = request.headers
    logging.debug("=" * 80)
    logging.debug(f"[REQUEST HEADERS] {headers}")
    logging.debug("=" * 80)

    skillberry_context = unflatten_keys(headers).get(SKILLBERRY_CONTEXT.lower())

    # Validate and provide default context if missing
    if skillberry_context is None:
        logging.warning("No Skillberry context headers for /disconnect, using default")
        skillberry_context = {"env_id": "default"}
    elif "env_id" not in skillberry_context:
        skillberry_context["env_id"] = "default"

    logging.debug("=" * 80)
    logging.debug(f"[SKILLBERRY CONTEXT] {skillberry_context}")
    logging.debug("=" * 80)

    # Delegate to agentic_graph disconnect function
    # ignore errors, also in case BTA is in none-mcp mode
    try:
        disconnect(skillberry_context)
    except Exception as e:
        logging.warning(f"Error during disconnect: {e}")

    return {"status": "disconnected"}


# Health check endpoint
@api_server.get("/health")
def health_check():
    return {"status": "ok"}


@api_server.get("/version")
def health_check():
    return {"version": __git_version__}
