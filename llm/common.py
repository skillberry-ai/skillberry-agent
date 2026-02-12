from enum import StrEnum
import os
import logging

from ibm_watsonx_ai.metanames import GenTextParamsMetaNames
from langchain_ibm.chat_models import ChatWatsonx
from langchain_openai import ChatOpenAI

from config.config_ui import config

logger = logging.getLogger(__name__)


class LLMProviderType(StrEnum):
    """
    Enum representing supported LLM providers.
    """

    WATSONX = "watsonx"
    RITS_OPENAI = "rits_openai"

    @classmethod
    def from_llm_provider_str(cls, llm_provider_type_str: str):
        try:
            return cls(llm_provider_type_str)
        except ValueError:
            raise ValueError(
                f"Invalid llm provider: {llm_provider_type_str}. "
                f"Supported llm providers are: {[p.value for p in cls]}"
            )


class LLMProvider:
    def __init__(
        self,
        llm_provider_type_str: str,
        llm_model: str,
        llm_temperature: float,
        llm_role: str,
        llm_timeout: int = 30,
    ):
        """
        Initialize an LLM provider instance.

        Parameters:
            llm_provider_type_str (str): the platform of this LLM (one of LLMProviderType string values)
            llm_model (str): LLM model
            llm_temperature (int): LLM temperature
            llm_role (str): the BTM role of this LLM (coder, validator or evaluator)
            llm_timeout (int): the amount of time (in seconds) that the client will wait for
                               response before raising a timeout error

        """
        try:
            self.llm_provider_type = LLMProviderType.from_llm_provider_str(
                llm_provider_type_str
            )
        except Exception as e:
            print(f"Failed to detect LLM platform: {str(e)}")
            exit(1)

        self.llm_temperature = llm_temperature
        self.llm_model = llm_model
        self.llm_role = llm_role
        self.llm_timeout = llm_timeout
        self.llm_url = ""

        model_url = config.get("model_url")

        if self.llm_provider_type == LLMProviderType.RITS_OPENAI:
            if "RITS_API_KEY" not in os.environ:
                print("RITS_API_KEY environment variable not set")
                print("Please set RITS_API_KEY environment variable")
                print("Additional info can be found on #rits-community slack")
                exit(1)

            self.api_key = os.environ["RITS_API_KEY"]

            self.rits_api_url = config.get("rits_api_url")
            self.use_rits_proxy = config.get("use_rits_proxy")
            self.rits_proxy_api_url = config.get("rits_proxy_api_url")

            if self.use_rits_proxy:
                logger.info(f"using rits_proxy")
                model_name = f"rits/{self.llm_model}"
                logger.info(f"model_name = {model_name}")
                self.llm_url = self.rits_proxy_api_url
                self.llm = ChatOpenAI(
                    model=model_name,
                    temperature=self.llm_temperature,
                    max_retries=2,
                    api_key=self.api_key,
                    base_url=self.rits_proxy_api_url,
                    request_timeout=self.llm_timeout,
                )
            elif model_url != "":
                logger.info(f"using model_url = {model_url}")
                logger.info(f"self.llm_model = {self.llm_model}")
                self.llm_url = model_url
                self.llm = ChatOpenAI(
                    model=self.llm_model,
                    temperature=self.llm_temperature,
                    max_retries=2,
                    api_key="/",
                    base_url=model_url,
                    default_headers={"RITS_API_KEY": self.api_key},
                    request_timeout=self.llm_timeout,
                )
            else:
                # best effort to guess the url from the model name
                logger.info(f"using best effort to guess model url")
                model = self.llm_model.split("/")[1].replace(".", "-").lower()
                url = f"{self.rits_api_url}/{model}/v1"
                logger.info(f"model = {model}")
                logger.info(f"url = {url}")
                self.llm_url = url
                self.llm = ChatOpenAI(
                    model=self.llm_model,
                    temperature=self.llm_temperature,
                    max_retries=2,
                    api_key="/",
                    base_url=url,
                    default_headers={"RITS_API_KEY": self.api_key},
                    request_timeout=self.llm_timeout,
                )

        elif self.llm_provider_type == LLMProviderType.WATSONX:
            DEFAULT_PARAMS_WATSONX = {
                GenTextParamsMetaNames.DECODING_METHOD: "greedy",
                GenTextParamsMetaNames.MIN_NEW_TOKENS: 1,
                GenTextParamsMetaNames.TEMPERATURE: self.llm_temperature,
                GenTextParamsMetaNames.TIME_LIMIT: 40000,
            }

            if "WATSONX_APIKEY" not in os.environ:
                print("WATSONX_APIKEY environment variable not set")
                print("Please set WATSONX_APIKEY environment variable")
                print(
                    "Additional info can be found on https://www.ibm.com/products/watsonx-ai"
                )
                exit(1)
            if "WATSONX_PROJECT_ID" not in os.environ:
                print("WATSONX_PROJECT_ID environment variable not set")
                print("Please set WATSONX_PROJECT_ID environment variable")
                print(
                    "Additional info can be found on https://www.ibm.com/products/watsonx-ai"
                )
                exit(1)
            if "WATSONX_URL" not in os.environ:
                print("WATSONX_URL environment variable not set")
                print("Please set WATSONX_URL environment variable")
                print(
                    "Additional info can be found on https://www.ibm.com/products/watsonx-ai"
                )
                exit(1)

            self.api_key = os.environ["WATSONX_APIKEY"]
            self.watsonx_project_id = os.environ["WATSONX_PROJECT_ID"]
            self.watsonx_url = os.environ["WATSONX_URL"]
            self.llm_url = self.watsonx_url

            _llm = ChatWatsonx(
                project_id=self.watsonx_project_id,
                apikey=self.api_key,
                model_id=f"{self.llm_model}",
                params=DEFAULT_PARAMS_WATSONX,
                url=self.watsonx_url,
            )
            self.llm = _llm.with_config({"timeout": self.llm_timeout})

    def check_llm_communication(self):
        """
        Check connectivity status into the proper LLM.

        Returns:
            bool: whether connectivity succeeded
        """
        if self.llm_provider_type == LLMProviderType.RITS_OPENAI:
            logger.info(
                f"\n\n"
                f"==> LLM Configuration (for role: {self.llm_role}):\n"
                f"==> =================\n"
                f"==> Using rits proxy: {self.use_rits_proxy}\n"
                f"==> rits API URL: {self.rits_api_url}\n"
                f"==> rits proxy API URL: {self.rits_proxy_api_url}\n"
                f"==> LLM URL: {self.llm_url}\n"
                f"==> =================\n\n"
                f"==> Using model: {self.llm_model}\n"
                f"==> Coder Temperature: {self.llm_temperature}\n"
                f"==> =================\n\n"
            )
        elif self.llm_provider_type == LLMProviderType.WATSONX:
            logger.info(
                f"\n\n"
                f"==> LLM Configuration: (for role: {self.llm_role}):\n"
                f"==> =================\n"
                f"==> watsonx API URL: {self.watsonx_url}\n"
                f"==> watsonx project_id: {self.watsonx_project_id}\n"
                f"==> =================\n\n"
                f"==> Using model: {self.llm_model}\n"
                f"==> Coder Temperature: {self.llm_temperature}\n"
                f"==> =================\n\n"
            )

        try:
            self.llm.invoke(f"try to communicate with the {self.llm_role} llm")
            logger.info(f"Communication with the {self.llm_role} LLM established.")
        except Exception as e:
            logger.error(f"{self.llm_role} LLM is not working {e}")
            logger.error(f"llm_url = {self.llm_url}")
            raise e

        return True


# FIXME: define llm_provider as enum (selectable)
llm_provider_type_str = config.get("llm_provider")
llm_coder_model = config.get("selected_model")
llm_coder_temperature = config.get("temperature")


current_llm = LLMProvider(
    llm_provider_type_str=llm_provider_type_str,
    llm_model=llm_coder_model,
    llm_temperature=llm_coder_temperature,
    llm_role="",
)
