import logging
from typing import Dict, List
import uuid

from data_model.virtual_mcp_server import VirtualMcpServer
from utils.tools_service_api import tools_service


logger = logging.getLogger(__name__)


class VirtualMcpServerManager:
    """
    Manages virtual MCP servers for the Skillberry Agent.

    This class provides functionality to create, manage, and remove virtual MCP servers.
    """

    def __init__(self):
        """
        Initialize the virtual MCP server manager.

        """
        # env_id -> server map
        self.servers: Dict[str, VirtualMcpServer] = {}

    def add_server(self, skillberry_context: Dict, tools: List[str]) -> VirtualMcpServer:
        """
        Add a new virtual MCP server and add it to the list.

        Args:
            skillberry_context: The context of the MCP server
            tools: List of tool names to include in the server.

        Returns:
            VirtualMcpServer: The created virtual MCP server instance.

        """
        name = f"tau-{uuid.uuid4().hex[:4]}"
        logger.info(f"Adding vmcp_server: '{name}'")

        tools_service.add_vmcp_server(name=name, description="description", tools=tools,
                                      skillberry_context=skillberry_context)
        vmcp_server_info = tools_service.get_vmcp_server_details(name=name)

        server = VirtualMcpServer(**vmcp_server_info)

        env_id = skillberry_context["env_id"]
        logger.info(f"Add Mapping {env_id} <-> server '{name}'")
        self.servers[env_id] = server

        logger.info(f"Added and started new vmcp_server: {name} on port {server.port}")
        return server

    def remove_server(self, skillberry_context: Dict):
        """
        Remove a virtual MCP server and delete it from servers list

        Args:
            skillberry_context: The context of the MCP server

        Raises:
            ValueError: If the virtual MCP server is not found.
        """
        env_id = skillberry_context["env_id"]

        if env_id in self.servers:
            server = self.servers[env_id]
            name = server.name
            logger.info(f"Removing vmcp_server: '{name}'")
            tools_service.remove_vmcp_server(name)

            logger.info(f"Remove Mapping {env_id} <-> server '{name}'")
            del self.servers[env_id]
        else:
            raise ValueError(f"Mapping {env_id} <-> server '{name}' not found")

    def get_server(self, skillberry_context: Dict) -> VirtualMcpServer:
        """
        Get detailed information about a virtual MCP server.

        Args:
            skillberry_context: The context of the MCP server

        Returns:
            VirtualMcpServer: The virtual MCP server instance.

        """
        env_id = skillberry_context["env_id"]

        return self.servers[env_id]


# FIXME: make this singleton concurrent robust (and inside function) -
# consider to use threading.RLock() around servers manipulation functions
vmsm = VirtualMcpServerManager()
