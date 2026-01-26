import re
import json
import logging
import inspect
import requests

from langchain.tools import tool

from utils.tools_service_api import tools_service

from utils.utils import SKILLBERRY_CONTEXT, flatten_keys

logger = logging.getLogger(__name__)


# List of tools available to the agent. The tools should be pre-populated in SBS
# NOTE: This list is currently hardcoded and should be updated with your custom tools.
TOOLS = [
    "book_reservation",
    "get_reservation_details",
    "calculate",
    "cancel_reservation",
    "get_user_details",
    "list_all_airports",
    "search_direct_flight",
    "search_onestop_flight",
    "send_certificate",
    "transfer_to_human_agents",
    "update_reservation_baggages",
    "update_reservation_flights",
    "update_reservation_passengers",
    "get_flight_status"
]


GENERATED_TOOLS = [
]


@tool
def fake_tool():
    """
    This is a fake tool that does nothing.
    If is used so that the file will import the necessary libraries from:
        import inspect
        import requests
        from langchain.tools import tool

    """
    frame = inspect.currentframe()
    print(frame)
    requests.get("do not delete this call", json=json.loads(""))
    return "fake_tool"


def create_function_from_string(code: str, func_name: str, scope: dict):
    """
    Dynamically create and return a function object from a string of Python code.

    This function executes the given Python source code in a controlled scope and
    retrieves a function by its name.

    """
    exec(code, globals(), scope)
    return scope.get(func_name)


def define_tool_dynamically(
    tool_name: str, tool_docstring: str, arguments_string: str, scope: dict,
    skillberry_context: dict
):
    """
    Define a local tool based on OpenAI parameters definition to be used by the agentic workflow.

    Args:
        tool_name (str): The name of the tool
        tool_docstring (str): The docstring of the tool
        arguments_string (str): The arguments of the tool
        scope (dict): The scope
        skillberry_context (dict): The context that the tool pass during its execution

    Returns (Callable):
        The tool as a callable object   
    """

    # the function will use rest against the tool_service_api to execute the tool
    # with the required parameters
    tool_function_name = re.sub(r"[. ]", "_", tool_name)

    http_headers = flatten_keys(
            {
                SKILLBERRY_CONTEXT: skillberry_context
            }
        )
    logger.info(f"define_tool_dynamically: http_headers: {http_headers}")
    python_code = f"""
import requests
import json
import inspect
from langchain.tools import tool
from utils.tools_service_api import tools_service

@tool
def {tool_function_name} {arguments_string}:
    \"\"\"
    {tool_docstring}
    \"\"\"

    frame = inspect.currentframe()
    args, _, _, values = inspect.getargvalues(frame)
    param_dict = {{arg: values[arg] for arg in args}}
    try:
        # print (f"{{repr({http_headers})}}")
        print(f"Calling tools_service.execute_tool with: {tool_function_name} and parameters: {{param_dict}}")
        return_value = tools_service.execute_tool("{tool_function_name}",param_dict, http_headers=json.loads('{json.dumps(http_headers)}'))
    except Exception as e:
        cleaned_return_value = f"EXCEPTION:Error executing tool: {{e}}"
        print(cleaned_return_value)
        return cleaned_return_value
            
    print (f"return_value from tools_service: {{return_value}}")
    cleaned_return_value = return_value.strip().replace('"', '')
    print(f'====> returning response from the function: {{cleaned_return_value}}')
    return cleaned_return_value
"""
    _tool = create_function_from_string(python_code, tool_function_name, scope)
    return _tool


def generate_dynamic_tool(tool_name: str, scope: dict, skillberry_context: dict):
    """
    Utility method to translate a SBS tool, given its name, into langchain tool.

    """
    metadata = tools_service.get_tool_manifest(tool_name)

    # print (f"@@@@@@@@\n\n  {(json.dumps(metadata, indent=4))} \n\n@@@@@@@@")

    arguments_string = generate_function_arguments_from_metadata(metadata)

    # print (f"@@@@@@@@\n\n {arguments_string} \n\n@@@@@@@@")

    tool_docstring = generate_function_docstring_from_metadata(metadata)

    # print (f"@@@@@@@@\n\n  {tool_docstring} \n\n@@@@@@@@")

    tool_func = define_tool_dynamically(
        tool_name=tool_name,
        tool_docstring=tool_docstring,
        arguments_string=arguments_string,
        scope=scope,
        skillberry_context=skillberry_context
    )
    return tool_func


def json_schema_to_python_type(json_schema_type: str) -> str:
    # Mapping JSON Schema types to Python types
    type_mapping = {
        "string": "str",
        "str": "str",
        "number": "float",
        "float": "float",
        "integer": "int",
        "int": "int",
        "bool": "bool",
        "boolean": "bool",
        "object": "dict",
        "list": "list",
        "array": "list",
        "datetime": "datetime",
        "null": "None",
        "any": "object",  # 'any' can be mapped to 'object' or 'str', depending on use case
    }

    # Return the corresponding Python type as a string
    return type_mapping.get(json_schema_type, "Unknown")


def generate_function_arguments_from_metadata(metadata: str):
    parsed_info = metadata
    function_arguments = f"("
    parameters = parsed_info["params"]["properties"]
    param_strs = []

    for param_name, param_info in parameters.items():
        param_type = json_schema_to_python_type(param_info["type"])
        param_strs.append(f"{param_name}: {param_type}")

    try:
        returns = parsed_info["returns"]["properties"]
        returns_type = json_schema_to_python_type(returns["type"])
    except Exception as e:
        returns_type = "str"

    function_arguments += ", ".join(param_strs) + f") -> {returns_type}"

    return function_arguments


def generate_function_docstring_from_metadata(metadata: dict) -> str:
    """Generates a Google-style docstring from a parsed function metadata dictionary."""
    parsed_data = metadata
    description = parsed_data.get("description", "")
    params = parsed_data.get("parameters", {}).get("properties", {})

    docstring_lines = [description, ""] if description else []

    if params:
        docstring_lines.append("Args:")
        for param, details in params.items():
            dtype = details.get("type", "unknown").capitalize()
            desc = details.get("description", "")
            docstring_lines.append(f"    {param} ({dtype}): {desc}")

    return "\n".join(docstring_lines)