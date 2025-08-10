import logging

logger = logging.getLogger(__name__)
# DAVIDBR: TODO: Add placeholder for sequential thinking configuration
CONFIG_STRUCTURE = {
    "tools_service_base_url": {
        "type": "str",
        "default": "http://127.0.0.1:8000",
        "label": "The tools service url: ",
    },
    "tools_maker_base_url": {
        "type": "str",
        "default": "http://127.0.0.1:9000",
        "label": "The tools maker url: ",
    },
    "llm_provider": {
        "type": "str",
        "default": "rits_openai",
        "label": "LLM provider ('rits_openai' or 'watsonx')",
    },
    "use_rits_proxy": {
        "type": "bool",
        "default": True,
        "label": "Should use the rits proxy (or connect to rits directly): ",
    },
    "rits_api_url": {
        "type": "str",
        "default": "https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com",
        "label": "IBM rits service API URL (for direct connection)",
    },
    "rits_proxy_api_url": {
        "type": "str",
        "default": "http://9.148.245.32:4000",
        "label": "IBM rits proxy API URL (for proxy connection)",
    },
    "selected_model": {
        "type": "str",
        "default": "meta-llama/llama-4-maverick-17b-128e-instruct-fp8",
        "label": "LLM model to be used by the agent: ",
    },
    "temperature": {
        "type": "float",
        "default": 0,
        "label": "The LLM model temperature: ",
    },
    "max_suggested_functions": {
        "type": "int",
        "default": 3,
        "label": "Maximum numbers of functions and tools to suggest: ",
    },
    "tools_react_agent": {
        "type": "group",
        "label": "Tool calling React agent",
        "children": {
            "recursion_limit": {
                "type": "int",
                "default": 10,
                "label": "Maximum number of iterations for the react agent: ",
            },
        },
    },
    "generate_tools_dynamically": {
        "type": "bool",
        "default": True,
        "label": "Generate (code) tools dynamically: ",
    },
    "advanced": {
        "type": "group",
        "label": "Advanced Settings",
        "children": {
            "debug": {"type": "bool", "default": False, "label": "Enable debug mode: "},
            "log_file": {
                "type": "str",
                "default": "/tmp/tools-agent.log",
                "label": "log file name",
            },
            "otel_logging": {
                "type": "bool",
                "default": False,
                "label": "Enable open-telemetry Logging (applicable only when debug is enabled): ",
            },
            "similarity_threshold": {
                "type": "float",
                "default": 0.5,
                "label": "Similarity threshold for tools shortlisting: ",
            },
            "max_tools_count": {
                "type": "int",
                "default": 5,
                "label": "Maximum number of tools in the tools shortlisting: ",
            },
            "max_tools_generation_per_execution": {
                "type": "int",
                "default": 10000,
                "label": "Maximum number of tools that the agent can generate per execution: ",
            },
        },
    },
}
