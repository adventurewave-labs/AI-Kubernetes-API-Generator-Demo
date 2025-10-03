# Testing Guide

This comprehensive testing guide covers all aspects of testing for the AI-Assisted Platform Extension Generator project.

## Overview

The testing suite is organized into several categories following the testing pyramid:

```
         /\
        /E2E\      <- End-to-end workflow tests
       /------\
      /Valid. \   <- Go project validation tests
     /----------\
    /Perf.      \ <- Performance and benchmark tests
   /--------------\
   /Integr.      \ <- Integration tests with external tools
  /----------------\
 /   Unit        \ <- Fast, isolated unit tests
/------------------\
```

## Test Categories

### 1. Unit Tests (`tests/unit/`)

**Purpose**: Test individual components in isolation
**Coverage Goal**: >80%
**Execution Time**: < 1 minute total

#### Structure
- `tests/unit/agent/` - Agent core functionality tests
- `tests/unit/codegen/` - Code generation and parsing tests
- `tests/unit/cli/` - Command-line interface tests
- `tests/unit/utils/` - Utility function tests

#### Key Test Files
- `test_agent_core.py` - Agent processing and LLM interaction
- `test_spec_parser.py` - API specification parsing and validation
- `test_command_executor.py` - Command execution and subprocess handling

#### Running Unit Tests
```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ -v --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/agent/test_agent_core.py -v

# Run with specific marker
pytest tests/unit/ -v -m "unit"
```

### 2. Integration Tests (`tests/integration/`)

**Purpose**: Test integration between components and external services
**Coverage Goal**: Critical paths only
**Execution Time**: 2-5 minutes

#### Prerequisites
- Docker installed and running
- Access to external tools (optional, mocked when unavailable)

#### Structure
- `tests/integration/openapi/` - OpenAPI codegen tool integration
- `tests/integration/docker/` - Docker build and deployment tests
- `tests/integration/kubernetes/` - Kubernetes cluster interactions

#### Key Test Files
- `test_openapi_codegen.py` - Integration with openapi-mcp-codegen tool
- `test_docker_integration.py` - Docker image building and validation
- `test_kubernetes_integration.py` - Kubernetes API interactions

#### Running Integration Tests
```bash
# Run all integration tests
pytest tests/integration/ -v

# Run with Docker
pytest tests/integration/ -v -m "docker"

# Run with Kubernetes (requires cluster)
pytest tests/integration/ -v -m "kubernetes"
```

### 3. End-to-End Tests (`tests/e2e/`)

**Purpose**: Test complete workflows from natural language to generated Go projects
**Coverage Goal**: User scenarios only
**Execution Time**: 5-15 minutes

#### Prerequisites
- Docker installed
- Kubernetes cluster (kind/minikube optional)
- OpenAI API key (for some tests)

#### Key Test Files
- `test_complete_workflow.py` - Full workflow testing
- `test_real_world_scenarios.py` - Platform engineer scenarios
- `test_kubernetes_deployment.py` - Kubernetes deployment testing

#### Running E2E Tests
```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Run fast E2E tests (excludes slow ones)
pytest tests/e2e/ -v -m "not slow"

# Run with OpenAI API
OPENAI_API_KEY=your_key pytest tests/e2e/ -v
```

### 4. Performance Tests (`tests/performance/`)

**Purpose**: Benchmark performance and detect regressions
**Coverage Goal**: Critical performance paths
**Execution Time**: 10-30 minutes

#### Structure
- `tests/performance/benchmarks/` - Performance benchmarks
- `tests/performance/profiling/` - Memory and CPU profiling

#### Key Test Files
- `test_codegen_performance.py` - Code generation performance
- `test_scalability_tests.py` - Scalability under load
- `test_performance_regression.py` - Regression detection

#### Running Performance Tests
```bash
# Run performance benchmarks
pytest tests/performance/ -v --benchmark-only

# Run with detailed profiling
pytest tests/performance/ -v --benchmark-only --benchmark-sort=mean

# Run regression tests
pytest tests/performance/test_performance_regression.py -v
```

### 5. Validation Tests (`tests/validation/`)

**Purpose**: Validate generated Go projects
**Coverage Goal**: All output validation
**Execution Time**: 5-10 minutes

#### Structure
- `tests/validation/go-projects/` - Go project structure and syntax
- `tests/validation/api-contracts/` - API contract validation
- `tests/validation/kubernetes/` - Kubernetes manifest validation

