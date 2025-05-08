import logging

from agents.state import State
from config.config_ui import config
from utils.tools_service_api import tools_service

logger = logging.getLogger(__name__)

# search for tools from the repository using API call (semantic search)


def find_existing_tools(state: State):
    thinking_log = []
    logging.info(f"=======>>> find_existing_tools. started <<<=======")
    existing_tools = []
    need_to_generate_tools = []

    try:
        for useful_tool in state["useful_tools"]:
            name = useful_tool.name
            description = useful_tool.description
            examples = useful_tool.examples
            category = useful_tool.category
            candidate_for_generation = useful_tool.candidate_for_generation

            logger.info(f"find_existing_tools called for tool: {name}")
            # issue get request against the url with `search_term` equals to the name of the suggested tool
            similarity_threshold = config.get("advanced__similarity_threshold")
            max_tools_count = config.get("advanced__max_tools_count")
            found_tools = tools_service.search_tools(
                name, description, max_tools_count, similarity_threshold
            )

            if found_tools is not None and len(found_tools) > 0:
                logger.info("find_existing_tools returned: %s", found_tools)

                for found_tool in found_tools:
                    logger.info(f"Found existing tool: {found_tool}")

                    found_tool["search_term_name"] = name
                    found_tool["search_term_description"] = description
                    found_tool["search_term_examples"] = examples

                    found_tool["name"] = found_tool["filename"]

                    # append only if the tool is not already in the list of existing tools
                    if not any(
                        tool["name"] == found_tool["name"] for tool in existing_tools
                    ):
                        existing_tools.append(found_tool)
            else:
                # Can't find the tools, adding the tools to the list of need_to_generate_tools tools
                logger.info(f"Can't find the useful_tool {name}")
                if candidate_for_generation:
                    logger.info(f"Adding {name} to the list of need_to_generate_tools")
                    need_to_generate_tools.append(useful_tool)
                else:
                    logger.info(
                        f"The tools {name} from category {category} is not candidate for generation, "
                        f"not adding to the list of need_to_generate_tools"
                    )
                continue
    except Exception as e:
        logging.error(f"Error while find_existing_tools: {e}")

    if len(existing_tools) > 0:
        thinking_log.append("I found existing approved tools that I will use.")
        tool_names = ""
        for i, tool in enumerate(existing_tools):
            tool_name = (
                tool["name"].split(".py")[0] if ".py" in tool["name"] else tool["name"]
            )
            tool_names += f"{tool_name}"
            if i < len(existing_tools) - 1:
                tool_names += ", and a tool named "
            else:
                tool_names += "."

        thinking_log.append(f"A tool named {tool_names}")

    logging.info(f"=======>>> find_existing_tools. ended <<<=======")
    return {
        "existing_tools": existing_tools,
        "need_to_generate_tools": need_to_generate_tools,
        "thinking_log": thinking_log,
    }
