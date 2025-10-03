"""
Mock implementations for OpenAI API and external dependencies.
Provides comprehensive mocking for unit and integration tests.
"""

import json
from unittest.mock import Mock, patch
from typing import Dict, Any, List, Optional
import time

from .test_data.agent_requests import (
    get_mock_openai_response,
    get_sample_request,
    get_error_scenario
)


class MockOpenAIClient:
    """Mock OpenAI client for testing."""

    def __init__(self, model: str = "gpt-4", temperature: float = 0.1, max_tokens: int = 1000):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.call_count = 0
        self.call_history = []
        self.responses = {}
        self._setup_default_responses()

    def _setup_default_responses(self):
        """Setup default mock responses."""
        self.responses.update({
            "simple_vector_db": get_mock_openai_response("simple_vector_db"),
            "notebook_crd": get_mock_openai_response("notebook_crd"),
            "error_response": get_mock_openai_response("error_response"),
            "missing_command": get_mock_openai_response("missing_command")
        })

    def chat(self):
        """Return chat completions interface."""
        return MockChatCompletions(self)

    def set_response(self, key: str, response: Dict[str, Any]):
        """Set a custom response for testing."""
        self.responses[key] = response

    def get_call_history(self) -> List[Dict[str, Any]]:
        """Get history of all calls made to this mock."""
        return self.call_history.copy()

    def reset_call_history(self):
        """Reset the call history."""
        self.call_history = []


class MockChatCompletions:
    """Mock chat completions interface."""

    def __init__(self, client: MockOpenAIClient):
        self.client = client

    def create(self, messages: List[Dict[str, str]], **kwargs) -> Mock:
        """Mock chat completion creation."""
        self.client.call_count += 1

        # Record the call
        call_record = {
            "messages": messages,
            "model": kwargs.get("model", self.client.model),
            "temperature": kwargs.get("temperature", self.client.temperature),
            "max_tokens": kwargs.get("max_tokens", self.client.max_tokens),
            "timestamp": time.time()
        }
        self.client.call_history.append(call_record)

        # Generate response based on the last user message
        user_message = messages[-1]["content"] if messages else ""
        response = self._generate_response(user_message)

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = response

        return mock_response

    def _generate_response(self, user_message: str) -> str:
        """Generate appropriate response based on user message."""
        # Simple pattern matching for common requests
        if "vectordb" in user_message.lower():
            return json.dumps(
                get_sample_request("simple_vector_db")["expected_spec"]
            )
        elif "notebook" in user_message.lower():
            return json.dumps(
                get_sample_request("notebook_crd")["expected_spec"]
            )
        elif "clusterclaim" in user_message.lower():
            return json.dumps(
                get_sample_request("cluster_claim")["expected_spec"]
            )
        elif "database" in user_message.lower():
            return json.dumps({
                "command": [
                    "openapi-mcp-codegen",
                    "--output-dir", "/tmp/database",
                    "--go-header-file", "hack/boilerplate.go.txt",
                    "--input-spec", json.dumps({
                        "group": "database.example.io",
                        "version": "v1alpha1",
                        "kind": "Database",
                        "spec": {
                            "properties": {
                                "engine": {"type": "string"},
                                "replicas": {"type": "integer"}
                            }
                        }
                    })
                ]
            })
        else:
            # Default response for any other request
            return json.dumps({
                "command": [
                    "openapi-mcp-codegen",
                    "--output-dir", "/tmp/default",
                    "--go-header-file", "hack/boilerplate.go.txt",
                    "--input-spec", json.dumps({
                        "group": "default.example.io",
                        "version": "v1alpha1",
                        "kind": "DefaultResource",
                        "spec": {
                            "properties": {
                                "name": {"type": "string"}
                            }
                        }
                    })
                ]
            })


class MockDockerClient:
    """Mock Docker client for testing."""

    def __init__(self):
        self.containers = MockContainers()
        self.images = MockImages()
        self.api_client = MockAPIClient()


class MockContainers:
    """Mock Docker containers interface."""

    def __init__(self):
        self.created_containers = []
        self.running_containers = []

    def get(self, container_id: str) -> Mock:
        """Get a container by ID."""
        container = Mock()
        container.id = container_id
        container.status = "running"
        container.logs.return_value = b"Mock container logs"
        container.reload.return_value = None
        container.remove.return_value = None
        return container

    def run(self, image: str, **kwargs) -> Mock:
        """Run a container."""
        container = Mock()
        container.id = f"mock_container_{len(self.created_containers)}"
        container.status = "running"
        container.logs.return_value = b"Mock container logs"
        container.reload.return_value = None
        container.remove.return_value = None

        self.created_containers.append(container)
        self.running_containers.append(container)

        return container

    def list(self, all: bool = False) -> List[Mock]:
        """List containers."""
        return self.running_containers.copy()


