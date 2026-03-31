import asyncio
import logging
from typing import Any, Dict, List, Optional
import requests

from skillberry_agent_lib.utils import SKILLBERRY_CONTEXT, flatten_keys, extract_base_url


logger = logging.getLogger(__name__)


class SkillberryAPI:
    """Client for interacting with the Skillberry Tools Store API."""
    
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

    def search_skills(
        self,
        search_term: str,
        max_number_of_results: int = 5,
        similarity_threshold: float = 1.0,
    ):
        """
        Search for skills matching the given search term.

        Parameters:
            search_term (str): Search term to find matching skills
            max_number_of_results (int): Maximum number of results to return
            similarity_threshold (float): Similarity threshold for the search

        Returns:
            list: List of matching skills with name and similarity score

        Raises:
            Exception: Any failure occurred during execution

        """
        logger.info(f"search_skills called with search_term: '{search_term}', max_results: {max_number_of_results}, threshold: {similarity_threshold}")
        params = {
            "search_term": search_term,
            "max_number_of_results": max_number_of_results,
            "similarity_threshold": similarity_threshold,
        }
        response = self.session.get(f"{self.base_url}/search/skills", params=params)
        response.raise_for_status()
        results = response.json()
        logger.info(f"search_skills returned {len(results)} results: {results}")
        return results

    def get_skill(self, skill_name: str):
        """
        Retrieve the skill with the given name.

        Parameters:
            skill_name (str): The name of the skill

        Returns:
            dict: The skill object with full details including UUID

        Raises:
            Exception: Any failure occurred during execution

        """
        logger.info(f"get_skill called for skill: {skill_name}")
        response = self.session.get(f"{self.base_url}/skills/{skill_name}")
        response.raise_for_status()
        skill_data = response.json()
        logger.info(f"get_skill returned skill with UUID: {skill_data.get('uuid')}, name: {skill_data.get('name')}")
        logger.debug(f"Full skill data: {skill_data}")
        return skill_data

    def find_skill_uuid_by_search(self, search_term: str):
        """
        Find a skill UUID by searching for a skill matching the search term.
        Returns the UUID of the first matching skill, or None if no match found.

        Parameters:
            search_term (str): Search term to find matching skill

        Returns:
            str or None: UUID of the first matching skill, or None if not found

        """
        logger.info(f"find_skill_uuid_by_search called with search_term: '{search_term}'")
        try:
            # Search for skills matching the term
            search_results = self.search_skills(search_term, max_number_of_results=1)
            
            if not search_results:
                logger.warning(f"No skills found matching search term: '{search_term}'")
                return None
            
            # Get the first matching skill name
            first_match = search_results[0]
            skill_name = first_match.get("filename")
            similarity_score = first_match.get("similarity_score", 0.0)
            
            logger.info(f"Found matching skill: '{skill_name}' with similarity score: {similarity_score}")
            
            # Get the full skill details to retrieve UUID
            skill_data = self.get_skill(skill_name)
            skill_uuid = skill_data.get("uuid")
            
            logger.info(f"Retrieved skill UUID: {skill_uuid} for skill: '{skill_name}'")
            return skill_uuid
            
        except Exception as e:
            logger.error(f"Error finding skill UUID for search term '{search_term}': {e}")
            return None

    def add_vmcp_server(self, name: str, description: str, skill_uuid: Optional[str] = None,
                        skillberry_context: Optional[Dict] = None):
        """
        Creates a vmcp server on BTS with given parameters.

        Parameters:
            name (str): Name of vmcp server
            description (str): Description of vmcp server
            skill_uuid (str): UUID of the skill to expose via the vmcp server (Optional)
            skillberry_context (dict): The context to be passed (Optional)

        Returns:
            dict: Success message with the server name, uuid, and port.

        Raises:
            Exception: Any failure occurred during execution.
        """
        logger.info(f"add_vmcp_server called for name: {name}, skill_uuid: {skill_uuid}")

        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        if skillberry_context:
            headers.update(
                flatten_keys(
                    {
                        SKILLBERRY_CONTEXT: skillberry_context
                    }
                )
            )

        # Build query parameters - ALL parameters are query params, not in body
        params = {}
        if name:
            params["name"] = name
        if description:
            params["description"] = description
        if skill_uuid:
            params["skill_uuid"] = skill_uuid
        
        # Try to create the server
        response = self.session.post(
            f"{self.base_url}/vmcp_servers/",
            headers=headers,
            params=params
        )
        
        # If server already exists (409 Conflict), get its details instead
        if response.status_code == 409:
            logger.info(f"VMCP server '{name}' already exists, retrieving existing server details")
            try:
                existing_server = self.get_vmcp_server_details(name=name)
                logger.info(f"Reusing existing VMCP server: {existing_server}")
                return existing_server
            except Exception as e:
                logger.error(f"Failed to retrieve existing server '{name}': {e}")
                response.raise_for_status()  # Raise the original 409 error
        
        response.raise_for_status()
        return response.json()

    def get_vmcp_server_details(self, name: str):
        """Get detailed information about a virtual MCP server.

        Retrieves comprehensive details about the specified virtual MCP server,
        including its configuration, port, and available tools.

        Args:
            name: The name of the virtual MCP server.

        Returns:
            dict: Detailed information about the virtual MCP server.

        Raises:
            Exception: Any failure occurred during execution.
        """
        logger.info(f"get_vmcp_server_details called for: {name}")
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        response = self.session.get(
            f"{self.base_url}/vmcp_servers/{name}",
            headers=headers
        )
        response.raise_for_status()
        return response.json()

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

    def get_mcp_tools(self, port: int, server_name: str = "skillberry-tools",
                      tool_interceptors: Optional[List[Any]] = None) -> List[Any]:
        """Get tools from an MCP server via SSE transport.

        Args:
            port: The port number where the MCP server is running
            server_name: Name identifier for the MCP server (default: "skillberry-tools")
            tool_interceptors: Optional list of tool interceptors to use with the MCP client

        Returns:
            list: List of tools available from the MCP server

        Raises:
            Exception: Any failure occurred during execution.

        """
        logger.info(f"get_mcp_tools called for port: {port}, server_name: {server_name}")
        
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            
            # Construct the MCP server URL
            mcp_server_base_url = f"{extract_base_url(self.base_url)}:{port}"
            logger.info(f"Connecting to MCP server at: {mcp_server_base_url}/sse")
            
            # Build client configuration
            client_config = {
                server_name: {
                    "url": f"{mcp_server_base_url}/sse",
                    "transport": "sse",
                }
            }
            
            # Create MCP client with optional interceptors
            if tool_interceptors:
                client = MultiServerMCPClient(client_config, tool_interceptors=tool_interceptors)
            else:
                client = MultiServerMCPClient(client_config)
            
            # Get tools from the MCP server
            # Check if we're already in an event loop (e.g., FastAPI context)
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context - run in a thread to avoid event loop conflict
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, client.get_tools())
                    tools = future.result()
            except RuntimeError:
                # No event loop running - safe to use asyncio.run()
                tools = asyncio.run(client.get_tools())
            
            logger.info(f"Retrieved {len(tools)} tools from MCP server: {[getattr(t, 'name', 'unknown') for t in tools]}")
            
            return tools
            
        except Exception as e:
            logger.error(f"Error getting MCP tools from port {port}: {e}")
            raise

    def get_mcp_prompts(self, port: int, server_name: str = "skillberry-tools") -> List[Any]:
        """Get prompts from an MCP server via SSE transport.

        Args:
            port: The port number where the MCP server is running
            server_name: Name identifier for the MCP server (default: "skillberry-tools")

        Returns:
            list: List of prompt objects available from the MCP server

        Raises:
            Exception: Any failure occurred during execution.

        """
        logger.info(f"get_mcp_prompts called for port: {port}, server_name: {server_name}")
        
        try:
            from mcp.client.sse import sse_client
            from mcp import ClientSession
            
            # Construct the MCP server URL
            mcp_server_base_url = f"{extract_base_url(self.base_url)}:{port}"
            mcp_url = f"{mcp_server_base_url}/sse"
            logger.info(f"Connecting to MCP server at: {mcp_url}")
            
            # Use asyncio to fetch prompts
            async def fetch_prompts():
                prompts_list = []
                async with sse_client(mcp_url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        
                        # List available prompts
                        prompts_result = await session.list_prompts()
                        if not prompts_result or not prompts_result.prompts:
                            return []
                        
                        # Fetch the actual content for each prompt
                        for prompt_meta in prompts_result.prompts:
                            try:
                                # Get the full prompt content using get_prompt
                                prompt_result = await session.get_prompt(prompt_meta.name)
                                if prompt_result and prompt_result.messages:
                                    # Extract the content from the messages
                                    for message in prompt_result.messages:
                                        if hasattr(message, 'content'):
                                            content = message.content
                                            # Handle different content types - use getattr to avoid type errors
                                            description = getattr(content, 'text', None)
                                            if description is None:
                                                if isinstance(content, str):
                                                    description = content
                                                else:
                                                    description = str(content)
                                            
                                            # Create a prompt object with the actual content
                                            prompt_obj = type('Prompt', (), {
                                                'name': prompt_meta.name,
                                                'description': description
                                            })()
                                            prompts_list.append(prompt_obj)
                                            break  # Use first message content
                            except Exception as e:
                                logger.warning(f"Failed to get content for prompt '{prompt_meta.name}': {e}")
                                # Fallback to using the metadata description if available
                                if hasattr(prompt_meta, 'description') and prompt_meta.description:
                                    prompts_list.append(prompt_meta)
                
                return prompts_list
            
            # Check if we're already in an event loop (e.g., FastAPI context)
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context - run in a thread to avoid event loop conflict
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, fetch_prompts())
                    prompts = future.result(timeout=30)  # 30 second timeout
            except RuntimeError:
                # No event loop running - safe to use asyncio.run()
                prompts = asyncio.run(fetch_prompts())
            
            logger.info(f"Retrieved {len(prompts)} prompts from MCP server: {[getattr(p, 'name', 'unknown') for p in prompts]}")
            
            return prompts
            
        except Exception as e:
            logger.error(f"Error getting MCP prompts from port {port}: {e}")
            raise


# TODO (weit): hardcode
tools_service_base_url = "http://localhost:8000"
skillberry_api = SkillberryAPI(tools_service_base_url)

# Made with Bob
