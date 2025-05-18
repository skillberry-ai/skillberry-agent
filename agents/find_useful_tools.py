import logging
import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from agents.state import State
from config.config_ui import config
from llm.common import llm
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

find_useful_tools_chat_prompt_template = ChatPromptTemplate(
    [
        ("system", "You are a helpful assistant"),
        (
            "system",
            "You are expert in finding functions and tools that can reduce AI hallucinations",
        ),
        (
            "system",
            "For each suggested tool and function, "
            "include the function name, and a list of usage examples.",
        ),
        (
            "system",
            "For each suggested tool and function, "
            "specify the name of the tool in hungarian notation and provide crisp and informative description."
            "Tool names should include only the letters A-Z and a-z, digits 0-9, and underscores. "
            "Do not use spaces or any other characters.",
        ),
        ("system", "Suggest only simple tools and simple functions"),
        (
            "system",
            "Each function in the list of suggested tools and functions should provide different functionality. "
            "Do not suggest tools and functions that provide the same or similar functionality."
            "If you identify that two or more tools and functions provide the same or similar functionality, "
            "suggest only one of them.",
        ),
        (
            "system",
            "Suggest minimal amount of functions. Focus on deterministic tools. "
            "For example mathematical functions, transformations and conversion functions, "
            "string manipulation functions, and so on.",
        ),
        ("system", "Do not suggest tools and functions that performs error handling"),
        (
            "system",
            "Do not suggest tools and functions that are functional helper functions."
            "For example, do not suggest printing to the console functions or `hello world` functions.",
        ),
        (
            "system",
            "Do not suggest tools and functions that requires access to external services",
        ),
        ("system", "Do not suggest tools and functions that are complicated"),
        ("system", "Response only using json format"),
        (
            "user",
            "List up to {max_suggested_functions} deterministic tools and functions that helps "
            'to response to the prompt: "{user_prompt}"',
        ),
    ]
)


class ToolCategory(str, Enum):
    FACTUAL_TOOL_CATEGORY = "factual"
    EXTERNAL_TOOL_CATEGORY = "external"
    STRUCTURED_TOOL_CATEGORY = "structured"


tool_category_description = {
    ToolCategory.FACTUAL_TOOL_CATEGORY: "a tool that provides factual knowledge "
                                        "(e.g., time, date, location, user, weather data, company financials).",
    ToolCategory.EXTERNAL_TOOL_CATEGORY: "a tool that retrieval data from an external source "
                                         "(e.g., databases, APIs, search engines).",
    ToolCategory.STRUCTURED_TOOL_CATEGORY: "a tool that performs structured operations "
                                           "(e.g., math, date calculations, unit conversions).",
}

# only tools that are `True` will be candidates for generation
tool_category_candidate_for_generation = {
    ToolCategory.FACTUAL_TOOL_CATEGORY: False,
    ToolCategory.EXTERNAL_TOOL_CATEGORY: False,
    ToolCategory.STRUCTURED_TOOL_CATEGORY: True,
}

category_descriptions = "\n".join(
    f"- `{key.value}`: {desc}" for key, desc in tool_category_description.items()
)


class SuggestedTool(BaseModel):
    name: str = Field(description="the name of the tool (in hungarian notation, no spaces, no special characters)")
    description: str = Field(description="the description of the tool")
    examples: str = Field(description="Usage examples of the tool")
    category: str = Field(
        description=f"The tool category. "
        f'Valid values for "category" are:\n {category_descriptions}'
    )
    candidate_for_generation: Optional[bool]


class FindingToolsResponseJsonSchema(BaseModel):
    suggested_tools: List[SuggestedTool] = Field(
        description="A list of suggested tools.\n"
        "Each suggested tool includes a dictionary with exactly four key and values:\n"
        '"name" - the name of the tool.\n '
        '"description" - the description of the tool\n'
        '"examples" - Usage examples of the tool\n'
        '"category" - the category of the tool\n'
    )


# plan what tools can help to resolve the user prompt
# get for each of the tools the name and description
def find_useful_tools(state: State):
    thinking_log = []
    logging.info(f"=======>>> find_useful_tools. started <<<=======")
    logger.info("find_useful_tools called")
    structured_llm = llm.with_structured_output(
        schema=FindingToolsResponseJsonSchema,
        method="function_calling",
        strict=True,
        include_raw=False,
    )

    find_useful_tools_chain = find_useful_tools_chat_prompt_template | structured_llm
    user_content = state["original_user_prompt"].content
    logger.info(f"finding useful tools for the user content: {user_content}")
    max_suggested_functions = config.get("max_suggested_functions")
    response = find_useful_tools_chain.invoke(
        {
            "user_prompt": user_content,
            "max_suggested_functions": max_suggested_functions,
        }
    )
    logger.info("find_useful_tools returned: %s", response)

    # Add to useful_tools only tools from relevant categories
    useful_tools = []
    for suggested_tool in response.suggested_tools:
        suggested_tool.candidate_for_generation = (
            tool_category_candidate_for_generation[suggested_tool.category]
        )

        suggested_tool.name = re.sub(r'[^A-Za-z_]', '_', suggested_tool.name)
        useful_tools.append(suggested_tool)

    if useful_tools is not None:
        thinking_log.append(
            "I think that there are tools that "
            "can help me to reduce hallucinations and be more accurate."
        )
        tool_descriptions = ""
        for i, tool in enumerate(useful_tools):
            tool_descriptions += f"{tool.category} tool that {tool.description}"
            if i < len(useful_tools) - 1:
                tool_descriptions += ", and a "
            else:
                tool_descriptions += "."

        thinking_log.append(f"I think that the tools are: a {tool_descriptions}")

    logging.info(f"=======>>> find_useful_tools. ended <<<=======")
    return {"useful_tools": useful_tools, "thinking_log": thinking_log}