class MockImages:
    """Mock Docker images interface."""

    def __init__(self):
        self.built_images = []
        self.pulled_images = []

    def get(self, image_name: str) -> Mock:
        """Get an image by name."""
        image = Mock()
        image.id = f"mock_image_{image_name}"
        image.tags = [image_name]
        return image

    def build(self, path: str, tag: str, **kwargs) -> Mock:
        """Build an image."""
        image = Mock()
        image.id = f"mock_image_{tag}"
        image.tags = [tag]

        # Simulate build logs
        build_logs = [
            {"stream": "Step 1/5 : FROM golang:1.19-alpine"},
            {"stream": "Step 2/5 : WORKDIR /workspace"},
            {"stream": "Step 3/5 : COPY go.mod ./"},
            {"stream": "Step 4/5 : RUN go mod download"},
            {"stream": "Step 5/5 : COPY . ."},
            {"stream": "Successfully built mock_image"},
            {"aux": {"ID": image.id}}
        ]

        self.built_images.append(image)

        # Return an iterator for build logs
        return iter(build_logs)

    def remove(self, image_name: str, **kwargs) -> None:
        """Remove an image."""
        self.built_images = [
            img for img in self.built_images
            if image_name not in img.tags
        ]

    def pull(self, image_name: str, **kwargs) -> Mock:
        """Pull an image."""
        image = Mock()
        image.id = f"mock_image_{image_name}"
        image.tags = [image_name]

        self.pulled_images.append(image)
        return image


class MockAPIClient:
    """Mock Docker API client."""

    def __init__(self):
        self.calls = []

    def build(self, **kwargs):
        """Mock build API call."""
        self.calls.append(("build", kwargs))
        return Mock()


class MockKubernetesClient:
    """Mock Kubernetes client for testing."""

    def __init__(self):
        self.api_client = Mock()
        self.core_v1 = MockCoreV1Api()
        self.apiextensions_v1 = MockApiextensionsV1Api()
        self.apps_v1 = MockAppsV1Api()
        self.rbac_v1 = MockRbacV1Api()


class MockCoreV1Api:
    """Mock Kubernetes CoreV1Api."""

    def __init__(self):
        self.namespaces = Mock()
        self.config_maps = Mock()
        self.secrets = Mock()
        self.pods = Mock()
        self.services = Mock()


class MockApiextensionsV1Api:
    """Mock Kubernetes ApiextensionsV1Api."""

    def __init__(self):
        self.custom_resource_definitions = Mock()

    def create_custom_resource_definition(self, body, **kwargs):
        """Mock CRD creation."""
        crd = Mock()
        crd.metadata.name = body["metadata"]["name"]
        crd.spec.group = body["spec"]["group"]
        crd.spec.names.kind = body["spec"]["names"]["kind"]
        return crd

    def read_custom_resource_definition(self, name, **kwargs):
        """Mock CRD read."""
        crd = Mock()
        crd.metadata.name = name
        crd.spec.group = "test.example.io"
        crd.spec.names.kind = "TestResource"
        return crd

    def delete_custom_resource_definition(self, name, **kwargs):
        """Mock CRD deletion."""
        return Mock()


class MockAppsV1Api:
    """Mock Kubernetes AppsV1Api."""

    def __init__(self):
        self.deployments = Mock()
        self.replica_sets = Mock()
        self.stateful_sets = Mock()


class MockRbacV1Api:
    """Mock Kubernetes RbacV1Api."""

    def __init__(self):
        self.roles = Mock()
        self.role_bindings = Mock()
        self.cluster_roles = Mock()
        self.cluster_role_bindings = Mock()


class MockSubprocess:
    """Mock subprocess for testing."""

    def __init__(self):
        self.call_history = []
        self.default_returncode = 0
        self.default_output = b"Mock command output"
        self.default_error = b""

    def run(self, command, **kwargs):
        """Mock subprocess.run."""
        self.call_history.append({
            "command": command,
            "kwargs": kwargs,
            "timestamp": time.time()
        })

        result = Mock()
        result.returncode = self.default_returncode
        result.stdout = self.default_output
        result.stderr = self.default_error

        return result

    def set_returncode(self, code: int):
        """Set the return code for next calls."""
        self.default_returncode = code

    def set_output(self, output: bytes):
        """Set the output for next calls."""
        self.default_output = output

    def set_error(self, error: bytes):
        """Set the error output for next calls."""
        self.default_error = error

    def raise_exception(self, exception: Exception):
        """Make next call raise an exception."""
        self._exception = exception

    def run_with_exception(self, command, **kwargs):
        """Run with configured exception."""
        if hasattr(self, '_exception'):
            raise self._exception
        return self.run(command, **kwargs)


