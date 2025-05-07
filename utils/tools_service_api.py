import logging

import blueberry_tools_service_sdk
from config.config_ui import config

logger = logging.getLogger(__name__)


# TODO: consider to be consistent across all sdk calls to
# raise an Exception/HTTPException during any adk call failures


# class for blueberry-tools-service-sdk
class ToolsService:
    def __init__(self, base_url=None):
        self.base_url = base_url if base_url else tools_service_base_url
        configuration = blueberry_tools_service_sdk.Configuration(host=self.base_url)
        with blueberry_tools_service_sdk.ApiClient(configuration) as api_client:
            self.manifest_api = blueberry_tools_service_sdk.ManifestApi(api_client)

    def get_tools_service_base_url(self):
        """
        Retrieve the tools service base URL.

        Returns:
            str: The tools service base URL

        """
        return self.base_url

    def check_communication(self):
        """
        Check connectivity status into the tools service.

        Returns:
            bool: whether connectivity succeeded

        """
        logger.info("check_communication called")
        try:
            self.manifest_api.get_manifest_manifests_uid_get("test")

        except blueberry_tools_service_sdk.ApiException as e:
            if e.status == 404:
                pass
            else:
                logger.error(f"Tools service is not reachable: {e}")
                return False
        logger.info("Tools service is up and running.")
        return True

    def get_manifest(self, tool_name: str):
        """
        Retrieve the manifest with the given name using blueberry-tools-service-sdk.

        Parameters:
            tool_name (str): The name of the tool

        Returns:
            dict: the manifest

        """
        logger.info(f"get_manifest called for tool: {tool_name}")
        api_response = self.manifest_api.get_manifest_manifests_uid_get(tool_name)
        return api_response

    def search_tools(self,
                     tool_name: str,
                     tool_description: str,
                     max_numer_of_results: int = 3,
                     similarity_threshold: float = 1.0):
        """
        Invoke a tool denoted by tool_name with given parameters using blueberry-tools-service-sdk.

        Parameters:
            tool_name (str): Name of the tool to invoke
            tool_description (str): Description of the tool to invoke
            max_numer_of_results (int): Maximum number of results to return
            similarity_threshold (float): Similarity threshold for the search

        Returns:
            dict: return value result

        Raises:
            Exception: Any failure occurred during execution

        """
        logger.info(f"execute_tool called for tool: {tool_name}")

        response = self.manifest_api.search_manifest_search_manifests_get(
            search_term=f"{tool_name}: {tool_description}",
            max_number_of_results=max_numer_of_results,
            similarity_threshold=similarity_threshold,
        )
        return response


# Load configuration and set up the tools maker API
tools_service_base_url = config.get("tools_service_base_url")
tools_service = ToolsService(tools_service_base_url)
