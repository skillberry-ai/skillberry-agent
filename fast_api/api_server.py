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
from agents.trajectory_manager import tracjectory_manager


# Define the API
api_server = FastAPI(
    title="Skillberry Tools Agent",
    description="Skillberry Tools Agent API",
    version=__git_version__,
)

logger = logging.getLogger(__name__)


# Load MCP tools implementation
from mcp_tools_agentic_graph import stream_graph_updates
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

        response = stream_graph_updates(
            chat_history=chat_history,
            skillberry_context=skillberry_context,
        )
        if response is None:
            logging.error("stream_graph_updates returned None")
            raise HTTPException(
                status_code=500,
                detail="Internal server error: stream_graph_updates returned None",
            )
        try:
            final_response = list(response)[0]["messages"][-1]["content"]
        except (IndexError, TypeError) as e:
            logging.error(f"Error processing response from stream_graph_updates: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error processing response from stream_graph_updates",
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
def trajectory(request: Request):
    headers = request.headers
    logging.info("!!!!!!!!!!!!!!!!!")
    logging.info(f"headers: {headers}")
    logging.info("!!!!!!!!!!!!!!!!!")

    skillberry_context = unflatten_keys(headers).get(SKILLBERRY_CONTEXT.lower())
    logging.info(f"@@@@@@@@@@@@@@@@")
    logging.info(f"skillberery_context: {skillberry_context}")            
    logging.info(f"@@@@@@@@@@@@@@@@")

    trajectory = tracjectory_manager.get_trajectory(skillberry_context)
    return {"trajectory": trajectory}


@api_server.post("/disconnect")
def disconnect(request: Request):
    headers = request.headers
    logging.info("!!!!!!!!!!!!!!!!!")
    logging.info(f"headers: {headers}")
    logging.info("!!!!!!!!!!!!!!!!!")

    skillberry_context = unflatten_keys(headers).get(SKILLBERRY_CONTEXT.lower())
    logging.info(f"@@@@@@@@@@@@@@@@")
    logging.info(f"skillberery_context: {skillberry_context}")            
    logging.info(f"@@@@@@@@@@@@@@@@")

    # ignore errors, also in case BTA is in none-mcp mode
    try:
        from utils.skillberry_api import skillberry_api
        server_name = "proxy-vmcp-server"
        logging.info(f"Removing VMCP server '{server_name}'")
        skillberry_api.remove_vmcp_server(name=server_name)
    except:
        pass
    try:
        tracjectory_manager.remove_trajectory(skillberry_context)
    except:
        pass


# Health check endpoint
@api_server.get("/health")
def health_check():
    return {"status": "ok"}


@api_server.get("/version")
def health_check():
    return {"version": __git_version__}
