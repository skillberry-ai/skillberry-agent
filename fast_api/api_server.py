import logging
import time

from fastapi import FastAPI, HTTPException
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
import requests

from tools_agentic_graph import stream_graph_updates

# Define the API
api_server = FastAPI()

logger = logging.getLogger(__name__)


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
):
    try:
        user_message = ChatMessage(role="user", content=user_prompt)
        chat_request = ChatRequest(model="API_CALL", messages=[user_message])
        response = api_chat_completion(chat_request)
        return response
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_server.post("/chat/completions", tags=["chat"])
def api_chat_completion(request: ChatRequest):
    try:
        chat_history = []
        for message in request.messages:
            chat_history.append(message.to_base_message())

        last_user_prompt = chat_history[-1]
        response = stream_graph_updates(
            chat_history=chat_history, original_user_prompt=last_user_prompt
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
            "id": "blueberry",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "blueberry",
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
            "system_fingerprint": "blueberry",
        }

        return response
    except requests.HTTPError as e:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@api_server.get("/health")
def health_check():
    return {"status": "ok"}
