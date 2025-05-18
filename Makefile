.DEFAULT_GOAL := help

BUILD_VERSION ?= latest
BUILD_DATE := $(shell date +%Y-%m-%d\ %H:%M)

DOCKER_REPOSITORY_NAME ?= artifactory.haifa.ibm.com:5130
IMAGE_NAME = blueberry-tools-agent

DOCKER_NAME = $(DOCKER_REPOSITORY_NAME)/$(IMAGE_NAME)
DOCKER_VERSION = $(BUILD_VERSION)


TOOLS_SERVICE_SENTINEL=/tmp/tools-service.pid

AWK := awk
ifeq ($(OS),Windows_NT)
		AWK = gawk
		ifeq (, $(shell where gawk 2> NUL))
			$(error "gawk not found. Please install it and ensure it's in your PATH.")
		endif
else
	ifeq ($(shell uname -s), Darwin)
		AWK = gawk
		ifeq (, $(shell which gawk 2> /dev/null))
			$(error "gawk not found. Please install it and ensure it's in your PATH.")
		endif
	endif
endif

.PHONY: help
help: ## Display this help.
	@$(AWK) 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

BASE_DIR=$(shell pwd)

.PHONY: run

##@ Setup & teardown

git_hooks_setup:
	@git config core.hooksPath .githooks
	@chmod +x .githooks/*

.PHONY: check-venv
check-venv:
	@python -c "import sys, os; in_venv = ('VIRTUAL_ENV' in os.environ) or (hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)); print('✅ In virtual environment' if in_venv else '❌ Not in virtual environment'); exit(0) if in_venv else exit(1)"

.PHONY: check_rits_key
check_rits_key:
	@if [ -z $$RITS_API_KEY ]; then echo "RITS_API_KEY is not set. It is required for the agent service"; exit 1; fi

install_requirements: check-venv git_hooks_setup # Install requirements
	pip install -r requirements.txt
	
run: check_rits_key install_requirements  ## Start blueberry tools-agent.
	python main.py

##@ Docker

docker_build: ## Build docker image
	for key in ~/.ssh/*; do ssh-add "$$key" 2>/dev/null || true ; done
	DOCKER_BUILDKIT=1 docker build --ssh default --progress=plain --build-arg BUILD_VERSION=$(BUILD_VERSION) --build-arg BUILD_DATE="$(BUILD_DATE)" -t $(DOCKER_NAME):$(DOCKER_VERSION) .

docker_run: docker_stop ## Run the docker image
	@echo "Running Docker container: $(IMAGE_NAME)"
	docker run --name $(IMAGE_NAME) --env-file .env -d -v /tmp:/tmp -p 7000:7000 -p 7001:7001 $(DOCKER_NAME):$(DOCKER_VERSION)

docker_stop: ## Stop the docker image
	@echo "Stopping Docker container: $(IMAGE_NAME)"
	@docker stop $(IMAGE_NAME) > /dev/null 2>&1 || true
	@docker rm $(IMAGE_NAME) > /dev/null 2>&1 || true

# make sure that you are login with required credentials
docker_push: docker_build ## Push docker image
	docker push $(DOCKER_NAME):$(DOCKER_VERSION)

include .mk/development.mk
include .mk/ci.mk
