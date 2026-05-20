import inspect
import os
import logging
import json
import uuid
from enum import StrEnum
from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import AIMessage, ToolCall
from llm_switchboard.llm import get_llm
from llm_switchboard.llm.types import LLMResponse

from config.config_ui import config

logger = logging.getLogger(__name__)

# Suffix used by llm-switchboard to denote providers with structured output validation support.
_OUTPUT_VAL_SUFFIX = ".output_val"


class LLMProviderType(StrEnum):
    """
    Enum representing supported LLM providers.
    """

    LITELLM = "litellm"
    LITELLM_IBM = "litellm.ibm"
    LITELLM_RITS = "litellm.rits"
    LITELLM_OUTPUT_VAL = "litellm.output_val"
    LITELLM_IBM_OUTPUT_VAL = "litellm.ibm.output_val"
    LITELLM_RITS_OUTPUT_VAL = "litellm.rits.output_val"
    WATSONX = "watsonx"
    WATSONX_OUTPUT_VAL = "watsonx.output_val"

    @classmethod
    def from_llm_provider_str(cls, llm_provider_type_str: str):
        """
        Convert a string to an LLMProviderType enum value.

        Args:
            llm_provider_type_str: String representation of the provider type

        Returns:
            LLMProviderType: The corresponding enum value

        Raises:
            ValueError: If the provider string is not supported
        """
        try:
            return cls(llm_provider_type_str)
        except ValueError:
            raise ValueError(
                f"Invalid llm provider: {llm_provider_type_str}. "
                f"Supported llm providers are: {[p.value for p in cls]}"
            )


def _langchain_message_to_openai_dict(m: Any, role_map: Dict[str, str]) -> Dict[str, Any]:
    """Convert a LangChain message object to OpenAI dict format."""
    
    def _convert_tool_call_to_openai(tc: Any, idx: int) -> Optional[Dict[str, Any]]:
        """Convert a single tool call to OpenAI format."""
        # Extract fields from either dict or object
        tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
        tc_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
        tc_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
        
        # Generate ID if missing (required by OpenAI)
        if not tc_id:
            tc_id = str(uuid.uuid4())
            logger.warning(f"Tool call {idx} missing id, generated: {tc_id}")
        
        # Skip if name is missing
        if not tc_name:
            logger.error(f"Tool call {idx} missing name, skipping")
            return None
        
        # Ensure arguments is a JSON string
        arguments_str = tc_args if isinstance(tc_args, str) else json.dumps(tc_args)
        
        return {
            "id": tc_id,
            "type": "function",
            "function": {
                "name": tc_name,
                "arguments": arguments_str
            }
        }
    
    msg_dict = {
        "role": role_map.get(m.type, m.type),
        "content": m.content or ""
    }
    
    # Handle tool_calls for AIMessage
    if hasattr(m, "tool_calls") and m.tool_calls:
        logger.debug(f"Processing {len(m.tool_calls)} tool calls")
        tool_calls = []
        for idx, tc in enumerate(m.tool_calls):
            converted = _convert_tool_call_to_openai(tc, idx)
            if converted:
                tool_calls.append(converted)
        if tool_calls:
            msg_dict["tool_calls"] = tool_calls
    
    # Handle tool_call_id for ToolMessage
    if hasattr(m, "tool_call_id"):
        msg_dict["tool_call_id"] = m.tool_call_id
    
    return msg_dict


