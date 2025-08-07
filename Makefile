.DEFAULT_GOAL := help

# 
# In blueberry every tag/release is created in a separate branch (to have dedicated toml with
# proper @ to sdk). So we implement our logic to maintain git format for 'git describe --always --dirty'
# - i.e. 0.5.3 or 0.5.3-5-gc9b7ddd or 0.5.3-5-gc9b7ddd-dirty
# 
_LATEST_RELEASE=$(shell git branch -r | grep 'branch-' | sed 's|.*/branch-||' | sort -V | tail -n 1 | head -n 1)

#
# _LATEST_RELEASE is the actual tag e.g. 0.5.3
#
ifeq ($(_LATEST_RELEASE),)
	#
	# Latest release does not exist
	#

	_CURRENT_COMMIT=$(shell git rev-parse --short=7 HEAD)
	# sets with "dirty" if there are uncommitted changes
	_DIRTY=$(shell git diff --quiet || echo "-dirty")
	# e.g. gc9b7ddd, gc9b7ddd-dirty
	BUILD_VERSION="g$(_CURRENT_COMMIT)$(_DIRTY)"
else
	# Find the common ancestor (branch point)
	# TODO: confirm _BASE_COMMIT not needed and remove 
	# _BASE_COMMIT=$(shell git merge-base origin/main origin/branch-$(_LATEST_RELEASE))

	#
	# Count commits in main after the branch point
	# tag is git global - can be safely used
	#
	_COMMIT_COUNT=$(shell git rev-list --count $(_LATEST_RELEASE)..HEAD)

	_CURRENT_COMMIT=$(shell git rev-parse --short=7 HEAD)

	_DIRTY=$(shell git diff --quiet || echo "-dirty")

	ifeq ($(_COMMIT_COUNT),0)
		# e.g. 0.4
		BUILD_VERSION="$(_LATEST_RELEASE)$(_DIRTY)"
	else
		# e.g. 0.4-70-gc9b7ddd
		BUILD_VERSION="$(_LATEST_RELEASE)-$(_COMMIT_COUNT)-g$(_CURRENT_COMMIT)$(_DIRTY)"
	endif
endif


BUILD_DATE := $(shell date "+%Y-%m-%d %H:%M")

DOCKER_NAME ?= $(DOCKER_REPOSITORY_NAME)/$(IMAGE_NAME)
DOCKER_VERSION ?= $(BUILD_VERSION)

DOCKER_REPOSITORY_NAME ?= us.icr.io/research3
IMAGE_NAME = blueberry-tools-agent



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

update_git_version:
	@echo "Writing git version to fast_api/git_version.py"
	@echo "__git_version__ = \"$(BUILD_VERSION)\"" > fast_api/git_version.py

.PHONY: check_rits_key
check_rits_key:
	@if [ -z $$RITS_API_KEY ]; then echo "RITS_API_KEY is not set. It is required for the agent service"; exit 1; fi

install_requirements: update_git_version check-venv git_hooks_setup # Install requirements
	pip install -r requirements.txt
	
run: check_rits_key install_requirements  ## Start blueberry tools-agent.
	python main.py

##@ Docker

docker_build: update_git_version ## Build docker image
	for key in ~/.ssh/*; do ssh-add "$$key" 2>/dev/null || true ; done
	DOCKER_BUILDKIT=1 docker buildx build --ssh default \
							--build-arg BUILD_VERSION=$(BUILD_VERSION) --build-arg BUILD_DATE="$(BUILD_DATE)" \
							-t $(DOCKER_NAME):$(DOCKER_VERSION) \
							-t $(DOCKER_NAME):latest .

docker_run: docker_stop ## Run the docker image privileged
	@echo "Running Docker container: $(IMAGE_NAME)"
	-@sudo rm /tmp/tools-agent.log
	docker run --privileged --name $(IMAGE_NAME) --env-file .env --env RITS_API_KEY \
		   -d -v /tmp:/tmp -p 7000:7000 \
		   -p 7001:7001 $(DOCKER_NAME):latest

docker_stop: ## Stop the docker image
	@echo "Stopping Docker container: $(IMAGE_NAME)"
	@docker stop $(IMAGE_NAME) > /dev/null 2>&1 || true
	@docker rm $(IMAGE_NAME) > /dev/null 2>&1 || true

# make sure that you are login with required credentials
docker_push: docker_build ## Push docker image
	docker push $(DOCKER_NAME):$(DOCKER_VERSION)
	docker push $(DOCKER_NAME):latest

include .mk/development.mk
include .mk/ci.mk