#### Key Test Files
- `test_go_project_validation.py` - Go project validation
- `test_crd_validation.py` - CRD YAML validation
- `test_dockerfile_validation.py` - Dockerfile validation

#### Running Validation Tests
```bash
# Run all validation tests
pytest tests/validation/ -v

# Run Go-specific validation
pytest tests/validation/go-projects/ -v
```

## Test Configuration

### Environment Variables

```bash
# Required for some integration tests
export OPENAI_API_KEY=your_openai_api_key

# Optional configuration
export DEFAULT_OUTPUT_DIR=/tmp/test-output
export OPENAPI_CODEGEN_PATH=/usr/local/bin/openapi-mcp-codegen
export LOG_LEVEL=DEBUG
```

### Test Configuration Files

- `pytest.ini` - Pytest configuration and markers
- `.flake8` - Linting configuration
- `conftest.py` - Shared fixtures and test configuration
- `requirements-test.txt` - Test dependencies

### Test Markers

```bash
# Available test markers
pytest --collect-only | grep "markers"

# Common markers
-unit          # Unit tests
-integration   # Integration tests
-e2e          # End-to-end tests
-performance  # Performance tests
-validation   # Validation tests
-slow         # Slow running tests
-docker       # Tests requiring Docker
-kubernetes   # Tests requiring Kubernetes
```

## Test Data and Fixtures

### Location
- `tests/fixtures/test-data/` - Test data and sample inputs
- `tests/fixtures/mocks/` - Mock implementations
- `tests/fixtures/samples/` - Sample generated projects

### Key Test Data Files

- `agent_requests.py` - Sample natural language requests
- `mock_openai.py` - OpenAI API mocks
- `go_projects/` - Sample Go project structures
- `kubernetes_manifests/` - Sample K8s manifests

### Using Test Data

```python
from tests.fixtures.test_data.agent_requests import get_sample_request

# Get sample request
request_data = get_sample_request("simple_vector_db")

# Use in test
result = agent.process_request(request_data["input"])
```

## Running Tests

### Quick Start

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

### Development Workflow

```bash
# 1. Run unit tests frequently during development
pytest tests/unit/ -v

# 2. Run integration tests before committing
pytest tests/integration/ -v

# 3. Run full suite before PR
pytest tests/ -v

# 4. Check coverage
pytest --cov=src --cov-report=html --cov-fail-under=80
```

### CI/CD Integration

The GitHub Actions workflow (`.github/workflows/test.yml`) runs:

1. **Unit Tests** - All Python versions (3.8-3.11)
2. **Integration Tests** - With Docker and Kubernetes
3. **E2E Tests** - Full workflow validation
4. **Performance Tests** - Benchmarking and regression
5. **Validation Tests** - Go project validation
6. **Security Scanning** - Vulnerability detection
7. **Docker Build** - Image building and testing

### Running Tests in Docker

```bash
# Build test image
docker build -t test-runner -f Dockerfile.test .

# Run tests in container
docker run --rm -v $(pwd):/workspace test-runner pytest tests/ -v
```

## Test Best Practices

### Writing Unit Tests

1. **One assertion per test** when possible
2. **Descriptive test names** that explain what and why
3. **Arrange-Act-Assert** pattern
4. **Mock external dependencies**
5. **Test edge cases and error conditions**

```python
def test_agent_processes_vector_db_request_correctly(mock_openai_client):
    # Arrange
    request = "Create a VectorDB API with engine_type and replicas"
    mock_openai_client.set_response("vector_db", mock_response)

    # Act
    result = agent.process_request(request)

    # Assert
    assert "command" in result
    assert "openapi-mcp-codegen" in result["command"]
```

### Writing Integration Tests

1. **Use real services when possible**
2. **Test actual integration points**
3. **Include cleanup procedures**
4. **Handle service unavailability gracefully**
5. **Use realistic test data**

```python
@pytest.mark.integration
@pytest.mark.docker
def test_codegen_with_real_docker_image():
    # Test with actual Docker image
    # Will be skipped if Docker is not available
    pass
```

### Writing E2E Tests

1. **Focus on user scenarios**
2. **Test complete workflows**
3. **Include real-world data**
4. **Test error recovery**
5. **Validate actual outputs**

```python
@pytest.mark.e2e
def test_platform_engineer_creates_database_api():
    # Simulate real platform engineer workflow
    # From natural language to working Go controller
    pass
```

## Test Troubleshooting

### Common Issues