def _langchain_to_openai_messages(input_: Any) -> List[Dict[str, Any]]:
    """
    Convert LangChain message formats to OpenAI API message format.
    
    Handles:
    - Plain strings -> user message
    - LangChain PromptValue -> list of OpenAI messages
    - List of LangChain messages -> list of OpenAI messages
    - List of dicts -> normalized OpenAI messages
    
    Returns list of message dicts in OpenAI API format with roles: user, assistant, tool.
    """
    logger.debug(f"_langchain_to_openai_messages called with input type: {type(input_)}")
    
    # Handle string input
    if isinstance(input_, str):
        return [{"role": "user", "content": input_}]
    
    role_map = {"human": "user", "ai": "assistant", "tool": "tool"}
    
    # Handle PromptValue with to_messages()
    if hasattr(input_, "to_messages"):
        return [_langchain_message_to_openai_dict(m, role_map) for m in input_.to_messages()]
    
    # Handle list of messages
    if isinstance(input_, list):
        logger.debug(f"Processing list of {len(input_)} messages")
        result = []
        
        for m in input_:
            if isinstance(m, dict):
                # Dict message - fix tool_calls type if needed
                msg_dict = m.copy()
                if "tool_calls" in msg_dict and msg_dict["tool_calls"]:
                    msg_dict["tool_calls"] = [
                        {**tc, "type": "function"} if tc.get("type") == "tool_call" else tc
                        for tc in msg_dict["tool_calls"]
                    ]
                result.append(msg_dict)
            elif hasattr(m, "type") and hasattr(m, "content"):
                # LangChain message object
                result.append(_langchain_message_to_openai_dict(m, role_map))
            else:
                # Unknown format
                result.append({"role": "user", "content": str(m)})
        
        return result
    
    # Fallback
    return [{"role": "user", "content": str(input_)}]


def tool_to_openai_json(tool: Any) -> Optional[Dict[str, Any]]:
    """
    Convert a LangChain tool to OpenAI 'function' tool JSON.
    
    Expected fields on tool:
    - tool.name: str
    - tool.description: str (or None)
    - tool.args_schema: type[BaseModel] (Pydantic v2 class), optional
        OR tool.input_schema: dict (some adapters expose a raw JSON schema)
    """
    name = getattr(tool, "name", None)
    if not name:
        return None

    description = getattr(tool, "description", "") or ""

    # Prefer Pydantic v2 model class if available
    args_schema = getattr(tool, "args_schema", None)

    if args_schema:
         json_schema = tool.args_schema
    else:
        json_schema = None

    # Final fallback — minimally valid schema for OpenAI tools
    if json_schema is None:
        json_schema = {
            "type": "object",
            "properties": {},  # model may still call the tool; you can guard with validation at runtime
            "additionalProperties": True,
        }

    openai_schema = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": json_schema,
        },
    }
    return openai_schema


def _openai_response_to_langchain_message(response: Any) -> Any:
    """
    Convert llm-switchboard response to LangChain message format.
    
    Handles:
    - LLMResponse objects -> AIMessage with tool calls
    - String responses -> AIMessage
    - Already converted messages -> pass through
    
    Args:
        response: Response from llm-switchboard generate() call
        
    Returns:
        LangChain AIMessage or the original response if already converted
    """
    # Convert LLMResponse to LangChain AIMessage if needed
    if isinstance(response, LLMResponse):
        # Extract content and tool_calls from LLMResponse
        content = response.content or ""
        tool_calls_data = response.tool_calls or []
        
        # Convert tool_calls to LangChain ToolCall format
        langchain_tool_calls = []
        for tc in tool_calls_data:
            # Parse arguments from JSON string to dict
            args_str = tc.get("function", {}).get("arguments", "{}")
            try:
                args_dict = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse tool call arguments: {args_str}")
                args_dict = {}
            
            tool_call = ToolCall(
                name=tc.get("function", {}).get("name", ""),
                args=args_dict,
                id=tc.get("id", ""),
            )
            langchain_tool_calls.append(tool_call)
        
        # Create AIMessage with content and tool_calls
        return AIMessage(content=content, tool_calls=langchain_tool_calls)
    
    # If response is a string, wrap it in AIMessage
    if isinstance(response, str):
        return AIMessage(content=response)
    
    # Otherwise return as-is (might already be an AIMessage)
    return response


