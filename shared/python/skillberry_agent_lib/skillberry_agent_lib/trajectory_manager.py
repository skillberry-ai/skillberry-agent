import logging
import threading
from typing import Dict

from skillberry_agent_lib.data_model.messages import AssistantMessage, ToolMessage


logger = logging.getLogger(__name__)


class TrajectoryManager:
    """
    Manages agent trajectories with MCP support.

    This class provides functionality to create, manage, and remove trajectories representing
    the agent's reasoning and tool-use steps across tasks and sessions.
    
    Thread-safe implementation using threading.Lock to prevent race conditions in
    concurrent environments (e.g., FastAPI with multiple requests).
    """
    def __init__(self):
        self.trajectories: Dict[str, list[ToolMessage | AssistantMessage]] = {}
        self._lock = threading.Lock()

    def add_message(self, skillberry_context: Dict, message: ToolMessage | AssistantMessage) -> None:
        """
        Append a message to the trajectory for the given context/environment, creating
        the trajectory list if it does not already exist.
        
        Thread-safe operation using lock to prevent concurrent modification issues.
        
        Raises:
            ValueError: If skillberry_context is None or missing env_id
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
        with self._lock:
            self.trajectories.setdefault(env_id, []).append(message)
            logger.info(f"add_message: After {env_id}: {self.trajectories[env_id]}")

    def get_trajectory(self, skillberry_context: Dict) -> list[ToolMessage | AssistantMessage]:
        """
        Return the full trajectory for the given context/environment. If no trajectory
        exists, an empty list is returned.
        
        Thread-safe operation using lock to prevent reading during modification.
        
        Raises:
            ValueError: If skillberry_context is None or missing env_id
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
        with self._lock:
            trajectory = self.trajectories.get(env_id, [])
            logger.info(f"get_trajectory: {env_id}: {trajectory}")
            return trajectory.copy()  # Return a copy to prevent external modification

    def remove_trajectory(self, skillberry_context: Dict):
        """
        Remove and delete the trajectory associated with the given context/environment
        if it exists.
        
        Thread-safe operation using lock to prevent concurrent deletion issues.
        
        Raises:
            ValueError: If skillberry_context is None or missing env_id
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
        with self._lock:
            logger.info(f"remove_trajectory: {env_id}")
            if env_id in self.trajectories:
                logger.info(f"deleting trajectory: {env_id}")
                del self.trajectories[env_id]


# Global trajectory manager instance
trajectory_manager = TrajectoryManager()
