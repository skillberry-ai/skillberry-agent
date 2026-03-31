import json

from pydantic import BaseModel, Field


class VirtualMcpServer(BaseModel):
    """
    Represents a virtual MCP server.

    """
    name: str = Field(description="The name of the virtual MCP server.")
    description: str = Field(description="A description of the virtual MCP server.")
    port: int = Field(description="he port on which the virtual MCP server is running.")

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
        return "\n".join(lines)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VirtualMcpServer):
            return False
        return self.name == other.name and self.port == other.port
