import logging

import blueberry_tools_maker_sdk
from config.config_ui import config

logger = logging.getLogger(__name__)


class ToolsMaker:
    def __init__(self, base_url=None):
        self.base_url = base_url if base_url else tools_maker_base_url
        configuration = blueberry_tools_maker_sdk.Configuration(host=self.base_url)
        with blueberry_tools_maker_sdk.ApiClient(configuration) as api_client:
            self.api_instance = blueberry_tools_maker_sdk.ApiApi(api_client)

    def check_communication(self):
        """
        Check connectivity status into the tools' maker.

        Returns:
            bool: whether connectivity succeeded

        """
        logger.info("check_communication called")
        try:
            self.api_instance.api_validate_tool_validate_tool_post("test")

        except blueberry_tools_maker_sdk.ApiException as e:
            if e.status == 404 or e.status == 500:
                pass
            else:
                logger.error(f"Tools maker is not reachable: {e}")
                return False
        logger.info("Tools maker is up and running.")
        return True

    def generate_tool(
        self,
        tool_name: str,
        tool_description: str,
        usage_examples: str,
        original_prompt: str = None,
    ) -> bool:
        """
        Request blueberry tools maker to generate a tool with the given name, description and examples using
        blueberry-tools-maker-sdk.

        Parameters:
            tool_name (str): tool name
            tool_description (str): tool description
            usage_examples (str): tool usage examples
            original_prompt (str): original prompt to be used for tool generation

        Returns:
            bool: whether operation succeed

        Raises:
            Exception: Any failure occurred during execution

        """
        logger.info(f"generate_tool_tools_maker called for tool: {tool_name}")

        api_response = self.api_instance.api_generate_tool_generate_tool_post(
            tool_name=tool_name,
            tool_description=tool_description,
            usage_examples=usage_examples,
            original_prompt=original_prompt,
        )
        logger.debug(
            "The response of ApiApi->api_generate_tool_generate_tool_tool_name_post {api_response}:\n"
        )
        return api_response


# Load configuration and set up the tools maker API
tools_maker_base_url = config.get("tools_maker_base_url")
tools_maker = ToolsMaker(tools_maker_base_url)
