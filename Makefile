.PHONY: help install lint format test test-integration test-golden test-e2e test-all coverage clean demo wheel sdist release image sbom check-release e2e e2e-offline demo-offline shellcheck

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
	@echo "  wheel             Build the wheel distribution"
	@echo "  sdist             Build the source distribution"
	@echo "  release           Build wheel + sdist and run twine check"
	@echo "  image             Build a multi-arch container image (buildx)"
	@echo "  sbom              Generate a CycloneDX SBOM (sbom.cdx.json)"
	@echo "  check-release     Run pre-release guards (tag/version/changelog/clean)"

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

# ---------------------------------------------------------------------------
# Release / packaging targets (Wave 6, Agent T).
# See ADR-0019 (release process) and ADR-0020 (signing / SLSA).
# ---------------------------------------------------------------------------

wheel:
	python -m build --wheel

sdist:
	python -m build --sdist

release:
	python -m build
	python -m twine check dist/*

image:
	docker buildx build --platform linux/amd64,linux/arm64 \
	    -t ai-platform-generator:dev --load .

sbom:
	@python -c "import cyclonedx_py" 2>/dev/null || { \
	    echo "cyclonedx-bom is not installed."; \
	    echo "Install with: pip install -e '.[release]'"; \
	    exit 1; \
	}
	python -m cyclonedx_py environment -o sbom.cdx.json

check-release:
	python scripts/release/check_release.py

# ---------------------------------------------------------------------------
# End-to-end + demo orchestration (Wave 6, Agent S).
# `e2e` requires a real kind + docker stack; `e2e-offline` is the CI-friendly
# subset that exercises run.sh in DEMO MODE without touching a cluster.
# ---------------------------------------------------------------------------

e2e: ## Run end-to-end tests (requires kind + docker)
	pytest tests/e2e -m e2e -v

e2e-offline:
	OFFLINE=1 pytest tests/e2e/test_demo_flow.py::test_run_sh_demo_offline_mode -m e2e -v

demo-offline:
	OFFLINE=1 ./run.sh demo --no-deploy

shellcheck:
	@./scripts/shellcheck-runsh.sh