#### 1. Docker Tests Failing
```bash
# Check Docker is running
docker info

# Check permissions
sudo usermod -aG docker $USER
newgrp docker
```

#### 2. OpenAI API Tests Failing
```bash
# Check API key
echo $OPENAI_API_KEY

# Test API key manually
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models
```

#### 3. Kubernetes Tests Failing
```bash
# Check cluster status
kubectl cluster-info

# Check permissions
kubectl auth can-i create customresourcedefinitions
```

#### 4. Memory Issues in Tests
```bash
# Run with fewer parallel workers
pytest -n 1

# Increase memory limits
export PYTEST_XDIST_AUTO_NUM_WORKERS=1
```

### Debugging Failed Tests

```bash
# Run with verbose output
pytest -v -s tests/unit/agent/test_agent_core.py::test_function

# Run with pdb on failure
pytest --pdb

# Run with output capture disabled
pytest -s --capture=no

# Run specific test with debugging
pytest -v -s --pdb tests/unit/agent/test_agent_core.py::test_agent_processes_request_correctly
```

### Performance Debugging

```bash
# Run with profiling
pytest --profile

# Run memory profiling
pytest --memprof

# Run benchmark with detailed output
pytest --benchmark-only --benchmark-sort=mean --benchmark-json=results.json
```

## Coverage and Quality Metrics

### Coverage Goals
- **Unit Tests**: >80% line coverage
- **Integration Tests**: Critical paths covered
- **E2E Tests**: User workflows covered

### Quality Gates
- All tests must pass
- Coverage threshold met
- No security vulnerabilities
- Performance benchmarks within limits

### Viewing Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Open in browser
open htmlcov/index.html
```

## Contributing to Tests

### Adding New Tests

1. **Choose appropriate test category**
2. **Follow naming conventions**
3. **Add appropriate markers**
4. **Include necessary fixtures**
5. **Update documentation**

### Test Naming Conventions

```python
# Unit tests
def test_component_action_expected_result()

# Integration tests
def test_integration_with_service_expected_behavior()

# E2E tests
def test_user_scenario_from_start_to_finish()

# Performance tests
def test_performance_metric_under_conditions()
```

### Updating Test Data

1. **Add to appropriate fixture file**
2. **Follow existing patterns**
3. **Include edge cases**
4. **Document purpose**
5. **Update tests using the data**

## Continuous Integration

### GitHub Actions Workflow

The CI workflow runs tests in parallel jobs:

1. **Python Tests** (multiple versions)
2. **Go Validation Tests**
3. **E2E Tests** (with Kubernetes)
4. **Performance Tests** (on main branch)
5. **Security Scanning**
6. **Docker Build Tests**

### Test Results and Reporting

- **JUnit XML** files for CI integration
- **HTML coverage reports** for detailed analysis
- **Benchmark JSON** for performance tracking
- **Slack notifications** for failures
- **PR comments** with test summaries

### Local CI Simulation

```bash
# Run CI-like test suite locally
./scripts/run-ci-tests.sh

# Run specific CI stage
./scripts/run-stage.sh unit
./scripts/run-stage.sh integration
./scripts/run-stage.sh e2e
```

## Advanced Testing Topics

### Property-Based Testing

```python
import hypothesis
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=100))
def test_agent_handles_various_request_lengths(request_text):
    result = agent.process_request(request_text)
    assert "command" in result
```

### Mutation Testing

```bash
# Install mutmut
pip install mutmut

# Run mutation testing
mutmut run --paths-to-mutate src/

# See results
mutmut html
```

### Contract Testing

```python
def test_openai_contract_compliance():
    # Test that our mock matches real OpenAI API contract
    pass
```

### Chaos Testing

```python
@pytest.mark.chaos
def test_agent_resilience_under_failure():
    # Test behavior when external services fail
    pass
```

## Resources and References

### Documentation
- [Pytest Documentation](https://docs.pytest.org/)
- [Mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

### Tools
- **pytest** - Test framework
- **pytest-cov** - Coverage reporting
- **pytest-mock** - Mocking utilities
- **pytest-benchmark** - Performance testing
- **pytest-xdist** - Parallel test execution

### Best Practices
- [Effective Python Testing](https://docs.python-guide.org/writing/tests/)
- [Test-Driven Development](https://martinfowler.com/articles/mocksArentStubs.html)
- [Testing Pyramid](https://martinfowler.com/bliki/TestPyramid.html)

---

For questions or issues with testing, please open an issue in the repository or contact the development team.