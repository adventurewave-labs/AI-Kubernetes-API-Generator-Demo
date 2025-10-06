# Testing the AI-Assisted Platform Extension Generator

## Quick Start

### Prerequisites

```bash
# Python 3.8+
python --version

# Docker (for integration tests)
docker --version

# Optional: Kubernetes cluster (for E2E tests)
kubectl version --client
```

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/AI-Assisted-Platform-Extension-Generator.git
cd AI-Assisted-Platform-Extension-Generator

# Install test dependencies
pip install -r requirements-test.txt

# Install the package in development mode
pip install -e .
```

### Running Tests

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/ -v

# Run with coverage
pytest --cov=src --cov-report=html

# Run integration tests (requires Docker)
pytest tests/integration/ -v

# Run E2E tests (requires Kubernetes and OpenAI API key)
OPENAI_API_KEY=your_key pytest tests/e2e/ -v
```

## Test Suite Overview

This project includes a comprehensive test suite covering:

### 🧪 Unit Tests
- **Location**: `tests/unit/`
- **Purpose**: Test individual components in isolation
- **Coverage**: >80% of Python code
- **Runtime**: < 1 minute

### 🔗 Integration Tests
- **Location**: `tests/integration/`
- **Purpose**: Test integration with external tools
- **Dependencies**: Docker, openapi-mcp-codegen
- **Runtime**: 2-5 minutes

### 🚀 End-to-End Tests
- **Location**: `tests/e2e/`
- **Purpose**: Test complete workflows
- **Dependencies**: Docker, Kubernetes, OpenAI API
- **Runtime**: 5-15 minutes

### ⚡ Performance Tests
- **Location**: `tests/performance/`
- **Purpose**: Benchmark and performance regression testing
- **Runtime**: 10-30 minutes

### ✅ Validation Tests
- **Location**: `tests/validation/`
- **Purpose**: Validate generated Go projects
- **Dependencies**: Go toolchain, Docker
- **Runtime**: 5-10 minutes

## Key Test Scenarios

### 1. VectorDB API Generation (From PLANS.md)

```bash
# Test the exact scenario from the project description
pytest tests/e2e/test_complete_workflow.py::TestCompleteWorkflow::test_vector_db_complete_workflow -v
```

**What it tests**:
- Natural language processing: "I need to create a VectorDB API for our new AI platform. The spec should include a string for engine_type (like 'pinecone' or 'weaviate') and an integer for the number of replicas."
- LLM command generation
- OpenAPI codegen tool integration
- Go project file generation
- Project structure validation

### 2. Platform Engineer Workflow

```bash
# Test realistic platform engineer scenarios
pytest tests/e2e/test_complete_workflow.py::TestRealWorldScenarios::test_platform_engineer_workflow -v
```

**What it tests**:
- Multiple API generation (DatabaseCluster, CacheCluster, MessageQueue)
- Batch processing
- Consistent output quality
- Performance under load

### 3. Go Project Validation

```bash
# Test generated Go projects are production-ready
pytest tests/validation/test_go_project_validation.py::TestGoProjectValidation::test_validate_go_project_structure -v
```

**What it tests**:
- Go syntax and compilation
- Kubernetes controller patterns
- RBAC configuration
- Dockerfile optimization
- CRD YAML validation

## Environment Setup

### Required Environment Variables

```bash
# For tests that use OpenAI API
export OPENAI_API_KEY=your_openai_api_key

# Optional custom paths
export OPENAPI_CODEGEN_PATH=/usr/local/bin/openapi-mcp-codegen
export DEFAULT_OUTPUT_DIR=/tmp/test-output
```

### Test Configuration

The test suite is configured via:

- `pytest.ini` - Main pytest configuration
- `conftest.py` - Shared fixtures and setup
- `.flake8` - Code style configuration
- `requirements-test.txt` - Test dependencies

### Test Data and Fixtures

Test data is organized in `tests/fixtures/`:

```
tests/fixtures/
├── test_data/
│   └── agent_requests.py      # Sample requests and expected outputs
├── mocks/
│   └── mock_openai.py        # Mock implementations
└── samples/
    ├── go_projects/          # Sample Go projects
    └── kubernetes_manifests/ # Sample K8s manifests
```

## Running Specific Test Categories

### Development Workflow

```bash
# 1. During development - run unit tests frequently
pytest tests/unit/ -v --tb=short

# 2. Before committing - run integration tests
pytest tests/integration/ -v

# 3. Before PR - run full test suite
pytest tests/ -v

# 4. Check coverage threshold
pytest --cov=src --cov-fail-under=80
```

### With Different Markers

```bash
# Run only fast tests
pytest -m "not slow" -v

# Run tests requiring Docker
pytest -m "docker" -v

# Run tests requiring Kubernetes
pytest -m "kubernetes" -v

# Run performance tests
pytest -m "performance" -v --benchmark-only
```

### Parallel Execution

```bash
# Run with multiple workers
pytest -n auto -v

# Run with specific worker count
pytest -n 4 -v
```

