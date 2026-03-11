import logging
from typing import Dict

from data_model.messages import AssistantMessage, ToolMessage


logger = logging.getLogger(__name__)


class TrajectoryManager:
    """
    Manages agent trajectories for the Skillberry Agent.

    This class provides functionality to create, manage, and remove trajectories representing
    the agent's reasoning and tool-use steps across tasks and sessions.
    """
    def __init__(self):
        self.trajectories: Dict[str, list[ToolMessage | AssistantMessage]] = {}

    def add_message(self, skillberry_context: Dict, message: ToolMessage | AssistantMessage) -> None:
        """
        Append a message to the trajectory for the given context/environment, creating
        the trajectory list if it does not already exist.

        """
        env_id = skillberry_context["env_id"]
        self.trajectories.setdefault(env_id, []).append(message)
        logger.info(f"add_message: After {env_id}: {self.trajectories[env_id]}")

    def get_trajectory(self, skillberry_context: Dict) -> list[ToolMessage | AssistantMessage]:
        """
        Return the full trajectory for the given context/environment. If no trajectory
        exists, an empty list is returned.

        """
        env_id = skillberry_context["env_id"]
        logger.info(f"get_trajectory: {env_id}: {self.trajectories.get(env_id)}")
        return self.trajectories.get(env_id, [])

    def remove_trajectory(self, skillberry_context: Dict):
        """
        Remove and delete the trajectory associated with the given context/environment
        if it exists.

        """
        env_id = skillberry_context["env_id"]
        logger.info(f"remove_trajectory: {env_id}")
        if env_id in self.trajectories:
            logger.info(f"deleting trajectory: {env_id}")
            del self.trajectories[env_id]


# FIXME: make this singleton concurrent robust (and inside function) -
# consider to use threading.RLock() around servers manipulation functions
tracjectory_manager = TrajectoryManager()
