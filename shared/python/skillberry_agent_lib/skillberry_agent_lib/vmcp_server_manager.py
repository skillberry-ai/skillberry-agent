from typing import Optional, Dict
import logging
import threading
import time

from skillberry_agent_lib.skillberry_store import skillberry_store


# Thread-safe registry for VMCP servers
# Key: env_id, Value: vmcp_data dict
_vmcp_server_registry: Dict[str, Dict] = {}
_registry_lock = threading.Lock()

# Placeholder value to prevent race conditions during server creation
_PLACEHOLDER = {"status": "creating"}

def _wait_for_server_creation(env_id: str, max_wait: float = 30.0, poll_interval: float = 0.1) -> Optional[Dict]:
    """Wait for another thread to finish creating a server.
    
    Args:
        env_id: The environment ID to wait for
        max_wait: Maximum time to wait in seconds (default: 30)
        poll_interval: Time between checks in seconds (default: 0.1)
        
    Returns:
        The created server data dict, or None if timeout
        
    Raises:
        TimeoutError: If server creation doesn't complete within max_wait
    """
    logging.info(f"Server creation in progress for env_id '{env_id}', waiting...")
    waited = 0.0
    
    while waited < max_wait:
        time.sleep(poll_interval)
        waited += poll_interval
        
        with _registry_lock:
            current = _vmcp_server_registry.get(env_id)
            if current and current.get("status") != "creating":
                logging.info(f"Server ready for env_id '{env_id}' after {waited:.2f}s")
                return current
    
    # Timeout - clean up placeholder
    with _registry_lock:
        if env_id in _vmcp_server_registry and _vmcp_server_registry[env_id].get("status") == "creating":
            del _vmcp_server_registry[env_id]
    
    raise TimeoutError(f"Timeout waiting for server creation for env_id '{env_id}' after {max_wait}s")



def get_or_create_vmcp_server(
    skillberry_context: Dict,
    skill_uuid: Optional[str] = None
):
    """Create or retrieve VMCP server with direct skill UUID.
    
    This function manages VMCP servers per env_id with thread-safe registry.
    It accepts a pre-resolved skill UUID directly.

    Args:
        skillberry_context: The context for the MCP server (must not be None)
        skill_uuid: Pre-resolved skill UUID (optional)
        
    Returns:
        VirtualMcpServer data dict with keys: name, description, port, tools
        
    Raises:
        ValueError: If skillberry_context is None or missing env_id, or if server creation fails
    """
    # Validate context is not None
    if skillberry_context is None:
        raise ValueError("skillberry_context cannot be None")
    
    # Validate env_id exists
    if "env_id" not in skillberry_context:
        raise ValueError(
            f"skillberry_context must contain 'env_id' key. "
            f"Received: {skillberry_context}"
        )
    
    env_id = skillberry_context["env_id"]
    
    # Check if server already exists for this env_id
    with _registry_lock:
        if env_id in _vmcp_server_registry:
            existing_server = _vmcp_server_registry[env_id]
            
            # If placeholder, another thread is creating - wait for it
            if existing_server.get("status") == "creating":
                return _wait_for_server_creation(env_id)
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
        # Step 1: Generate server name based on env_id
        server_name = f"vmcp-server-{env_id}"
        logging.info(f"Creating VMCP server '{server_name}' with skill_uuid: {skill_uuid}")
        
        # Step 2: Check if server already exists in Skillberry Tools Service
        vmcp_server_info = None
        try:
            vmcp_server_info = skillberry_store.get_vmcp_server_details(name=server_name)
            logging.info(f"Found existing VMCP server '{server_name}' in Tools Service")
            
            # Validate skill UUID match if both are specified
            existing_skill_uuid = vmcp_server_info.get("skill_uuid")
            if existing_skill_uuid and skill_uuid and existing_skill_uuid != skill_uuid:
                logging.warning(
                    f"VMCP server '{server_name}' exists with skill_uuid '{existing_skill_uuid}', "
                    f"but requested skill_uuid is '{skill_uuid}'. "
                    f"Reusing existing server (skill mismatch detected)."
                )
        except Exception as e:
            logging.debug(f"No existing VMCP server found (or error): {e}")
            logging.info(f"Will create new VMCP server '{server_name}'")
        
        # Step 3: Create server if it doesn't exist
        if vmcp_server_info is None:
            vmcp_response = skillberry_store.add_vmcp_server(
                name=server_name,
                description=f"VMCP Server for env_id: {env_id}",
                skill_uuid=skill_uuid,
                skillberry_context=skillberry_context
            )
            logging.info(f"VMCP server created with response: {vmcp_response}")
            
            # Get full server details including runtime information
            vmcp_server_info = skillberry_store.get_vmcp_server_details(name=server_name)
            logging.info(f"Retrieved VMCP server info: {vmcp_server_info}")
        
        # Step 4: Extract necessary fields for VirtualMcpServer
        vmcp_data = {
            "uuid": vmcp_server_info.get("uuid"),  # Store UUID for future operations
            "name": vmcp_server_info.get("name") or server_name,
            "description": vmcp_server_info.get("description") or f"VMCP Server for {env_id}",
            "port": vmcp_server_info.get("port"),
            "skill_uuid": vmcp_server_info.get("skill_uuid"),
            "env_id": env_id
        }
        logging.info(f"Constructed VMCP data: {vmcp_data}")
        
        # Step 5: Update registry with actual server data
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
        skillberry_context: Context dictionary containing the context (must not be None)
        
    Returns:
        True if server was removed from registry, False if not found in registry
        
    Raises:
        ValueError: If skillberry_context is None or missing env_id
        
    Note:
        Even if the server is not in the local registry, this function will still
        attempt to remove it from the Skillberry Tools Service.
    """
    from skillberry_agent_lib.skillberry_store import skillberry_store
    
    # Validate context is not None
    if skillberry_context is None:
        raise ValueError("skillberry_context cannot be None")
    
    # Validate env_id exists
    if "env_id" not in skillberry_context:
        raise ValueError(
            f"skillberry_context must contain 'env_id' key. "
            f"Received: {skillberry_context}"
        )
    
    env_id = skillberry_context["env_id"]
    server_name = f"vmcp-server-{env_id}"
    registry_removed = False
    vmcp_uuid = None
    
    # Remove from local registry and get UUID if available
    with _registry_lock:
        if env_id in _vmcp_server_registry:
            vmcp_uuid = _vmcp_server_registry[env_id].get('uuid')
            del _vmcp_server_registry[env_id]
            logging.info(f"Removed VMCP server for env_id '{env_id}' from local registry")
            registry_removed = True
        else:
            logging.warning(f"No VMCP server found in local registry for env_id '{env_id}'")
    
    # Remove from Skillberry Tools Service - prefer UUID-based removal
    try:
        if vmcp_uuid:
            skillberry_store.remove_vmcp_server_by_uuid(vmcp_uuid)
            logging.info(f"Removed VMCP server by UUID '{vmcp_uuid}' from Skillberry Tools Service")
        else:
            skillberry_store.remove_vmcp_server(name=server_name)
            logging.info(f"Removed VMCP server by name '{server_name}' from Skillberry Tools Service")
    except Exception as e:
        logging.warning(f"Failed to remove VMCP server from Tools Service: {e}")
    
    return registry_removed


def clear_vmcp_servers():
    """Clear all VMCP servers from registry.
    
    Note: This only clears local registry, not Skillberry Tools Service.
    Useful for testing or cleanup.
    """
    with _registry_lock:
        _vmcp_server_registry.clear()
        logging.info("Cleared all VMCP servers from registry")


# Made with Bob
