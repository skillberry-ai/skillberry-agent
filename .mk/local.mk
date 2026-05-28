# ----------- MANDATORY IDENTIFIERS ------------------
# Names: No spaces, letter start, letters, digits, hyphen, underscore
# Python path names: also no hyphen
# Make sure NO TRAILING WHITE SPACES after values! No quotes or double-quotes!
ASSET_NAME := skillberry-agent
ACRONYM := SBA
DESC_NAME := Skillberry Agent service
VERSION_LOCATION := fast_api/git_version.py
# Set to 1 if this asset is using LLM services - watsonx or RITS
USE_LLM_SVCS := 0
# Set these two below even if your asset is not a service - it allows execution control
SERVICE_ENTRY_MODULE := main
SERVICE_NAME := $(ASSET_NAME)
# If this asset is an actual network service, define these service settings as well
SERVICE_PORTS := 7000 7001
SERVICE_PORT_ROLES := MAIN CONFIG
SERVICE_HOST := 0.0.0.0
SERVICE_HAS_SDK := 1
# If this service container uses persistent mounts, please specify here as pairs of mount:path - separated by space, e.g. /data:/mydata /logs:/tmp/logs
CNTR_MOUNTS := 
# ----------------------------------------------------

# Legacy variables for backward compatibility
# PROJECT_NAME := skillberry-agent
# DOCKER_REPOSITORY_NAME ?= us.icr.io/research3
# IMAGE_NAME := blueberry-tools-agent
# VERSION ?= latest
# BUILD_DATE := $(shell date "+%Y-%m-%d %H:%M")
# DOCKER_NAME ?= $(DOCKER_REPOSITORY_NAME)/$(IMAGE_NAME)
# DOCKER_VERSION ?= $(BUILD_VERSION)
# TOOLS_SERVICE_SENTINEL := /tmp/tools-service.pid
# BASE_DIR := $(shell pwd)

# Python command override (system uses python3)
PYTHON := python3

# Override python command in skillberry-common
export PYTHON

# Override CODE_SUBTREES for skillberry-agent structure
# Note: skillberry-agent is not yet an installable package, so it doesn't use the standard 'src/' directory.
# Instead, it has root-level directories for different components.
CODE_SUBTREES := agents config data_model fast_api llm tools utils .mk $(SB_COMMON_PATH)/.mk $(SB_COMMON_PATH)/scripts

include .mk/dev.mk
include .mk/process.mk