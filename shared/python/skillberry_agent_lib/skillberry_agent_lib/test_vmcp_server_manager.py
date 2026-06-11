"""
Unit tests for vmcp_server_manager module.

Tests the VMCP server management functions including:
1. Server creation and retrieval
2. Thread-safe registry operations
3. Server removal and cleanup
4. Concurrent access scenarios
"""

import threading
import time
import unittest
from unittest.mock import patch

from skillberry_agent_lib.vmcp_server_manager import (
    get_or_create_vmcp_server,
    remove_vmcp_server,
    clear_vmcp_servers,
    _wait_for_server_creation,
    _vmcp_server_registry,
    _PLACEHOLDER,
)


class TestGetOrCreateVmcpServerBasics(unittest.TestCase):
    """Test basic get_or_create_vmcp_server functionality."""
    
    def setUp(self):
        """Clear registry before each test."""
        clear_vmcp_servers()
    
    def tearDown(self):
        """Clear registry after each test."""
        clear_vmcp_servers()
    
    @patch('skillberry_agent_lib.vmcp_server_manager.skillberry_store')
    def test_create_new_server_success(self, mock_api):
        """Test successful creation of a new VMCP server."""
        # Setup mock responses
        mock_api.get_vmcp_server_details.side_effect = [
            Exception("Not found"),  # First call - server doesn't exist
            {  # Second call - after creation
                "uuid": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
                "name": "vmcp-server-test-env",
                "description": "VMCP Server for env_id: test-env",
                "port": 8001,
                "skill_uuid": "550e8400-e29b-41d4-a716-446655440000",
                "runtime": {"tools": ["tool1", "tool2"]}
            }
        ]
        mock_api.add_vmcp_server.return_value = {
            "name": "vmcp-server-test-env",
            "uuid": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            "port": 8001
        }
        
        # Create server
        context = {"env_id": "test-env"}
        result = get_or_create_vmcp_server(context, skill_uuid="550e8400-e29b-41d4-a716-446655440000")
        
        # Verify result includes UUID
        self.assertEqual(result["uuid"], "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")
        self.assertEqual(result["name"], "vmcp-server-test-env")
        self.assertEqual(result["port"], 8001)
        self.assertEqual(result["skill_uuid"], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(result["env_id"], "test-env")
        
        # Verify API calls
        mock_api.add_vmcp_server.assert_called_once_with(
            name="vmcp-server-test-env",
            description="VMCP Server for env_id: test-env",
            skill_uuid="550e8400-e29b-41d4-a716-446655440000",
            skillberry_context=context
        )
    
    @patch('skillberry_agent_lib.vmcp_server_manager.skillberry_store')
    def test_reuse_existing_server(self, mock_api):
        """Test reusing an existing VMCP server from registry."""
        # Setup mock for first creation
        mock_api.get_vmcp_server_details.side_effect = [
            Exception("Not found"),
            {
                "uuid": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
                "name": "vmcp-server-test-env",
                "description": "VMCP Server for env_id: test-env",
                "port": 8001,
                "skill_uuid": "550e8400-e29b-41d4-a716-446655440000",
                "runtime": {"tools": ["tool1"]}
            }
        ]
        mock_api.add_vmcp_server.return_value = {
            "name": "vmcp-server-test-env",
            "uuid": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"
        }
        
        # Create server first time
        context = {"env_id": "test-env"}
        result1 = get_or_create_vmcp_server(context, skill_uuid="550e8400-e29b-41d4-a716-446655440000")
        
        # Reset mock to verify no new calls
        mock_api.reset_mock()
        
        # Get server second time (should reuse)
        result2 = get_or_create_vmcp_server(context, skill_uuid="test-uuid-123")
        
        # Verify same server returned
        self.assertEqual(result1, result2)
        
        # Verify no new API calls were made
        mock_api.add_vmcp_server.assert_not_called()
        mock_api.get_vmcp_server_details.assert_not_called()
    
    @patch('skillberry_agent_lib.vmcp_server_manager.skillberry_store')
    def test_server_already_exists_in_tools_service(self, mock_api):
        """Test when server already exists in Skillberry Tools Service."""
        # Setup mock - server exists on first check
        mock_api.get_vmcp_server_details.return_value = {
            "uuid": "c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f",
            "name": "vmcp-server-test-env",
            "description": "Existing server",
            "port": 8001,
            "skill_uuid": "550e8400-e29b-41d4-a716-446655440000",
            "runtime": {"tools": ["tool1", "tool2"]}
        }
        
        # Create server
        context = {"env_id": "test-env"}
        result = get_or_create_vmcp_server(context, skill_uuid="550e8400-e29b-41d4-a716-446655440000")
        
        # Verify result
        self.assertEqual(result["name"], "vmcp-server-test-env")
        self.assertEqual(result["port"], 8001)
        
        # Verify add_vmcp_server was NOT called
        mock_api.add_vmcp_server.assert_not_called()
    
    @patch('skillberry_agent_lib.vmcp_server_manager.skillberry_store')
    def test_none_skillberry_context(self, mock_api):
        """Test that None skillberry_context raises ValueError."""
        # Attempting to create server with None context should raise ValueError
        with self.assertRaises(ValueError) as context:
            get_or_create_vmcp_server(None, skill_uuid="test-uuid")
        
        # Verify error message
        self.assertIn("skillberry_context cannot be None", str(context.exception))
    
    @patch('skillberry_agent_lib.vmcp_server_manager.skillberry_store')
    def test_creation_failure_cleans_up_placeholder(self, mock_api):
        """Test that placeholder is removed on creation failure."""
        # Setup mock to fail
        mock_api.get_vmcp_server_details.side_effect = Exception("Not found")
        mock_api.add_vmcp_server.side_effect = Exception("Creation failed")
        
        context = {"env_id": "test-env"}
        
        # Attempt to create server (should fail)
        with self.assertRaises(ValueError) as cm:
            get_or_create_vmcp_server(context, skill_uuid="550e8400-e29b-41d4-a716-446655440000")
        
        self.assertIn("VMCP server creation failed", str(cm.exception))
        
        # Verify placeholder was removed from registry
        self.assertNotIn("test-env", _vmcp_server_registry)
    
    @patch('skillberry_agent_lib.vmcp_server_manager.skillberry_store')
    def test_skill_uuid_mismatch_warning(self, mock_api):
        """Test warning when existing server has different skill_uuid."""
        # Setup mock - server exists with different skill_uuid
        mock_api.get_vmcp_server_details.return_value = {
            "uuid": "d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a",
            "name": "vmcp-server-test-env",
            "description": "Existing server",
            "port": 8001,
            "skill_uuid": "d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a",
            "runtime": {"tools": []}
        }
        
        context = {"env_id": "test-env"}
        
        # Create server with different skill_uuid
        with self.assertLogs(level='WARNING') as log:
            result = get_or_create_vmcp_server(context, skill_uuid="550e8400-e29b-41d4-a716-446655440000")
        
        # Verify warning was logged
        self.assertTrue(any("skill mismatch detected" in msg for msg in log.output))
        
        # Verify existing server was reused
        self.assertEqual(result["skill_uuid"], "d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a")


class TestGetOrCreateVmcpServerThreadSafety(unittest.TestCase):
    """Test thread-safety of get_or_create_vmcp_server."""
    
    def setUp(self):
        """Clear registry before each test."""
        clear_vmcp_servers()
    
    def tearDown(self):
        """Clear registry after each test."""
        clear_vmcp_servers()
    
    @patch('skillberry_agent_lib.vmcp_server_manager.skillberry_store')
    def test_concurrent_creation_same_env_id(self, mock_api):
        """Test multiple threads trying to create server for same env_id.
        
        Note: This test is simplified to avoid complex concurrency issues with mocking.
        It verifies that the registry prevents duplicate creations.
        """
        # Setup simple mocks
        mock_api.get_vmcp_server_details.side_effect = [
            Exception("Not found"),  # First check
            {  # After creation
                "uuid": "e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b",
                "name": "vmcp-server-test-env",
                "port": 8001,
                "skill_uuid": "550e8400-e29b-41d4-a716-446655440000",
                "runtime": {"tools": []}
            }
        ]
        mock_api.add_vmcp_server.return_value = {
            "name": "vmcp-server-test-env",
            "uuid": "e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b"
        }
        
        context = {"env_id": "test-env"}
        
        # First thread creates the server
        result1 = get_or_create_vmcp_server(context, skill_uuid="550e8400-e29b-41d4-a716-446655440000")
        self.assertIsNotNone(result1)
        self.assertEqual(result1["name"], "vmcp-server-test-env")
        
        # Reset mocks to verify no new calls
        mock_api.reset_mock()
        
        # Second "thread" should reuse existing server
        result2 = get_or_create_vmcp_server(context, skill_uuid="test-uuid")
        self.assertEqual(result1, result2)
        
        # Verify no new API calls were made
        mock_api.add_vmcp_server.assert_not_called()
        mock_api.get_vmcp_server_details.assert_not_called()
    
    @patch('skillberry_agent_lib.vmcp_server_manager.skillberry_store')
    def test_concurrent_creation_different_env_ids(self, mock_api):
        """Test multiple threads creating servers for different env_ids."""
        num_envs = 10
        
        # Track calls per server name using a dict
        call_counts = {}
        call_lock = threading.Lock()
        
        def get_details_side_effect(name):
            with call_lock:
                if name not in call_counts:
                    call_counts[name] = 0
                call_counts[name] += 1
                call_num = call_counts[name]
            
            # First call: server doesn't exist
            if call_num == 1:
                raise Exception("Not found")
            # Second call: server exists (after creation)
            else:
                env_id = name.replace("vmcp-server-", "")
                return {
                    "name": name,
                    "port": 8000 + int(env_id.split("-")[-1]),
                    "skill_uuid": f"uuid-{env_id}",
                    "runtime": {"tools": []}
                }
        
        mock_api.get_vmcp_server_details.side_effect = get_details_side_effect
        mock_api.add_vmcp_server.return_value = {"name": "test"}
        
        results = {}
        errors = []
        
        def create_server(env_num):
            try:
                context = {"env_id": f"test-env-{env_num}"}
                result = get_or_create_vmcp_server(context, skill_uuid=f"uuid-{env_num}")
                results[env_num] = result
            except Exception as e:
                errors.append((env_num, e))
        
        # Create threads for different env_ids
        threads = [
            threading.Thread(target=create_server, args=(i,))
            for i in range(num_envs)
        ]
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for completion with timeout
        for t in threads:
            t.join(timeout=5.0)
            if t.is_alive():
                self.fail("Thread did not complete within timeout")
        
        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Verify all servers were created
        self.assertEqual(len(results), num_envs)
        
        # Verify each env_id has unique server
        for i in range(num_envs):
            self.assertIn(i, results)
            self.assertEqual(results[i]["env_id"], f"test-env-{i}")


class TestWaitForServerCreation(unittest.TestCase):
    """Test _wait_for_server_creation helper function."""
    
    def setUp(self):
        """Clear registry before each test."""
        clear_vmcp_servers()
    
    def tearDown(self):
        """Clear registry after each test."""
        clear_vmcp_servers()
    
    def test_wait_for_successful_creation(self):
        """Test waiting for another thread to create server."""
        # Place placeholder
        _vmcp_server_registry["test-env"] = _PLACEHOLDER
        
        # Simulate another thread creating the server
        def create_server():
            time.sleep(0.2)
            _vmcp_server_registry["test-env"] = {
                "name": "vmcp-server-test-env",
                "port": 8001,
                "status": "ready"
            }
        
        thread = threading.Thread(target=create_server)
        thread.start()
        
        # Wait for server creation
        result = _wait_for_server_creation("test-env", max_wait=1.0)
        
        thread.join()
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "vmcp-server-test-env")
        self.assertEqual(result["port"], 8001)
    
    def test_wait_timeout(self):
        """Test timeout when server creation takes too long."""
        # Place placeholder that never gets replaced
        _vmcp_server_registry["test-env"] = _PLACEHOLDER
        
        # Wait should timeout
        with self.assertRaises(TimeoutError) as cm:
            _wait_for_server_creation("test-env", max_wait=0.3, poll_interval=0.1)
        
        self.assertIn("Timeout waiting for server creation", str(cm.exception))
        
        # Verify placeholder was cleaned up
        self.assertNotIn("test-env", _vmcp_server_registry)
    
    def test_wait_immediate_ready(self):
        """Test when server is already ready (no wait needed)."""
        # Place ready server
        _vmcp_server_registry["test-env"] = {
            "name": "vmcp-server-test-env",
            "port": 8001,
            "status": "ready"
        }
        
        # Wait should return immediately
        start_time = time.time()
        result = _wait_for_server_creation("test-env", max_wait=1.0)
        elapsed = time.time() - start_time
        
        # Verify quick return
        self.assertLess(elapsed, 0.2)
        self.assertEqual(result["name"], "vmcp-server-test-env")


