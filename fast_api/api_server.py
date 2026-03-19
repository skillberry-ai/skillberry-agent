import logging
import os
import time

import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Any

from langchain_core.messages import BaseMessage

from fast_api.git_version import __git_version__
from utils.utils import SKILLBERRY_CONTEXT, unflatten_keys
# Define the API
api_server = FastAPI(
    title="Skillberry Tools Agent",
    description="Skillberry Tools Agent API",
    version=__git_version__,
)

logger = logging.getLogger(__name__)


# Load MCP tools implementation
from agents.mcp_tools import mcp_tools, trajectory, disconnect
logger.info("Using MCP tools implementation")


class ChatMessage(BaseModel):
    role: str = Field(
        ...,
        description="Role of the message sender, e.g., 'system', 'user', or 'assistant'",
    )
    content: str = Field(..., description="Message content")

    # to BaseMessage
    def to_base_message(self):
        return BaseMessage(content=self.content, type=self.role)


# Prompt request data model
class ChatRequest(BaseModel):
    model: str = Field(..., description="Model to use, e.g., 'granite'")
    messages: list[ChatMessage] = Field(..., description="List of messages for context")
    temperature: float = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: int = Field(
        256, gt=0, description="Maximum number of tokens to generate"
    )
    # Skill resolution parameters (optional)
    skill_uuid: str | None = Field(None, description="Direct skill UUID (highest priority)")
    skill_name: str | None = Field(None, description="Skill name to resolve to UUID")
    skill_search_term: str | None = Field(None, description="Search term to find skill (lowest priority)")


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

    # TODO: BEGIN common skillberry library
    headers = request.headers
    logging.info("!!!!!!!!!!!!!!!!!")
    logging.info(f"headers: {headers}")
    logging.info("!!!!!!!!!!!!!!!!!")

    skillberry_context = unflatten_keys(headers).get(SKILLBERRY_CONTEXT.lower())
    logging.info(f"@@@@@@@@@@@@@@@@")
    logging.info(f"skillberery_context: {skillberry_context}")            
    logging.info(f"@@@@@@@@@@@@@@@@")
    # TODO: END common skillberry library

    try:
        chat_history = []
        if chat_request:
            for message in chat_request.messages:
                chat_history.append(message.to_base_message())

        final_response = mcp_tools(
            chat_history=chat_history,
            skillberry_context=skillberry_context,
            skill_uuid=chat_request.skill_uuid,
            skill_name=chat_request.skill_name,
            skill_search_term=chat_request.skill_search_term or "airline",  # Use default if not provided
        )
        
        if final_response is None:
            logging.error("mcp_tools returned None")
            raise HTTPException(
                status_code=500,
                detail="Internal server error: mcp_tools returned None",
            )

        logging.info(f"The response to the user prompt is: {final_response}")

        response = {
            "id": "skillberry",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "skillberry",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": final_response,
                        "refusal": None,
                    },
                    "logprobs": None,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 1,
                "prompt_tokens_details": {"cached_tokens": 0},
                "completion_tokens_details": {
                    "reasoning_tokens": 0,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0,
                },
            },
            "system_fingerprint": "skillberry",
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
    logging.info("!!!!!!!!!!!!!!!!!")
    logging.info(f"headers: {headers}")
    logging.info("!!!!!!!!!!!!!!!!!")

    skillberry_context = unflatten_keys(headers).get(SKILLBERRY_CONTEXT.lower())
    logging.info(f"@@@@@@@@@@@@@@@@")
    logging.info(f"skillberery_context: {skillberry_context}")
    logging.info(f"@@@@@@@@@@@@@@@@")

    # Handle missing context
    if skillberry_context is None:
        return {"trajectory": [], "warning": "No skillberry context provided"}
    
    trajectory_result = trajectory(skillberry_context)
    return {"trajectory": trajectory_result}


@api_server.post("/disconnect")
def api_disconnect(request: Request):
    headers = request.headers
    logging.info("!!!!!!!!!!!!!!!!!")
    logging.info(f"headers: {headers}")
    logging.info("!!!!!!!!!!!!!!!!!")

    skillberry_context = unflatten_keys(headers).get(SKILLBERRY_CONTEXT.lower())
    logging.info(f"@@@@@@@@@@@@@@@@")
    logging.info(f"skillberery_context: {skillberry_context}")
    logging.info(f"@@@@@@@@@@@@@@@@")

    # Delegate to mcp_tools disconnect function
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
