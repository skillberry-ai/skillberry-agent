"""
Unit tests for TrajectoryManager.

Following the testing pattern from skillberry-store where tests are co-located
with the modules they test. NO pytest fixtures - using direct instantiation instead.
"""

import threading
import time

from skillberry_agent_lib.trajectory_manager import TrajectoryManager
from skillberry_agent_lib.data_model.messages import (
    AssistantMessage,
    ToolMessage,
    ToolCall,
)


class TestTrajectoryManagerBasics:
    """Test basic TrajectoryManager functionality."""
    
    def test_add_message_creates_trajectory(self):
        """Test that adding a message creates a new trajectory."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        message = AssistantMessage(role="assistant", content="Test response")
        
        # Add message
        manager.add_message(context, message)
        
        # Verify trajectory exists and contains message
        trajectory = manager.get_trajectory(context)
        assert len(trajectory) == 1
        assert trajectory[0] == message
    
    def test_add_multiple_messages(self):
        """Test adding multiple messages to a trajectory."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        
        # Create multiple messages
        messages = [
            AssistantMessage(role="assistant", content="Message 1"),
            AssistantMessage(
                role="assistant",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={}, requestor="assistant")]
            ),
            ToolMessage(id="call_1", role="tool", content="Result", requestor="assistant"),
        ]
        
        # Add all messages
        for msg in messages:
            manager.add_message(context, msg)
        
        # Verify all messages are in trajectory
        trajectory = manager.get_trajectory(context)
        assert len(trajectory) == len(messages)
        for i, msg in enumerate(messages):
            assert trajectory[i] == msg
    
    def test_get_trajectory_returns_copy(self):
        """Test that get_trajectory returns a copy, not reference."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        message = AssistantMessage(role="assistant", content="Test")
        
        manager.add_message(context, message)
        
        # Get trajectory twice
        trajectory1 = manager.get_trajectory(context)
        trajectory2 = manager.get_trajectory(context)
        
        # Verify they are equal but not the same object
        assert trajectory1 == trajectory2
        assert trajectory1 is not trajectory2
        
        # Modify one copy
        trajectory1.append(ToolMessage(
            id="new_call",
            role="tool",
            content="new content",
            requestor="assistant",
        ))
        
        # Verify original trajectory unchanged
        trajectory3 = manager.get_trajectory(context)
        assert len(trajectory3) == 1
    
    def test_remove_trajectory_deletes_data(self):
        """Test that remove_trajectory properly deletes trajectory."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        message = AssistantMessage(role="assistant", content="Test")
        
        manager.add_message(context, message)
        
        # Verify trajectory exists
        trajectory = manager.get_trajectory(context)
        assert len(trajectory) == 1
        
        # Remove trajectory
        manager.remove_trajectory(context)
        
        # Verify trajectory is empty
        trajectory = manager.get_trajectory(context)
        assert len(trajectory) == 0
    
    def test_multiple_contexts_isolated(self):
        """Test that different env_ids maintain separate trajectories."""
        manager = TrajectoryManager()
        context1 = {"env_id": "test-env-001"}
        context2 = {"env_id": "test-env-002"}
        msg1 = AssistantMessage(role="assistant", content="Message 1")
        msg2 = ToolMessage(id="call_1", role="tool", content="Result", requestor="assistant")
        
        # Add different messages to different contexts
        manager.add_message(context1, msg1)
        manager.add_message(context2, msg2)
        
        # Verify each context has only its own message
        trajectory1 = manager.get_trajectory(context1)
        trajectory2 = manager.get_trajectory(context2)
        
        assert len(trajectory1) == 1
        assert len(trajectory2) == 1
        assert trajectory1[0] == msg1
        assert trajectory2[0] == msg2


