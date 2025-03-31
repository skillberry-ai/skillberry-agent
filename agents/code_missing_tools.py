import logging

from agents.state import State
from config.config_ui import config

logger = logging.getLogger(__name__)

# search for tools from the repository using API call (semantic search)
tools_repo_base_url = config.get("tools_repo_base_url")
post_file_url = f"{tools_repo_base_url}/file/"

headers = {"Accept": "application/json"}


def code_missing_tools(state: State):
    thinking_log = []
    logging.info(f"=======>>> code_missing_tools. starts <<<=======")
    need_to_generate_tools = state["need_to_generate_tools"]
    generated_tools = []

    logging.info(f"code_missing_tools: need_to_generate_tools: {need_to_generate_tools}")
    for need_to_generate_tool in need_to_generate_tools:
        name = need_to_generate_tool.name
        logging.info(f"Tool {name} will not be generated")
        thinking_log.append("I am not allowed to code new tools. ")

    logging.info(f"=======>>> code_missing_tools. ended <<<=======")
    # update the state with the generated tools
    return {"generated_tools": generated_tools,
            "thinking_log": thinking_log}
