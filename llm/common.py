import os
import logging
from langchain_openai import ChatOpenAI

from config.config_ui import config

logger = logging.getLogger(__name__)

if "RITS_API_KEY" not in os.environ:
    print("RITS_API_KEY environment variable not set")
    print("Please set RITS_API_KEY environment variable")
    print("Additional info can be found on #rits-community slack")
    exit(1)

rits_api_key = os.environ["RITS_API_KEY"]

rits_api_url = config.get("rits_api_url")
rits_proxy_api_url = config.get("rits_proxy_api_url")
use_rits_proxy = config.get("use_rits_proxy")

selected_model = config.get("selected_model")
use_rits_proxy = config.get("use_rits_proxy")
temperature = config.get("temperature")


if use_rits_proxy:
    model_name = f"rits/{selected_model}".replace(".", "-").lower()

    llm = ChatOpenAI(
        model=f"{model_name}",
        temperature=temperature,
        max_retries=2,
        api_key=rits_api_key,
        base_url=rits_proxy_api_url,
    )

else:
    model = selected_model.split("/")[1].replace(".", "-").lower()
    url = f"{rits_api_url}/{model}/v1"

    llm = ChatOpenAI(
        model=f"{selected_model}",
        temperature=temperature,
        max_retries=2,
        api_key="/",
        base_url=url,
        default_headers={"RITS_API_KEY": rits_api_key},
    )


def check_llm_communication():

    logger.info(
        f"\n\n"
        f"==> 0. Configuration:\n"
        f"==> =================\n"
        f"==> Using rits proxy: {use_rits_proxy}\n"
        f"==> rits API URL: {rits_api_url}\n"
        f"==> rits proxy API URL: {rits_proxy_api_url}\n"
        f"==> =================\n"
        f"==> Using model: {selected_model}\n"
        f"==> Temperature: {temperature}\n"
    )

    try:
        llm.invoke("try to communicate with the llm")
        logger.info("Communication with the LLM established.")
    except Exception as e:
        logger.error(f"LLM is not working {e}")
        return False

    return True
