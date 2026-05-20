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
        "default": "litellm.ibm.output_val",
        # Any provider registered in llm-client works here. Examples:
        #   'litellm.ibm.output_val'   - IBM LiteLLM proxy (default, uses IBM_THIRD_PARTY_API_KEY)
        #   'litellm.rits.output_val'  - RITS direct (uses RITS_API_KEY, RITS_API_URL)
        #   'litellm'                  - Plain LiteLLM (model & api_base fully manual)
        #   'openai.sync.output_val'   - OpenAI or compatible (uses OPENAI_API_KEY)
        #   'watsonx'                  - IBM WatsonX (uses WX_URL, WX_API_KEY, WX_PROJECT_ID)
        "label": "LLM provider name (any llm-client registered provider)",
    },
    "llm_api_base": {
        "type": "str",
        "default": "http://skillberry-1.vpc.cloud9.ibm.com:4000/",
        # The base URL for all LLM API calls.
        # Override per-provider with env vars if needed (e.g. IBM_LITELLM_API_BASE, RITS_API_URL).
        # Examples:
        #   IBM LiteLLM proxy: http://skillberry-1.vpc.cloud9.ibm.com:4000/
        #   IBM LiteLLM ETE:   https://ete-litellm.bx.cloud9.ibm.com
        "label": "Base URL for the LLM API",
    },
    "selected_model": {
        "type": "str",
        "default": "rits/openai/gpt-oss-120b",
        "label": "LLM model to be used by the agent: ",
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
