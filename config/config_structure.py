import logging

logger = logging.getLogger(__name__)
#DAVIDBR: TODO: Add placeholder for sequential thinking configuration
CONFIG_STRUCTURE = {
    "tools_service_base_url": {
        "type": "str",
        "default": "http://9.148.245.32:8000", #DVIDBR: TODO: remove hardcoded IP
        "label": "The tools service url: ",
    },
    "tools_maker_base_url": {
        "type": "str",
        "default": "http://9.148.245.32:9000",
        "label": "The tools maker url: ",
    },
    "use_rits_proxy": {
        "type": "bool",
        "default": True,
        "label": "Should use the rits proxy (or connect to rits directly): "
    },
    "selected_model": {
        "type": "str",
        "default": "meta-llama/llama-3-3-70b-instruct",
        "label": "LLM rits model to be used by the agent: ",
    },
    "temperature": {
        "type": "float",
        "default": 0,
        "label": "The LLM model temperature: "
    },
    "max_suggested_functions": {
        "type": "int",
        "default": 3,
        "label": "Maximum numbers of functions and tools to suggest: "
    },
    "tools_react_agent": {
        "type": "group",
        "label": "Tool calling React agent",
        "children": {
            "recursion_limit": {
                "type": "int",
                "default": 10,
                "label": "Maximum number of iterations for the react agent: "
            },
        },
    },
    "generate_tools_dynamically": {
        "type": "bool",
        "default": False,
        "label": "Generate (code) tools dynamically: "
    },
    "advanced": {
        "type": "group",
        "label": "Advanced Settings",
        "children": {
            "debug": {
                "type": "bool",
                "default": False,
                "label": "Enable debug mode: "
            },
            "log_file": {
                "type": "str",
                "default": "/tmp/tools-agent.log",
                "label": "log file name"
            },
            "otel_logging": {
                "type": "bool",
                "default": False,
                "label": "Enable open-telemetry Logging (applicable only when debug is enabled): "
            },
            "similarity_threshold": {
                "type": "float",
                "default": 1.0,
                "label": "Similarity threshold for tools shortlisting: "
            },
            "max_tools_count": {
                "type": "int",
                "default": 5,
                "label": "Maximum number of tools in the tools shortlisting: "
            },
        }
    }
}