class LLMClientLangChainAdapter:
    """
    Wraps an llm-switchboard pair (simple + structured) to expose the LangChain-compatible
    interface that proxy agent expects: .invoke() and .bind_tools().
    """

    def __init__(
        self,
        simple_client: Any,
        structured_client: Any,
        model_name: str = "",
        simple_model_in_generate: bool = False,
        structured_model_in_generate: bool = False,
        bound_tools: Optional[List[Any]] = None,
        tool_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._simple_client = simple_client
        self._structured_client = structured_client
        self._model_name = model_name
        self._simple_model_in_generate = simple_model_in_generate
        self._structured_model_in_generate = structured_model_in_generate
        self._bound_tools = bound_tools or []
        self._tool_kwargs = tool_kwargs or {}
        
        # Convert tools to OpenAI schema once during initialization
        self._tools_openai_schema: Optional[List[Dict[str, Any]]] = None
        if self._bound_tools:
            self._tools_openai_schema = [
                j for t in self._bound_tools if (j := tool_to_openai_json(t)) is not None
            ]
            logger.info(f"Converted {len(self._tools_openai_schema)} tools to OpenAI schema during initialization")
            for idx, schema in enumerate(self._tools_openai_schema):
                func_name = schema.get("function", {}).get("name", "unknown")
                func_desc = schema.get("function", {}).get("description", "no description")
                func_params = schema.get("function", {}).get("parameters", {})
                logger.info(f"OpenAI Schema {idx+1}: name='{func_name}', description='{func_desc}', params={func_params}")

    def invoke(self, input_: Union[str, Any], config: Optional[Any] = None, **kwargs: Any) -> Any:
        """Used by check_llm_communication() for a plain-text health check.
        
        Args:
            input_: The input prompt (string or messages)
            config: Optional LangChain config (callbacks, tags, metadata, etc.)
            **kwargs: Additional keyword arguments
        """
        messages = _langchain_to_openai_messages(input_)
        
        # Add pre-converted tools and tool kwargs if present
        if self._tools_openai_schema:
            kwargs["tools"] = self._tools_openai_schema
            # Merge tool-specific kwargs (e.g., tool_choice)
            kwargs.update(self._tool_kwargs)
        
        if self._simple_model_in_generate and self._model_name:
            kwargs["model"] = self._model_name
        
        response = self._simple_client.generate(prompt=messages, **kwargs)
        return _openai_response_to_langchain_message(response)

    def bind_tools(self, tools: List[Any], **kwargs: Any) -> "LLMClientLangChainAdapter":
        """
        Bind MCP tools to the LLM adapter.
        
        This method follows the LangChain pattern of returning a new adapter instance
        with tools bound, rather than modifying the existing instance (immutable pattern).
        
        Args:
            tools: List of tools from get_mcp_tools() in LangChain format
            **kwargs: Additional tool binding options (e.g., tool_choice="auto")
        
        Returns:
            New LLMClientLangChainAdapter instance with tools bound
        """
        return LLMClientLangChainAdapter(
            simple_client=self._simple_client,
            structured_client=self._structured_client,
            model_name=self._model_name,
            simple_model_in_generate=self._simple_model_in_generate,
            structured_model_in_generate=self._structured_model_in_generate,
            bound_tools=tools,
            tool_kwargs=kwargs,
        )


def _filter_supported_kwargs(provider_cls: Any, candidate_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Return kwargs accepted by an llm-switchboard provider constructor."""
    signature = inspect.signature(provider_cls)
    parameters = signature.parameters
    return {
        key: value
        for key, value in candidate_kwargs.items()
        if key in parameters and value not in (None, "")
    }


def _instantiate_llm_client(
    provider_cls: Any,
    model_name: str,
    provider_kwargs: Dict[str, Any],
) -> tuple[Any, bool]:
    """Instantiate an llm-switchboard provider and report whether model goes in generate()."""
    signature = inspect.signature(provider_cls)
    supported_kwargs = _filter_supported_kwargs(provider_cls, provider_kwargs)
    if "model_name" in signature.parameters:
        return provider_cls(model_name=model_name, **supported_kwargs), False
    return provider_cls(**supported_kwargs), True


def _build_llm_client_adapter(
    provider_name: str,
    model_name: str,
    **provider_kwargs: Any,
) -> LLMClientLangChainAdapter:
    """
    Build an LLMClientLangChainAdapter from any llm-switchboard provider name.

    The provider_name can be any name registered in the llm-switchboard registry
    (e.g. 'litellm.rits.output_val', 'litellm.ibm.output_val', 'watsonx',
    'openai.sync.output_val', etc.).  Each provider reads its own env vars
    automatically (RITS_API_KEY, IBM_THIRD_PARTY_API_KEY, etc.).

    For the structured client we always use the '.output_val' variant.
    For the simple client we use the base name (without '.output_val').
    """
    # Determine the base name (no .output_val) and the output_val name
    if provider_name.endswith(_OUTPUT_VAL_SUFFIX):
        output_val_name = provider_name
        base_name = provider_name[: -len(_OUTPUT_VAL_SUFFIX)]
    else:
        base_name = provider_name
        output_val_name = provider_name + _OUTPUT_VAL_SUFFIX

    # Try to get the structured (.output_val) provider class; fall back to base
    try:
        StructuredCls = get_llm(output_val_name)
    except (KeyError, ValueError):
        StructuredCls = get_llm(base_name)

    # Try to get the simple (base) provider class; fall back to structured
    try:
        SimpleCls = get_llm(base_name)
    except (KeyError, ValueError):
        SimpleCls = StructuredCls

    simple_client, simple_model_in_generate = _instantiate_llm_client(
        SimpleCls, model_name, provider_kwargs
    )
    structured_client, structured_model_in_generate = _instantiate_llm_client(
        StructuredCls, model_name, provider_kwargs
    )
    return LLMClientLangChainAdapter(
        simple_client,
        structured_client,
        model_name=model_name,
        simple_model_in_generate=simple_model_in_generate,
        structured_model_in_generate=structured_model_in_generate,
    )


class LLMAdapterError:
    """
    Error LLM adapter that always fails, used when provider validation fails.
    This ensures the health check will fail gracefully.
    """
    
    def __init__(self, error_message: str):
        self.error_message = error_message
    
    def invoke(self, input_: Union[str, Any], config: Optional[Any] = None, **kwargs: Any) -> Any:
        """Always raises an exception with the validation error message."""
        raise ValueError(f"Invalid LLM provider configuration: {self.error_message}")
    
    def bind_tools(self, tools: List[Any], **kwargs: Any) -> "LLMAdapterError":
        """Returns self to maintain interface compatibility."""
        return self


class LLMProvider:
    def __init__(
        self,
        llm_provider_type_str: str,
        llm_model: str,
        llm_temperature: float,
        llm_role: str,
        llm_timeout: int = 30,
        llm_api_base: str = "",
    ):
        """
        Initialize an LLM provider instance using llm-switchboard.

        Parameters:
            llm_provider_type_str (str): llm-switchboard provider name
                (e.g. 'litellm.rits.output_val', 'litellm.ibm.output_val',
                'litellm', 'openai.sync.output_val', 'watsonx')
            llm_model (str): LLM model name
            llm_temperature (float): LLM temperature
            llm_role (str): Role identifier for logging
            llm_timeout (int): Request timeout in seconds
            llm_api_base (str): Base URL for the LLM API endpoint
        """
        self.llm_provider_name = llm_provider_type_str
        self.llm_temperature = llm_temperature
        self.llm_model = llm_model
        self.llm_role = llm_role
        self.llm_timeout = llm_timeout
        self.llm_api_base = llm_api_base

        logger.info(
            f"Creating LLM provider: provider={self.llm_provider_name}, "
            f"model={self.llm_model}, role={self.llm_role}"
        )

        # Validate provider type
        try:
            self.llm_provider_type = LLMProviderType.from_llm_provider_str(
                llm_provider_type_str
            )
        except Exception as e:
            error_msg = f"Failed to detect LLM platform: {str(e)}"
            logger.error(error_msg)
            # Create an error LLM adapter that will fail health check
            self.llm = LLMAdapterError(error_msg)
            return

        # Build provider kwargs based on provider type
        provider_kwargs = {}

        # RITS-based providers (litellm.ibm, litellm.rits)
        if self.llm_provider_type in [
            LLMProviderType.LITELLM_IBM,
            LLMProviderType.LITELLM_IBM_OUTPUT_VAL,
            LLMProviderType.LITELLM_RITS,
            LLMProviderType.LITELLM_RITS_OUTPUT_VAL,
        ]:
            # Validate RITS_API_KEY
            if "RITS_API_KEY" not in os.environ:
                error_msg = (
                    "RITS_API_KEY environment variable not set. "
                    "Please set RITS_API_KEY environment variable. "
                    "Additional info can be found on #rits-community slack"
                )
                logger.error(error_msg)
                self.llm = LLMAdapterError(error_msg)
                return
            
            provider_kwargs["api_key"] = os.environ["RITS_API_KEY"]
            
            # Map llm_api_base to appropriate parameter
            if self.llm_provider_type in [
                LLMProviderType.LITELLM_IBM,
                LLMProviderType.LITELLM_IBM_OUTPUT_VAL,
            ]:
                provider_kwargs["api_base"] = llm_api_base
            elif self.llm_provider_type in [
                LLMProviderType.LITELLM_RITS,
                LLMProviderType.LITELLM_RITS_OUTPUT_VAL,
            ]:
                provider_kwargs["api_url"] = llm_api_base

        # Watsonx providers
        elif self.llm_provider_type in [
            LLMProviderType.WATSONX,
            LLMProviderType.WATSONX_OUTPUT_VAL,
        ]:
            # Validate all required Watsonx environment variables
            missing_vars = []
            if "WATSONX_APIKEY" not in os.environ:
                missing_vars.append("WATSONX_APIKEY")
            if "WATSONX_PROJECT_ID" not in os.environ:
                missing_vars.append("WATSONX_PROJECT_ID")
            if "WATSONX_URL" not in os.environ:
                missing_vars.append("WATSONX_URL")
            
            if missing_vars:
                error_msg = (
                    f"Missing required Watsonx environment variables: {', '.join(missing_vars)}. "
                    "Please set all required environment variables."
                )
                logger.error(error_msg)
                self.llm = LLMAdapterError(error_msg)
                return
            
            provider_kwargs["api_key"] = os.environ["WATSONX_APIKEY"]
            provider_kwargs["project_id"] = os.environ["WATSONX_PROJECT_ID"]
            provider_kwargs["url"] = os.environ["WATSONX_URL"]

        # Other providers (fallback to original behavior)
        else:
            provider_kwargs["api_base"] = llm_api_base
            
            # Fallback API key resolution for other providers
            api_key = os.getenv("RITS_API_KEY") or os.getenv("IBM_THIRD_PARTY_API_KEY")
            if api_key:
                provider_kwargs["api_key"] = api_key

        self.llm = _build_llm_client_adapter(
            self.llm_provider_name,
            self.llm_model,
            **provider_kwargs,
        )

    def check_llm_communication(self):
        """
        Check connectivity status into the proper LLM.

        Returns:
            bool: whether connectivity succeeded
        """
        logger.info(
            f"\n\n"
            f"==> LLM Configuration (for role: {self.llm_role}):\n"
            f"==> =================\n"
            f"==> Provider: {self.llm_provider_name}\n"
            f"==> LLM API Base: {self.llm_api_base}\n"
            f"==> Using model: {self.llm_model}\n"
            f"==> Temperature: {self.llm_temperature}\n"
            f"==> =================\n\n"
        )

        try:
            self.llm.invoke(f"try to communicate with the {self.llm_role} llm")
            logger.info(f"Communication with the {self.llm_role} LLM established.")
        except Exception as e:
            logger.error(f"{self.llm_role} LLM is not working {e}")
            logger.error(f"llm_api_base = {self.llm_api_base}")
            raise e

        return True


# Initialize current_llm with configuration
llm_provider_type_str = config.get("llm_provider")
llm_coder_model = config.get("selected_model")
llm_coder_temperature = config.get("temperature")
llm_api_base = config.get("llm_api_base", "")

current_llm = LLMProvider(
    llm_provider_type_str=llm_provider_type_str,
    llm_model=llm_coder_model,
    llm_temperature=llm_coder_temperature,
    llm_role="",
    llm_api_base=llm_api_base,
)

# Made with Bob
