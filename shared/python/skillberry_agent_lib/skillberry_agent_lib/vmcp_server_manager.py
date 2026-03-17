from typing import Optional, Dict
import logging
import requests


def resolve_skill_uuid(
    skill_name: Optional[str], skill_uuid: Optional[str]) -> Optional[str]:
    """
    Internal helper method to resolve skill UUID based on provided parameters.
    
    Args:
        skill_name: Name of the skill to resolve
        skill_uuid: Direct UUID specification
        enable_skill_search: Whether to enable runtime skill search
        
    Returns:
        Resolved skill UUID or None
        
    Raises:
        NotImplementedError: If enable_skill_search is True (not yet implemented)
    """
    if skill_uuid:
        # Build-time mode: Direct UUID specification
        logging.info(f"[BUILD-TIME] Using explicit skill UUID: {skill_uuid}")
        return skill_uuid
        
    elif skill_name:
        # Build-time mode: Get skill by name
        logging.info(f"[BUILD-TIME] Getting skill by name: '{skill_name}'")
        try:
            from skillberry_agent_lib.skillberry_api import skillberry_api
            skill_data = skillberry_api.get_skill(skill_name)
            if skill_data:
                resolved_skill_uuid = skill_data.get("uuid")
                if resolved_skill_uuid:
                    logging.info(f"[BUILD-TIME] Resolved skill '{skill_name}' to UUID: {resolved_skill_uuid}")
                    return resolved_skill_uuid
                else:
                    logging.warning(f"Skill '{skill_name}' found but has no UUID, creating VMCP without skill")
                    return None
            else:
                logging.warning(f"No skill data returned for skill name: '{skill_name}', creating VMCP without skill")
                return None
        except requests.exceptions.HTTPError as e:
            logging.warning(f"HTTP error while getting skill '{skill_name}': {e}. Creating VMCP without skill")
            return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request error while getting skill '{skill_name}': {e}. Creating VMCP without skill")
            return None
        except Exception as e:
            logging.warning(f"Unexpected error while getting skill '{skill_name}': {e}. Creating VMCP without skill")
            return None
            
    else:
        # Fallback mode: Use domain-based search (backward compatibility)
        logging.warning("[DEFAULT MODE] No skill specified, using domain-based search")
        search_term = "airline"  # Default search term
        logging.info(f"Searching for skill with search term: '{search_term}'")
        try:
            from skillberry_agent_lib.skillberry_api import skillberry_api
            resolved_skill_uuid = skillberry_api.find_skill_uuid_by_search(search_term)
            if resolved_skill_uuid:
                logging.info(f"Found skill UUID: {resolved_skill_uuid} for search term: '{search_term}'")
                return resolved_skill_uuid
            else:
                logging.warning(f"No skill found for search term: '{search_term}', creating VMCP without skill")
                return None
        except requests.exceptions.HTTPError as e:
            logging.warning(f"HTTP error while searching for skill with term '{search_term}': {e}. Creating VMCP without skill")
            return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request error while searching for skill with term '{search_term}': {e}. Creating VMCP without skill")
            return None
        except Exception as e:
            logging.warning(f"Unexpected error while searching for skill with term '{search_term}': {e}. Creating VMCP without skill")
            return None


def create_vmcp_server(skillberry_context: Optional[Dict], skill_uuid: Optional[str]):
    """Create VMCP server with given skill UUID.
    
    This function creates a singleton VMCP server.

    Args:
        skillberry_context: The context for the MCP server (can be None)
        skill_uuid: UUID of skill to use, or None for no skill
        
    Returns:
        VirtualMcpServer instance
        
    Raises:
        ValueError: If server exists with different skill_uuid
    """
    from skillberry_agent_lib.skillberry_api import skillberry_api

    # Handle None skillberry_context
    if skillberry_context is None:
        logging.warning("skillberry_context is None, using default context")
        skillberry_context = {"env_id": "default"}

    # TODO (weit) hard code
    server_name = "my-vmcp-server"
    logging.info(f"Creating VMCP server '{server_name}' with skill_uuid: {skill_uuid}")
    
    # Check if server already exists
    vmcp_server_info = None
    try:
        vmcp_server_info = skillberry_api.get_vmcp_server_details(name=server_name)
        logging.info(f"Found existing VMCP server '{server_name}'")
        
        # # Check if existing server has different skill_uuid
        # existing_skill_uuid = vmcp_server_info.get("skill_uuid")
        # if existing_skill_uuid and skill_uuid and existing_skill_uuid != skill_uuid:
        #     raise ValueError(
        #         f"VMCP server '{server_name}' already exists with skill_uuid '{existing_skill_uuid}', "
        #         f"but requested skill_uuid is '{skill_uuid}'. "
        #         f"Please remove the existing server first or use the same skill_uuid."
        #     )
        
        logging.info(f"Reusing existing VMCP server '{server_name}'")
    except ValueError:
        # Re-raise ValueError for UUID mismatch
        raise
    except Exception as e:
        logging.debug(f"No existing VMCP server found (or error): {e}")
        logging.info(f"Will create new VMCP server '{server_name}'")
    
    # If server doesn't exist, create it
    if vmcp_server_info is None:
        # Create VMCP server
        vmcp_response = skillberry_api.add_vmcp_server(
            name=server_name,
            description="Skillberry MCP Server (singleton)",
            skill_uuid=skill_uuid,
            skillberry_context=skillberry_context
        )
        logging.info(f"VMCP server created with response: {vmcp_response}")
        
        # Get full server details including runtime information
        vmcp_server_info = skillberry_api.get_vmcp_server_details(name=server_name)
        logging.info(f"Retrieved VMCP server info: {vmcp_server_info}")
    
    # Extract necessary fields for VirtualMcpServer
    vmcp_data = {
        "name": vmcp_server_info.get("name") or server_name,
        "description": vmcp_server_info.get("description") or "Proxy MCP Server",
        "port": vmcp_server_info.get("port"),
        "tools": vmcp_server_info.get("runtime", {}).get("tools", [])
    }
    logging.info(f"Constructed VMCP data: {vmcp_data}")
    
    # Return the vmcp_data dict instead of VirtualMcpServer object
    # since VirtualMcpServer is defined elsewhere
    logging.info(f"Successfully created VMCP server on port {vmcp_data.get('port')}")
    
    return vmcp_data

# Made with Bob
