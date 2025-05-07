import logging

from config import config, config_structure
from agents.state import State

from utils.tools_maker_api import tools_maker

logger = logging.getLogger(__name__)


def code_missing_tools(state: State):
    thinking_log = []
    logging.info(f"=======>>> code_missing_tools. starts <<<=======")
    need_to_generate_tools = state["need_to_generate_tools"]
    generated_tools = []

    logging.info(f"code_missing_tools: need_to_generate_tools: {need_to_generate_tools}")
    for need_to_generate_tool in need_to_generate_tools:
        name = need_to_generate_tool.name

        # A flag that allows (or disallows) to generate tools dynamically by the agent
        my_config = config.DynamicConfig(config_structure.CONFIG_STRUCTURE)
        generate_tools_dynamically = my_config.get("generate_tools_dynamically")
        if not generate_tools_dynamically:
            thinking_log.append("I am not allowed to code new tools. ")
            logger.info(
                f"!!! generate_tools_dynamically is False: tool {name} will not be generated !!!")
            continue

        try:
            response = tools_maker.generate_tool(
                need_to_generate_tool.name,
                need_to_generate_tool.description,
                need_to_generate_tool.examples,
                skip_validation=False,
                original_prompt=state.original_user_prompt.content,
            )

            if response is None:
                logger.info(f"!!! tools_maker.generate_tool failed for tool {name}. The tool will not be generated !!!")
                thinking_log.append("I failed to code new tool {name}. ")
                continue

            generated_tool_name = response["name"]
            generated_tool_description = response["description"]
            logger.info(f"!!! tools_maker.generate_tool succeeded for tool {generated_tool_name} !!!")
            thinking_log.append(f"I just coded a new ephemeral tool {generated_tool_name}. ")

            generated_tools.append({
                "name": generated_tool_name,
                "description": generated_tool_description
            })
        except Exception as e:
            logger.error(f"code_missing_tools: generate_tool for '{name}' failed: {str(e)}")

    if len(generated_tools) > 0:
        thinking_log.append("I just coded ephemeral tools that I will use.")
        tool_descriptions = ""
        for i, tool in enumerate(generated_tools):
            tool_description = tool["description"]
            tool_descriptions += f"{tool_description} "
            if i < len(generated_tools) - 1:
                tool_descriptions += ", and a tool that "
            else:
                tool_descriptions += "."

        thinking_log.append(f"a tool that {tool_descriptions}")

    logging.info(f"=======>>> code_missing_tools. ended <<<=======")

    return {
        "generated_tools": generated_tools,
        "thinking_log": thinking_log
    }
