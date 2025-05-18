VERSION ?= latest

##@ Development

test: install_requirements ## Test the tools-agent
	pytest -s

test-e2e: install_requirements install_dev_requirements ## Test end-to-end the tools agent
	pytest -s tests/e2e

lint: install_requirements ## Lint the tools-maker
	black --check --diff --color agents config fast_api llm tools utils || \
		(echo "Lint Failed. Please run 'black agents config fast_api llm tools utils' to fix the issues" && exit 1)

fix-lint: ## Fix lint issues
	black agents config fast_api llm tools utils