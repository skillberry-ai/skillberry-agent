.PHONY: help install install-dev test clean

help:
	@echo "Available commands:"
	@echo "  make install          - Install package"
	@echo "  make install-dev      - Install package with dev dependencies"
	@echo "  make test             - Run all tests"
	@echo "  make clean            - Remove build artifacts and caches"

install:
	pip install -e .

install-dev:
	pip install -e .[dev]

test:
	pytest

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete