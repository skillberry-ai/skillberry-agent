VERSION ?= latest

##@ Development

test: check_rits_key install_requirements ## Test the tools-agent
	pytest -s

test-e2e: check_rits_key install_requirements ## Test end-to-end the tools agent
	pytest -s tests/e2e

lint: install_requirements ## Lint the tools-maker
	black --check --diff --color agents config fast_api llm tools utils || \
		(echo "Lint Failed. Please run 'black agents config fast_api llm tools utils' to fix the issues" && exit 1)

fix-lint: ## Fix lint issues
	black agents config fast_api llm tools utils

check-git-clean:
	@changes="$$(git status --porcelain)"; \
	if [ -n "$$changes" ]; then \
	  echo "! You have uncommitted changes. Please commit, stash or clean them before releasing."; \
	  echo "=== Changes ==="; \
	  echo "$$changes"; \
	  exit 1; \
	fi

check-git-main:
	@if [ "$(shell git rev-parse --abbrev-ref HEAD)" != "main" ]; then \
		echo "! You must be on the main branch to run this command"; \
		exit 1; \
	fi

release: check_rits_key check-git-main check-git-clean install_requirements  ## Release a new version
	@if [ -z "$(RELEASE_VERSION)" ]; then \
		echo "++++++++++++++++++++++++++++++++++++++++++++"; \
  		echo "RELEASE_VERSION is not set. It is required for the release"; \
  		echo "Please set RELEASE_VERSION and use 'RELEASE_VERSION=<version> make release' "; \
		echo "++++++++++++++++++++++++++++++++++++++++++++"; \
	exit 1; fi

	@command -v sed >/dev/null 2>&1 || { echo "❌ 'sed' is not installed. Aborting."; exit 1; }
	@echo "++++++++++++++++++++++++++++++++++++++++++++"
	@echo "=> Creating release with version: $(RELEASE_VERSION)"
	@echo "++++++++++++++++++++++++++++++++++++++++++++"
	@sleep 10
	@echo "===> Generating git tag $(RELEASE_VERSION) and creating GitHub release"

	@git checkout -b branch-$(RELEASE_VERSION)
	@echo "===> Generated release branch $(RELEASE_VERSION)"
	sed -i "s|git+ssh://git@github.ibm.com/Blueberry/blueberry-sdk.git#subdirectory=blueberry_tools_service_sdk|git+ssh://git@github.ibm.com/Blueberry/blueberry-sdk.git@$$RELEASE_VERSION#subdirectory=blueberry_tools_service_sdk|" requirements.txt 
	sed -i "s|git+ssh://git@github.ibm.com/Blueberry/blueberry-sdk.git#subdirectory=blueberry_tools_maker_sdk|git+ssh://git@github.ibm.com/Blueberry/blueberry-sdk.git@$$RELEASE_VERSION#subdirectory=blueberry_tools_maker_sdk|" requirements.txt 
	git add requirements.txt && \
	if git diff --cached --quiet; then \
	  		echo "!!! No updates to commit in blueberry-tools-agent !!!"; \
	else \
		echo "!!! Updates detected in blueberry-tools-agent, committing... !!!"; \
		git config --get user.name >/dev/null || git config user.name "Blueberry CI process" && \
		git config --get user.email >/dev/null || git config user.email "blueberry.ci@blueberry.ai" && \
		git commit -m "Update tools_agent requirements file with $(RELEASE_VERSION)" && \
		git push origin branch-$(RELEASE_VERSION) && \
		echo "Pushed updated requirements file to blueberry-tools-agent repository (origin branch-$(RELEASE_VERSION))"; \
	fi

	@git tag -a $(RELEASE_VERSION) -m "Release $(RELEASE_VERSION)" && \
	git push origin $(RELEASE_VERSION) && \
	gh release create $(RELEASE_VERSION) --generate-notes

	@echo "===> Building and pushing new docker image"
	@make docker_push
	@echo "++++++++++++++++++++++++++++++++++++++++++++"
	@echo "=> Release $(RELEASE_VERSION) created successfully"
	@echo "++++++++++++++++++++++++++++++++++++++++++++"

