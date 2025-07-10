import logging

from config.config_ui import config
from agents.state import State

from utils.tools_maker_api import tools_maker
from config.generated_tools_count import generated_tools_count

logger = logging.getLogger(__name__)


def code_missing_tools(state: State):
    thinking_log = []
    logging.info(f"=======>>> code_missing_tools. starts <<<=======")
    need_to_generate_tools = state["need_to_generate_tools"]
    generated_tools = []

    logging.info(
        f"code_missing_tools: need_to_generate_tools: {need_to_generate_tools}"
    )
    for need_to_generate_tool in need_to_generate_tools:
        name = need_to_generate_tool.name

        # A flag that allows (or disallows) to generate tools dynamically by the agent
        generate_tools_dynamically = config.get("generate_tools_dynamically")
        if not generate_tools_dynamically:
            thinking_log.append("I am not allowed to code new tools. ")
            logger.info(
                f"!!! generate_tools_dynamically is False: tool {name} will not be generated !!!"
            )
            continue

        max_tools_generation_per_execution = config.get(
            "advanced__max_tools_generation_per_execution"
        )
        if (
            generated_tools_count.get_generated_tools_count()
            >= max_tools_generation_per_execution
        ):
            thinking_log.append("I reached the limit of tools I can code. ")
            logger.info(
                f"!!! generated tools count >= {max_tools_generation_per_execution}: "
                f"tool {name} will not be generated !!!"
            )
            continue

        try:
            response = tools_maker.generate_tool(
                need_to_generate_tool.name,
                need_to_generate_tool.description,
                need_to_generate_tool.examples,
                original_prompt=state["original_user_prompt"].content,
            )

            if response is None:
                logger.info(
                    f"!!! tools_maker.generate_tool failed for tool {name}. The tool will not be generated !!!"
                )
                thinking_log.append("I failed to code new tool {name}. ")
                continue

            # update the tool with the generated name and description
            generated_tool_name = response["detail"]["manifest"]["name"]
            generated_tool_description = response["detail"]["manifest"]["description"]

            need_to_generate_tool.name = generated_tool_name
            need_to_generate_tool.description = generated_tool_description

            logger.info(
                f"!!! tools_maker.generate_tool succeeded for tool {generated_tool_name} !!!"
            )
            thinking_log.append(
                f"I just coded a new ephemeral tool {generated_tool_name}. "
            )

            # Increment the generated tools count
            generated_tools_count.increment_generated_tools_count()

            generated_tools.append(
                {"name": generated_tool_name, "description": generated_tool_description}
            )
        except Exception as e:
            logger.error(
                f"code_missing_tools: generate_tool for '{name}' failed: {str(e)}"
            )

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

    return {"generated_tools": generated_tools, "thinking_log": thinking_log}