# Context managers for easy mocking
class MockOpenAIContext:
    """Context manager for mocking OpenAI."""

    def __init__(self, responses: Optional[Dict[str, Any]] = None):
        self.responses = responses or {}
        self.mock_client = None
        self.patcher = None

    def __enter__(self) -> MockOpenAIClient:
        self.patcher = patch('openai.OpenAI')
        mock_class = self.patcher.start()

        self.mock_client = MockOpenAIClient()
        if self.responses:
            for key, response in self.responses.items():
                self.mock_client.set_response(key, response)

        mock_class.return_value = self.mock_client
        return self.mock_client

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.patcher.stop()


class MockDockerContext:
    """Context manager for mocking Docker."""

    def __init__(self):
        self.mock_client = None
        self.patcher = None

    def __enter__(self) -> MockDockerClient:
        self.patcher = patch('docker.from_env')
        mock_function = self.patcher.start()

        self.mock_client = MockDockerClient()
        mock_function.return_value = self.mock_client
        return self.mock_client

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.patcher.stop()


class MockKubernetesContext:
    """Context manager for mocking Kubernetes."""

    def __init__(self):
        self.mock_client = None
        self.config_patcher = None
        self.client_patcher = None

    def __enter__(self) -> MockKubernetesClient:
        self.config_patcher = patch('kubernetes.config.load_kube_config')
        self.client_patcher = patch('kubernetes.client.ApiClient')

        self.config_patcher.start()
        mock_class = self.client_patcher.start()

        self.mock_client = MockKubernetesClient()
        mock_class.return_value = self.mock_client.api_client

        return self.mock_client

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.config_patcher.stop()
        self.client_patcher.stop()


class MockSubprocessContext:
    """Context manager for mocking subprocess."""

    def __init__(self, returncode: int = 0, output: bytes = b"", error: bytes = b""):
        self.returncode = returncode
        self.output = output
        self.error = error
        self.mock_subprocess = None
        self.patcher = None

    def __enter__(self) -> MockSubprocess:
        self.patcher = patch('subprocess.run')
        mock_function = self.patcher.start()

        self.mock_subprocess = MockSubprocess()
        self.mock_subprocess.set_returncode(self.returncode)
        self.mock_subprocess.set_output(self.output)
        self.mock_subprocess.set_error(self.error)

        mock_function.side_effect = self.mock_subprocess.run
        return self.mock_subprocess

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.patcher.stop()


# Utility functions for creating common mock scenarios
def create_mock_openai_with_error(error_scenario: str) -> MockOpenAIContext:
    """Create OpenAI mock with specific error scenario."""
    scenario = get_error_scenario(error_scenario)

    class ErrorMockOpenAIClient(MockOpenAIClient):
        def __init__(self):
            super().__init__()
            self.error = scenario["exception"]

        def chat(self):
            class ErrorChatCompletions:
                def create(self, *args, **kwargs):
                    raise self.error
            return ErrorChatCompletions()

    class ErrorMockOpenAIContext:
        def __enter__(self):
            patcher = patch('openai.OpenAI')
            mock_class = patcher.start()
            mock_class.return_value = ErrorMockOpenAIClient()
            self.patcher = patcher
            return mock_class.return_value

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.patcher.stop()

    return ErrorMockOpenAIContext()


def create_mock_subprocess_with_error(returncode: int = 1) -> MockSubprocessContext:
    """Create subprocess mock that returns error code."""
    return MockSubprocessContext(returncode=returncode)


def create_mock_docker_with_build_error():
    """Create Docker mock that fails on build."""
    class ErrorDockerClient(MockDockerClient):
        def __init__(self):
            super().__init__()

        class ErrorImages(MockImages):
            def build(self, *args, **kwargs):
                raise Exception("Docker build failed")

        def __init__(self):
            super().__init__()
            self.images = self.ErrorImages()

    class ErrorDockerContext:
        def __enter__(self):
            patcher = patch('docker.from_env')
            mock_function = patcher.start()
            mock_function.return_value = ErrorDockerClient()
            self.patcher = patcher
            return mock_function.return_value

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.patcher.stop()

    return ErrorDockerContext()


# Global mock instances for use across tests
mock_openai_client = MockOpenAIClient()
mock_docker_client = MockDockerClient()
mock_kubernetes_client = MockKubernetesClient()
mock_subprocess = MockSubprocess()