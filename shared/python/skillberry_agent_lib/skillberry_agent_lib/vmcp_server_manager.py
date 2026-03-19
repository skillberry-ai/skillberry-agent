from typing import Optional, Dict
import logging
import threading


# Thread-safe registry for VMCP servers
# Key: env_id, Value: vmcp_data dict
_vmcp_server_registry: Dict[str, Dict] = {}
_registry_lock = threading.Lock()

# Placeholder value to prevent race conditions during server creation
_PLACEHOLDER = {"status": "creating"}


def create_vmcp_server(
    skillberry_context: Optional[Dict],
    skill_uuid: Optional[str] = None,
    skill_name: Optional[str] = None,
    skill_search_term: Optional[str] = None
):
    """Create or retrieve VMCP server with unified skill resolution.
    
    This function manages VMCP servers per env_id with thread-safe registry.
    It uses the unified get_skill_uuid() method for skill resolution.

    Args:
        skillberry_context: The context for the MCP server (can be None)
        skill_uuid: Direct UUID specification (highest priority)
        skill_name: Skill name to resolve to UUID (medium priority)
        skill_search_term: Search term to find skill (lowest priority)
        
    Returns:
        VirtualMcpServer data dict with keys: name, description, port, tools
        
    Raises:
        ValueError: If skill resolution fails or server creation fails
    """
    from skillberry_agent_lib.skillberry_api import skillberry_api

    # Handle None skillberry_context
    if skillberry_context is None:
        logging.warning("skillberry_context is None, using default context")
        skillberry_context = {"env_id": "default"}
    
    env_id = skillberry_context.get("env_id", "default")
    
    # Check if server already exists for this env_id
    with _registry_lock:
        if env_id in _vmcp_server_registry:
            existing_server = _vmcp_server_registry[env_id]
            
            # If placeholder, another thread is creating - wait and retry
            if existing_server.get("status") == "creating":
                logging.info(f"Server creation in progress for env_id '{env_id}', waiting...")
            else:
                logging.info(f"Reusing existing VMCP server for env_id '{env_id}'")
                return existing_server
        else:
            # Place placeholder to prevent race conditions
            _vmcp_server_registry[env_id] = _PLACEHOLDER
            logging.info(f"Placed placeholder for env_id '{env_id}'")
    
    # If we placed the placeholder, we're responsible for creating the server
    # Perform network calls OUTSIDE the lock to prevent deadlock
    try:
        # Step 1: Resolve skill UUID using unified method
        resolved_skill_uuid = None
        if skill_uuid or skill_name or skill_search_term:
            try:
                resolved_skill_uuid = skillberry_api.get_skill_uuid(
                    skill_uuid=skill_uuid,
                    skill_name=skill_name,
                    skill_search_term=skill_search_term
                )
                logging.info(f"Resolved skill UUID: {resolved_skill_uuid}")
            except ValueError as e:
                logging.warning(f"Skill resolution failed: {e}. Creating VMCP without skill")
                resolved_skill_uuid = None
        else:
            logging.info("No skill parameters provided, creating VMCP without skill")
        
        # Step 2: Generate server name based on env_id
        server_name = f"vmcp-server-{env_id}"
        logging.info(f"Creating VMCP server '{server_name}' with skill_uuid: {resolved_skill_uuid}")
        
        # Step 3: Check if server already exists in Skillberry Tools Service
        vmcp_server_info = None
        try:
            vmcp_server_info = skillberry_api.get_vmcp_server_details(name=server_name)
            logging.info(f"Found existing VMCP server '{server_name}' in Tools Service")
            
            # Validate skill UUID match if both are specified
            existing_skill_uuid = vmcp_server_info.get("skill_uuid")
            if existing_skill_uuid and resolved_skill_uuid and existing_skill_uuid != resolved_skill_uuid:
                logging.warning(
                    f"VMCP server '{server_name}' exists with skill_uuid '{existing_skill_uuid}', "
                    f"but requested skill_uuid is '{resolved_skill_uuid}'. "
                    f"Reusing existing server (skill mismatch detected)."
                )
        except Exception as e:
            logging.debug(f"No existing VMCP server found (or error): {e}")
            logging.info(f"Will create new VMCP server '{server_name}'")
        
        # Step 4: Create server if it doesn't exist
        if vmcp_server_info is None:
            vmcp_response = skillberry_api.add_vmcp_server(
                name=server_name,
                description=f"VMCP Server for env_id: {env_id}",
                skill_uuid=resolved_skill_uuid,
                skillberry_context=skillberry_context
            )
            logging.info(f"VMCP server created with response: {vmcp_response}")
            
            # Get full server details including runtime information
            vmcp_server_info = skillberry_api.get_vmcp_server_details(name=server_name)
            logging.info(f"Retrieved VMCP server info: {vmcp_server_info}")
        
        # Step 5: Extract necessary fields for VirtualMcpServer
        vmcp_data = {
            "name": vmcp_server_info.get("name") or server_name,
            "description": vmcp_server_info.get("description") or f"VMCP Server for {env_id}",
            "port": vmcp_server_info.get("port"),
            "tools": vmcp_server_info.get("runtime", {}).get("tools", []),
            "skill_uuid": vmcp_server_info.get("skill_uuid"),
            "env_id": env_id
        }
        logging.info(f"Constructed VMCP data: {vmcp_data}")
        
        # Step 6: Update registry with actual server data
        with _registry_lock:
            _vmcp_server_registry[env_id] = vmcp_data
            logging.info(f"Registered VMCP server for env_id '{env_id}' on port {vmcp_data.get('port')}")
        
        return vmcp_data
        
    except Exception as e:
        # Clean up placeholder on failure
        with _registry_lock:
            if env_id in _vmcp_server_registry and _vmcp_server_registry[env_id].get("status") == "creating":
                del _vmcp_server_registry[env_id]
                logging.error(f"Removed placeholder for env_id '{env_id}' due to creation failure")
        
        logging.error(f"Failed to create VMCP server for env_id '{env_id}': {e}")
        raise ValueError(f"VMCP server creation failed: {e}") from e


