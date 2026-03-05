import logging
from typing import Dict, List, Optional
import uuid

from data_model.virtual_mcp_server import VirtualMcpServer
from utils.skillberry_api import skillberry_api


logger = logging.getLogger(__name__)


class VirtualMcpServerManager:
    """
    Manages virtual MCP servers for the Skillberry Agent.

    This class provides functionality to create, manage, and remove virtual MCP servers.
    Supports both tool-list and skill-based approaches.
    """

    def __init__(self):
        """
        Initialize the virtual MCP server manager.

        """
        # Single server instance (singleton pattern)
        self.server: Optional[VirtualMcpServer] = None
        self.server_skill_uuid: Optional[str] = None

    def remove_server(self, skillberry_context: Dict):
        """
        Remove the singleton virtual MCP server

        Args:
            skillberry_context: The context of the MCP server

        Raises:
            ValueError: If the virtual MCP server is not found.
        """
        # TODO (weit) hard code
        server_name = "proxy-vmcp-server"

        if self.server is not None:
            logger.info(f"Removing singleton vmcp_server: {server_name} on port {self.server.port}")
            skillberry_api.remove_vmcp_server(name=server_name)
            logger.info(f"Removed singleton vmcp_server: {server_name}")

            # Clear singleton references
            self.server = None
            self.server_skill_uuid = None
        else:
            raise ValueError(f"No singleton server found to remove")

    def get_server(self, skillberry_context: Dict) -> VirtualMcpServer:
        """
        Get the singleton virtual MCP server.

        Args:
            skillberry_context: The context of the MCP server

        Returns:
            VirtualMcpServer: The virtual MCP server instance.

        Raises:
            KeyError: If no server exists

        """
        if self.server is None:
            raise KeyError("No singleton server exists")
        
        return self.server


# FIXME: make this singleton concurrent robust (and inside function) -
# consider to use threading.RLock() around servers manipulation functions
vmsm = VirtualMcpServerManager()