class TestTrajectoryManagerThreadSafety:
    """Test thread-safety of TrajectoryManager."""
    
    def test_concurrent_additions_same_context(self):
        """Test multiple threads adding to same trajectory."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        num_threads = 10
        messages_per_thread = 5
        
        def add_messages(thread_id: int):
            for i in range(messages_per_thread):
                msg = AssistantMessage(
                    role="assistant",
                    content=f"Thread {thread_id}, Message {i}",
                )
                manager.add_message(context, msg)
        
        # Create and start threads
        threads = [
            threading.Thread(target=add_messages, args=(i,))
            for i in range(num_threads)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify all messages were added
        trajectory = manager.get_trajectory(context)
        assert len(trajectory) == num_threads * messages_per_thread
    
    def test_concurrent_reads_and_writes(self):
        """Test reading while writing occurs."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        num_writers = 5
        num_readers = 5
        messages_per_writer = 10
        stop_reading = threading.Event()
        read_counts = []
        
        def writer(thread_id: int):
            for i in range(messages_per_writer):
                msg = AssistantMessage(
                    role="assistant",
                    content=f"Writer {thread_id}, Message {i}",
                )
                manager.add_message(context, msg)
                time.sleep(0.001)  # Small delay to interleave operations
        
        def reader():
            local_count = 0
            while not stop_reading.is_set():
                trajectory = manager.get_trajectory(context)
                local_count += 1
                time.sleep(0.001)
            read_counts.append(local_count)
        
        # Start writers and readers
        writer_threads = [
            threading.Thread(target=writer, args=(i,))
            for i in range(num_writers)
        ]
        reader_threads = [
            threading.Thread(target=reader)
            for _ in range(num_readers)
        ]
        
        for t in reader_threads:
            t.start()
        for t in writer_threads:
            t.start()
        
        # Wait for writers to finish
        for t in writer_threads:
            t.join()
        
        # Stop readers
        stop_reading.set()
        for t in reader_threads:
            t.join()
        
        # Verify final state
        trajectory = manager.get_trajectory(context)
        assert len(trajectory) == num_writers * messages_per_writer
        assert all(count > 0 for count in read_counts)
    
    def test_concurrent_removals(self):
        """Test multiple threads removing different trajectories."""
        manager = TrajectoryManager()
        num_contexts = 20
        
        # Create trajectories for multiple contexts
        contexts = [{"env_id": f"test-env-{i}"} for i in range(num_contexts)]
        for ctx in contexts:
            msg = AssistantMessage(role="assistant", content=f"Message for {ctx['env_id']}")
            manager.add_message(ctx, msg)
        
        # Remove them concurrently
        def remove_trajectory(ctx):
            manager.remove_trajectory(ctx)
        
        threads = [
            threading.Thread(target=remove_trajectory, args=(ctx,))
            for ctx in contexts
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify all trajectories are removed
        for ctx in contexts:
            trajectory = manager.get_trajectory(ctx)
            assert len(trajectory) == 0


class TestTrajectoryManagerEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_get_nonexistent_trajectory(self):
        """Test getting trajectory for non-existent env_id."""
        manager = TrajectoryManager()
        context = {"env_id": "nonexistent"}
        
        trajectory = manager.get_trajectory(context)
        assert trajectory == []
    
    def test_remove_nonexistent_trajectory(self):
        """Test removing non-existent trajectory (should not error)."""
        manager = TrajectoryManager()
        context = {"env_id": "nonexistent"}
        
        # Should not raise an error
        manager.remove_trajectory(context)
    
    def test_empty_trajectory_behavior(self):
        """Test behavior with empty trajectories."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        
        # Get trajectory before adding anything
        trajectory = manager.get_trajectory(context)
        assert trajectory == []
        assert isinstance(trajectory, list)
    
    def test_message_ordering_preserved(self):
        """Test that message order is maintained."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        
        # Add messages in specific order
        messages = [
            AssistantMessage(role="assistant", content=f"Message {i}")
            for i in range(10)
        ]
        
        for msg in messages:
            manager.add_message(context, msg)
        
        # Verify order is preserved
        trajectory = manager.get_trajectory(context)
        for i, msg in enumerate(trajectory):
            assert msg.content == f"Message {i}"


class TestTrajectoryManagerMessageTypes:
    """Test handling of different message types."""
    
    def test_assistant_message_storage(self):
        """Test storing AssistantMessage."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        message = AssistantMessage(role="assistant", content="Test content")
        
        manager.add_message(context, message)
        
        trajectory = manager.get_trajectory(context)
        assert len(trajectory) == 1
        assert isinstance(trajectory[0], AssistantMessage)
        assert trajectory[0].content == message.content
    
    def test_tool_message_storage(self):
        """Test storing ToolMessage."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        message = ToolMessage(id="call_123", role="tool", content="Tool result", requestor="assistant")
        
        manager.add_message(context, message)
        
        trajectory = manager.get_trajectory(context)
        assert len(trajectory) == 1
        assert isinstance(trajectory[0], ToolMessage)
        assert trajectory[0].id == message.id
    
    def test_mixed_message_types(self):
        """Test trajectory with mixed message types."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        
        messages = [
            AssistantMessage(role="assistant", content="Message 1"),
            AssistantMessage(
                role="assistant",
                tool_calls=[ToolCall(id="call_1", name="tool", arguments={}, requestor="assistant")]
            ),
            ToolMessage(id="call_1", role="tool", content="Result", requestor="assistant"),
        ]
        
        for msg in messages:
            manager.add_message(context, msg)
        
        trajectory = manager.get_trajectory(context)
        assert len(trajectory) == len(messages)
        
        # Verify types are preserved
        assert isinstance(trajectory[0], AssistantMessage)
        assert isinstance(trajectory[1], AssistantMessage)
        assert isinstance(trajectory[2], ToolMessage)
    
    def test_assistant_with_tool_calls(self):
        """Test assistant messages containing tool calls."""
        manager = TrajectoryManager()
        context = {"env_id": "test-env-001"}
        message = AssistantMessage(
            role="assistant",
            tool_calls=[
                ToolCall(id="call_456", name="test_tool", arguments={"param": "value"}, requestor="assistant")
            ]
        )
        
        manager.add_message(context, message)
        
        trajectory = manager.get_trajectory(context)
        assert len(trajectory) == 1
        assert isinstance(trajectory[0], AssistantMessage)
        assert trajectory[0].tool_calls is not None
        assert len(trajectory[0].tool_calls) == 1
        assert trajectory[0].tool_calls[0].name == "test_tool"

# Made with Bob
