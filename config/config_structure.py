import logging

logger = logging.getLogger(__name__)
CONFIG_STRUCTURE = {
    "tools_service_base_url": {
        "type": "str",
        "default": "http://127.0.0.1:8000",
        "label": "The tools service url: ",
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
        "default": "http://skillberry-1.vpc.cloud9.ibm.com:4000",
        "label": "IBM rits proxy API URL (for proxy connection)",
    },
    "selected_model": {
        "type": "str",
        "default": "openai/gpt-oss-120b",
        "label": "LLM model to be used by the agent: ",
    },
    "model_url": {
        "type": "str",
        "default": "",
        "label": "url of LLM model to be used by the agent (should be postfixed with /v1): ",
    },
    "temperature": {
        "type": "float",
        "default": 0,
        "label": "The LLM model temperature: ",
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
