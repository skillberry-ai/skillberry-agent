# coding: utf-8

"""
    Skillberry Agent Library

    Core utilities for Skillberry agents including message handling,
    trajectory management, and API client functionality.
"""

from setuptools import setup, find_packages

NAME = "skillberry-agent-lib"
VERSION = "1.0.0"
PYTHON_REQUIRES = ">= 3.8"
REQUIRES = [
    "pydantic >= 2",
    "requests >= 2.25.0",
    "typing-extensions >= 4.7.1",
]

setup(
    name=NAME,
    version=VERSION,
    description="Skillberry Agent Library - Core utilities for Skillberry agents",
    author="Skillberry Team",
    author_email="",
    url="",
    keywords=["skillberry", "agent", "mcp", "trajectory"],
    install_requires=REQUIRES,
    packages=find_packages(exclude=["test", "tests"]),
    include_package_data=True,
    long_description_content_type='text/markdown',
    long_description="""\
Core utilities library for Skillberry agents, providing message handling, 
trajectory management, and API client functionality.
    """,
    package_data={"skillberry_agent_lib": ["py.typed"]},
    python_requires=PYTHON_REQUIRES,
)

# Made with Bob