## Troubleshooting

### Docker Tests Failing

```bash
# Check Docker daemon status
sudo systemctl status docker

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Test Docker access
docker run hello-world
```

### OpenAI API Tests Failing

```bash
# Verify API key
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models

# Check API quota and usage
# Visit https://platform.openai.com/account/usage
```

### Kubernetes Tests Failing

```bash
# Create local cluster with kind
kind create cluster --name test-cluster

# Check cluster status
kubectl cluster-info

# Clean up after tests
kind delete cluster --name test-cluster
```

### Memory Issues

```bash
# Run with single worker
pytest -n 1 -v

# Run tests one by one
pytest -v --tb=short | head -50

# Run specific test file
pytest tests/unit/agent/test_agent_core.py -v
```

## Test Output and Reports

### Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# View in browser
open htmlcov/index.html
```

### Benchmark Results

```bash
# Run performance benchmarks
pytest tests/performance/ --benchmark-only --benchmark-json=benchmark.json

# View benchmark results
cat benchmark.json | python -m json.tool
```

### JUnit XML Reports

```bash
# Generate JUnit XML for CI systems
pytest --junitxml=test-results.xml

# View results
cat test-results.xml
```

## Continuous Integration

The project includes GitHub Actions workflows that:

1. **Run tests on multiple Python versions** (3.8-3.11)
2. **Execute integration tests with Docker**
3. **Run E2E tests with Kubernetes**
4. **Perform security scanning**
5. **Build and test Docker images**
6. **Upload coverage reports**

### Running Tests Locally Like CI

```bash
# Install all Python versions
pyenv install 3.8.0 3.9.0 3.10.0 3.11.0

# Run tests for each version
for version in 3.8.0 3.9.0 3.10.0 3.11.0; do
    pyenv local $version
    pytest tests/ -v --junitxml=test-results-$version.xml
done
```

## Contributing Tests

### Writing New Tests

1. **Choose appropriate test type** (unit/integration/e2e)
2. **Follow naming conventions**
3. **Use descriptive test names**
4. **Include proper assertions**
5. **Add necessary fixtures**

### Test Naming Patterns

```python
# Unit tests
def test_agent_processes_natural_language_request()

# Integration tests
def test_integration_with_openapi_codegen_tool()

# E2E tests
def test_complete_vectordb_generation_workflow()

# Performance tests
def test_request_processing_performance_under_load()
```

### Adding Test Data

```python
# Add to tests/fixtures/test_data/agent_requests.py
NEW_REQUEST = {
    "input": "Create a new API type",
    "expected_spec": {...},
    "category": "new_category",
    "complexity": "medium"
}
```

### Mock External Services

```python
# Use provided mock context managers
from tests.fixtures.mocks.mock_openai import MockOpenAIContext

def test_with_mock_openai():
    with MockOpenAIContext():
        result = agent.process_request("test request")
        assert result is not None
```

## Performance Benchmarks

### Current Benchmarks

- **Simple request processing**: < 1 second
- **Complex request processing**: < 5 seconds
- **Memory usage**: < 50MB per request
- **Concurrent processing**: > 2 requests/second

### Running Benchmarks

```bash
# Run all benchmarks
pytest tests/performance/ --benchmark-only

# Run specific benchmark
pytest tests/performance/test_codegen_performance.py::TestCodegenPerformance::test_request_processing_performance --benchmark-only

# Compare with baseline
pytest tests/performance/ --benchmark-only --benchmark-compare=baseline.json
```

### Performance Regression Detection

```bash
# Run regression tests
pytest tests/performance/test_performance_regression.py -v

# Generate baseline
pytest tests/performance/ --benchmark-only --benchmark-json=baseline.json

# Compare against baseline
pytest tests/performance/ --benchmark-only --benchmark-compare=baseline.json
```

## Security Testing

### Running Security Tests

```bash
# Run security scanning with bandit
bandit -r src/ -f json -o security-report.json

# Run dependency vulnerability check
pip-audit

# Run container security scan
trivy fs . --format json -o trivy-report.json
```

### Security Test Coverage

- **Static analysis** with bandit
- **Dependency scanning** with pip-audit
- **Container scanning** with Trivy
- **CodeQL analysis** in GitHub Actions

## Getting Help

### Documentation

- **Complete testing guide**: `docs/testing-guide.md`
- **API documentation**: `docs/api-reference.md`
- **Development guide**: `docs/development.md`

### Troubleshooting

1. **Check test logs**: `pytest -v -s`
2. **Debug with pdb**: `pytest --pdb`
3. **Run specific test**: `pytest tests/unit/agent/test_agent_core.py::test_function -v`
4. **Check environment**: `pytest --collect-only`

### Community

- **GitHub Issues**: Report bugs and request features
- **Discussions**: Ask questions and share ideas
- **Pull Requests**: Contribute improvements

---

For more detailed information, see the [complete testing guide](docs/testing-guide.md).