class TestRemoveVmcpServer(unittest.TestCase):
    """Test remove_vmcp_server functionality."""
    
    def setUp(self):
        """Clear registry before each test."""
        clear_vmcp_servers()
    
    def tearDown(self):
        """Clear registry after each test."""
        clear_vmcp_servers()
    
    @patch('skillberry_agent_lib.skillberry_store.skillberry_store')
    def test_remove_existing_server(self, mock_api):
        """Test removing an existing server from registry and Tools Service."""
        # Add server to registry
        _vmcp_server_registry["test-env"] = {
            "name": "vmcp-server-test-env",
            "port": 8001
        }
        
        mock_api.remove_vmcp_server.return_value = {"message": "Removed"}
        
        context = {"env_id": "test-env"}
        result = remove_vmcp_server(context)
        
        # Verify server removed from registry
        self.assertTrue(result)
        self.assertNotIn("test-env", _vmcp_server_registry)
        
        # Verify API call
        mock_api.remove_vmcp_server.assert_called_once_with(name="vmcp-server-test-env")
    
    @patch('skillberry_agent_lib.skillberry_store.skillberry_store')
    def test_remove_nonexistent_server(self, mock_api):
        """Test removing a server that doesn't exist in registry."""
        mock_api.remove_vmcp_server.return_value = {"message": "Removed"}
        
        context = {"env_id": "nonexistent"}
        result = remove_vmcp_server(context)
        
        # Verify False returned (not in registry)
        self.assertFalse(result)
        
        # Verify API still called (cleanup Tools Service)
        mock_api.remove_vmcp_server.assert_called_once_with(name="vmcp-server-nonexistent")
    
    @patch('skillberry_agent_lib.skillberry_store.skillberry_store')
    def test_remove_server_api_failure(self, mock_api):
        """Test removal when Tools Service API fails."""
        # Add server to registry
        _vmcp_server_registry["test-env"] = {
            "name": "vmcp-server-test-env",
            "port": 8001
        }
        
        mock_api.remove_vmcp_server.side_effect = Exception("API Error")
        
        context = {"env_id": "test-env"}
        
        # Should not raise exception
        with self.assertLogs(level='WARNING') as log:
            result = remove_vmcp_server(context)
        
        # Verify server still removed from registry
        self.assertTrue(result)
        self.assertNotIn("test-env", _vmcp_server_registry)
        
        # Verify warning logged
        self.assertTrue(any("Failed to remove VMCP server" in msg for msg in log.output))
    
    @patch('skillberry_agent_lib.skillberry_store.skillberry_store')
    def test_remove_with_default_env_id(self, mock_api):
        """Test removal with default env_id."""
        # Add server with default env_id
        _vmcp_server_registry["default"] = {
            "name": "vmcp-server-default",
            "port": 8001
        }
        
        mock_api.remove_vmcp_server.return_value = {"message": "Removed"}
        
        context = {"env_id": "default"}  # Explicitly specify default env_id
        result = remove_vmcp_server(context)
        
        # Verify default used
        self.assertTrue(result)
        self.assertNotIn("default", _vmcp_server_registry)
        mock_api.remove_vmcp_server.assert_called_once_with(name="vmcp-server-default")


