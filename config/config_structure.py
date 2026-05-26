import logging

logger = logging.getLogger(__name__)
CONFIG_STRUCTURE = {
    "tools_service_base_url": {
        "type": "str",
        "default": "http://127.0.0.1:8000",
        "label": "The tools service url: ",
    },
    "provider_name": {
        "type": "str",
        "default": "litellm.rits.output_val",
        "label": "LLM provider name (e.g., 'litellm.rits.output_val', 'openai.sync', 'litellm', 'watsonx'). Provider-specific credentials should be set via environment variables.",
    },
    "model_name": {
        "type": "str",
        "default": "openai/gpt-oss-120b",
        "label": "Model name to use with the provider",
    },
    "temperature": {
        "type": "float",
        "default": 0,
        "label": "LLM model temperature",
    },
    "tools_react_agent": {
        "type": "group",
        "label": "Tool calling React agent",
        "children": {
            "recursion_limit": {
                "type": "int",
                "default": 20,
                "label": "Maximum number of iterations for the react agent: ",
            },
        },
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
        },
    },
}
