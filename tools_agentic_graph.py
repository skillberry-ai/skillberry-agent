import logging

from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.graph import StateGraph, START, END

from agents.code_missing_tools import code_missing_tools
from agents.find_useful_tools import find_useful_tools
from agents.all_tools import all_tools
from agents.state import State


logger = logging.getLogger(__name__)

tools_agentic_graph = None


def define_tools_agentic_graph():
    global tools_agentic_graph
    graph_builder = StateGraph(State)
    graph_builder.add_node("all_tools",
                           all_tools)

    graph_builder.add_edge(START, "all_tools")
    graph_builder.add_edge("all_tools", END)

    # Compile the agentic graph
    tools_agentic_graph = graph_builder.compile()
    logger.info("Tools agentic graph compiled")
    return tools_agentic_graph


def stream_graph_updates(chat_history: list[BaseMessage], original_user_prompt: HumanMessage, env_id):

    # print("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
    # print(f"{input_messages}")
    # print("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")

    for event in tools_agentic_graph.stream({"original_user_prompt": original_user_prompt,
                                             "chat_history": chat_history,
                                             "messages": chat_history,
                                             "env_id": env_id,
                                             "thinking_log": []}):
        # print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
        # print(f"{input_messages}")
        # print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
        for value in event.values():
            logging.info("==> stream_graph_updates: event.value: [%s]", value)
    values = event.values()
    return values
