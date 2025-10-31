from typing_extensions import TypedDict
from typing import Annotated, List, Dict, Sequence
from langgraph.graph import add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage


class State(TypedDict):

    thinking_log: Annotated[list[AIMessage], add_messages]
    original_user_prompt: HumanMessage
    chat_history: list[BaseMessage]

    useful_tools: List[Dict[str, str]]

    existing_tools: List[Dict[str, str]]
    need_to_generate_tools: List[Dict[str, str]]
    generated_tools: List[Dict[str, str]]
    env_id: str

    messages: Annotated[Sequence[BaseMessage], add_messages]
