import json

from typing import List
from pydantic import BaseModel, Field


class VirtualMcpServer(BaseModel):
    """
    Represents a virtual MCP server.

    """
    name: str = Field(description="The name of the virtual MCP server.")
    description: str = Field(description="A description of the virtual MCP server.")
    port: int = Field(description="he port on which the virtual MCP server is running.")
    tools: List[str] = Field(description="A list of tool UUIDs registered with the virtual MCP server.")

    def __str__(self) -> str:
        lines = [
            "VirtualMcpServer",
        ]
        if self.name is not None:
            lines.append(f"name: {self.name}")
        if self.description is not None:
            lines.append(f"description: {self.description}")
        if self.port is not None:
            lines.append(f"port: {self.port}")
        if self.tools is not None:
            lines.append(f"tools:\n{json.dumps(self.tools, indent=2)}")
        return "\n".join(lines)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VirtualMcpServer):
            return False
        return self.name == other.name and self.port == other.port