def remove_vmcp_server(skillberry_context: Dict) -> bool:
    """Remove VMCP server from both local registry and Skillberry Tools Service.
    
    This function performs a complete cleanup:
    1. Removes from local registry
    2. Removes from Skillberry Tools Service
    Args:
        skillberry_context: Context dictionary containing the context
        
        
    Returns:
        True if server was removed from registry, False if not found in registry
        
    Note:
        Even if the server is not in the local registry, this function will still
        attempt to remove it from the Skillberry Tools Service.
    """
    from skillberry_agent_lib.skillberry_api import skillberry_api
    
    env_id = skillberry_context.get("env_id", "default")
    server_name = f"vmcp-server-{env_id}"
    registry_removed = False
    
    # Remove from local registry
    with _registry_lock:
        if env_id in _vmcp_server_registry:
            del _vmcp_server_registry[env_id]
            logging.info(f"Removed VMCP server for env_id '{env_id}' from local registry")
            registry_removed = True
        else:
            logging.warning(f"No VMCP server found in local registry for env_id '{env_id}'")
    
    # Remove from Skillberry Tools Service
    try:
        skillberry_api.remove_vmcp_server(name=server_name)
        logging.info(f"Removed VMCP server '{server_name}' from Skillberry Tools Service")
    except Exception as e:
        logging.warning(f"Failed to remove VMCP server '{server_name}' from Tools Service: {e}")
    
    return registry_removed


def list_vmcp_servers() -> Dict[str, Dict]:
    """List all registered VMCP servers.
    
    Returns:
        Dictionary mapping env_id to server data
    """
    with _registry_lock:
        # Return copy to prevent external modification
        return {
            env_id: server.copy()
            for env_id, server in _vmcp_server_registry.items()
            if server.get("status") != "creating"
        }


def clear_vmcp_servers():
    """Clear all VMCP servers from registry.
    
    Note: This only clears local registry, not Skillberry Tools Service.
    Useful for testing or cleanup.
    """
    with _registry_lock:
        _vmcp_server_registry.clear()
        logging.info("Cleared all VMCP servers from registry")


# Made with Bob
