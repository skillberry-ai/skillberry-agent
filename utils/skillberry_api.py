import logging
from typing import Optional
import requests

from config.config_ui import config


logger = logging.getLogger(__name__)


class SkillberryAPI:
    """Client for interacting with the Skillberry Tools Store API.
    
    This is a minimal version containing only methods used by skillberry-agent.
    The shared library (skillberry_agent_lib) has its own complete implementation.
    """
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url if base_url else tools_service_base_url
        self.session = requests.Session()

    def check_communication(self):
        """
        Check connectivity status to the Skillberry API.

        Returns:
            bool: whether connectivity succeeded

        """
        logger.info("check_communication called")
        try:
            # Try to search for skills as a connectivity test
            response = self.session.get(f"{self.base_url}/search/skills", params={"search_term": "test", "max_number_of_results": 1})
            response.raise_for_status()
            logger.info("Skillberry API is up and running.")
            return True
        except Exception as e:
            logger.error(f"Skillberry API is not reachable: {e}")
            return False

    def remove_vmcp_server(self, name: str):
        """Remove a virtual MCP server

        Args:
            name: The name of the virtual MCP server to remove.

        Returns:
            dict: Success message

        Raises:
            Exception: Any failure occurred during execution.

        """
        logger.info(f"remove_vmcp_server called for: {name}")
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        response = self.session.delete(
            f"{self.base_url}/vmcp_servers/{name}",
            headers=headers
        )
        response.raise_for_status()
        return response.json()


# TODO (weit): hardcode
tools_service_base_url = "http://localhost:8000"
skillberry_api = SkillberryAPI(tools_service_base_url)
