.PHONY: help install lint format test test-integration test-golden test-e2e test-all coverage clean demo

help:
	@echo "Available targets:"
	@echo "  install           Install package and dev dependencies (editable)"
	@echo "  lint              Run ruff check and mypy"
	@echo "  format            Run ruff format"
	@echo "  test              Run unit tests"
	@echo "  test-integration  Run integration tests"
	@echo "  test-golden       Run golden-file tests"
	@echo "  test-e2e          Run end-to-end tests"
	@echo "  test-all          Run all test suites"
	@echo "  coverage          Run unit tests with coverage report"
	@echo "  clean             Remove caches and build artifacts"
	@echo "  demo              Placeholder demo entry point"

install:
	pip install -e ".[dev]"

lint:
	ruff check src tests
	mypy

format:
	ruff format src tests

test:
	pytest tests/unit

test-integration:
	pytest tests/integration

test-golden:
	pytest tests/golden

test-e2e:
	pytest tests/e2e

test-all:
	pytest tests/unit tests/integration tests/golden tests/e2e

coverage:
	pytest --cov=ai_platform_generator --cov-report=term-missing tests/unit

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

demo:
	@echo "not yet implemented; see docs/ddd/08-implementation-roadmap.md"