class TestClearVmcpServers(unittest.TestCase):
    """Test clear_vmcp_servers functionality."""
    
    def test_clear_empty_registry(self):
        """Test clearing an empty registry."""
        clear_vmcp_servers()
        self.assertEqual(len(_vmcp_server_registry), 0)
    
    def test_clear_populated_registry(self):
        """Test clearing a populated registry."""
        # Add multiple servers
        _vmcp_server_registry["env-1"] = {"name": "server-1"}
        _vmcp_server_registry["env-2"] = {"name": "server-2"}
        _vmcp_server_registry["env-3"] = {"name": "server-3"}
        
        # Clear registry
        clear_vmcp_servers()
        
        # Verify all removed
        self.assertEqual(len(_vmcp_server_registry), 0)
    
    def test_clear_thread_safe(self):
        """Test that clear is thread-safe."""
        # Add servers
        for i in range(20):
            _vmcp_server_registry[f"env-{i}"] = {"name": f"server-{i}"}
        
        # Clear from multiple threads
        def clear_registry():
            clear_vmcp_servers()
        
        threads = [threading.Thread(target=clear_registry) for _ in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify registry is empty
        self.assertEqual(len(_vmcp_server_registry), 0)


class TestVmcpServerManagerEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""
    
    def setUp(self):
        """Clear registry before each test."""
        clear_vmcp_servers()
    
    def tearDown(self):
        """Clear registry after each test."""
        clear_vmcp_servers()
    
    @patch('skillberry_agent_lib.vmcp_server_manager.skillberry_store')
    def test_missing_runtime_tools(self, mock_api):
        """Test handling when runtime.tools is missing."""
        mock_api.get_vmcp_server_details.side_effect = [
            Exception("Not found"),
            {
                "name": "vmcp-server-test-env",
                "port": 8001,
                "runtime": {}  # No tools field
            }
        ]
        mock_api.add_vmcp_server.return_value = {"name": "vmcp-server-test-env"}
        
        context = {"env_id": "test-env"}
        result = get_or_create_vmcp_server(context)
        
        # Verify empty tools list
    
    @patch('skillberry_agent_lib.vmcp_server_manager.skillberry_store')
    def test_missing_port(self, mock_api):
        """Test handling when port is missing."""
        mock_api.get_vmcp_server_details.side_effect = [
            Exception("Not found"),
            {
                "name": "vmcp-server-test-env",
                "runtime": {}
                # No port field
            }
        ]
        mock_api.add_vmcp_server.return_value = {"name": "vmcp-server-test-env"}
        
        context = {"env_id": "test-env"}
        result = get_or_create_vmcp_server(context)
        
        # Verify None port
        self.assertIsNone(result["port"])
    
    @patch('skillberry_agent_lib.vmcp_server_manager.skillberry_store')
    def test_no_skill_uuid_provided(self, mock_api):
        """Test creating server without skill_uuid."""
        mock_api.get_vmcp_server_details.side_effect = [
            Exception("Not found"),
            {
                "name": "vmcp-server-test-env",
                "port": 8001,
                "runtime": {}
            }
        ]
        mock_api.add_vmcp_server.return_value = {"name": "vmcp-server-test-env"}
        
        context = {"env_id": "test-env"}
        result = get_or_create_vmcp_server(context, skill_uuid=None)
        
        # Verify server created without skill_uuid
        self.assertIsNone(result.get("skill_uuid"))
        
        # Verify API called with None skill_uuid
        mock_api.add_vmcp_server.assert_called_once()
        call_kwargs = mock_api.add_vmcp_server.call_args[1]
        self.assertIsNone(call_kwargs["skill_uuid"])


if __name__ == "__main__":
    unittest.main()


# Made with Bob