# skillberry-agent-lib

Core utilities library for Skillberry agents, providing message handling, trajectory management, and API client functionality.

## Requirements

Python 3.8+

## Installation & Usage

### pip install

Install directly from the local directory:

```sh
pip install .
```

Or install in development mode:

```sh
pip install -e .
```

Then import the package:

```python
import skillberry_agent_lib
from skillberry_agent_lib import SkillberryAPI, TrajectoryManager
```

### Poetry

If using Poetry in your project:

```sh
poetry add path/to/skillberry_agent_lib
```

Or install in development mode:

```sh
poetry install
```

## Features

### Message Handling

The library provides Pydantic models for different message types:

```python
from skillberry_agent_lib import SystemMessage, UserMessage, AssistantMessage, ToolMessage

# Create messages
system_msg = SystemMessage(content="You are a helpful assistant")
user_msg = UserMessage(content="Hello!")
assistant_msg = AssistantMessage(content="Hi there!")
```

### Trajectory Management

Manage agent trajectories across tasks and sessions:

```python
from skillberry_agent_lib import TrajectoryManager

manager = TrajectoryManager()

# Add messages to trajectory
manager.add_message(skillberry_context, message)

# Get trajectory
trajectory = manager.get_trajectory(skillberry_context)

# Remove trajectory
manager.remove_trajectory(skillberry_context)
```

### Skillberry API Client

Interact with the Skillberry Tools Store API:

```python
from skillberry_agent_lib import SkillberryAPI

api = SkillberryAPI(base_url="http://localhost:8000")

# Check connectivity
api.check_communication()

# Search for skills
results = api.search_skills("python", max_number_of_results=5)
```

### Utilities

Helper functions for working with Skillberry contexts:

```python
from skillberry_agent_lib import flatten_keys, extract_base_url, SKILLBERRY_CONTEXT

# Flatten nested dictionary keys
flat_dict = flatten_keys(nested_dict)

# Extract base URL from full URL
base_url = extract_base_url("http://example.com/api/v1/endpoint")
```

## Development

### Running Tests

```sh
pytest
```

### Type Checking

```sh
mypy skillberry_agent_lib
```

### Linting

```sh
flake8 skillberry_agent_lib
```

## License

NoLicense

## Authors

Skillberry Team