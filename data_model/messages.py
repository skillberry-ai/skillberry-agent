from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal, Optional


AssistantRole = Literal["assistant"]
ToolRole = Literal["tool"]
ToolRequestor = Literal["user", "assistant"]


def format_time(time: datetime) -> str:
    """
    Format the time in the format YYYYMMDD_HHMMSS.
    """
    return time.isoformat()


def get_now() -> str:
    """
    Returns the current date and time in the format YYYYMMDD_HHMMSS.
    """
    now = datetime.now()
    return format_time(now)


class ToolCall(BaseModel):
    """
    A tool call.
    """

    id: str = Field(default="", description="The unique identifier for the tool call.")
    name: str = Field(description="The name of the tool.")
    arguments: dict = Field(description="The arguments of the tool.")
    requestor: ToolRequestor = Field(
        "assistant",
        description="The requestor of the tool call.",
    )


class ParticipantMessageBase(BaseModel):
    """
    A message from a participant in the conversation.
    """

    role: str = Field(description="The role of the message sender.")

    content: Optional[str] = Field(
        description="The content of the message.", default=None
    )
    tool_calls: Optional[list[ToolCall]] = Field(
        description="The tool calls made in the message.", default=None
    )
    turn_idx: Optional[int] = Field(
        description="The index of the turn in the conversation.", default=None
    )
    timestamp: Optional[str] = Field(
        description="The timestamp of the message.", default_factory=get_now
    )
    cost: Optional[float] = Field(description="The cost of the message.", default=None)

    usage: Optional[dict] = Field(
        description="The token usage of the message.", default=None
    )
    raw_data: Optional[dict] = Field(
        description="The raw data of the message.", default=None
    )


class AssistantMessage(ParticipantMessageBase):
    """
    A message from the assistant.
    """

    role: AssistantRole = Field(description="The role of the message sender.")


class ToolMessage(BaseModel):
    """
    A message from the tool.
    """

    id: str = Field(description="The unique identifier for the tool call.")
    role: ToolRole = Field(description="The role of the message sender.")
    content: Optional[str] = Field(description="The output of the tool.", default=None)
    requestor: Literal["user", "assistant"] = Field(
        "assistant",
        description="The requestor of the tool call.",
    )
    error: bool = Field(description="Whether the tool call failed.", default=False)
    turn_idx: Optional[int] = Field(
        description="The index of the turn in the conversation.", default=None
    )
    timestamp: Optional[str] = Field(
        description="The timestamp of the message.", default_factory=get_now
    )
