"""
End-to-end tests for the complete AI-Assisted Platform Extension Generator workflow.
Tests the full pipeline from natural language input to working Go controller output.
"""

import pytest
import subprocess
import tempfile
import shutil
import json
import os
import time
from pathlib import Path
from unittest.mock import patch, Mock

# Import the main application modules
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from main import AIPlatformExtensionGenerator
from agent.agent_core import AgentCore
from codegen.openapi_client import OpenAPICodegenClient
from validation.go_validator import GoProjectValidator


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteWorkflow:
    """End-to-end tests for the complete workflow."""

    @pytest.fixture
    def generator(self):
        """Create the main generator instance."""
        return AIPlatformExtensionGenerator()

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing."""
        workspace = Path(tempfile.mkdtemp(prefix="e2e-test-"))
        yield workspace
        shutil.rmtree(workspace, ignore_errors=True)

    def test_vector_db_complete_workflow(self, generator, temp_workspace):
        """Test complete workflow for VectorDB API generation."""
        # This is the exact scenario described in PLANS.md
        natural_language_request = (
            "I need to create a VectorDB API for our new AI platform. "
            "The spec should include a string for engine_type (like 'pinecone' or 'weaviate') "
            "and an integer for the number of replicas."
        )

        # Execute the complete workflow
        with patch('openai.OpenAI') as mock_openai:
            # Mock OpenAI response
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "command": [
                    "openapi-mcp-codegen",
                    "--output-dir", str(temp_workspace / "vectordb"),
                    "--go-header-file", "hack/boilerplate.go.txt",
                    "--input-spec", json.dumps({
                        "group": "platform.ai.example.io",
                        "version": "v1alpha1",
                        "kind": "VectorDB",
                        "spec": {
                            "properties": {
                                "engine_type": {"type": "string"},
                                "replicas": {"type": "integer"}
                            }
                        }
                    })
                ]
            })
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            # Mock the codegen execution
            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(returncode=0)

                # Execute the workflow
                result = generator.generate_extension(
                    request=natural_language_request,
                    output_dir=str(temp_workspace)
                )

                # Verify the workflow completed successfully
                assert result["success"] is True
                assert "project_path" in result
                assert "generated_files" in result

    def test_notebook_crd_complete_workflow(self, generator, temp_workspace):
        """Test complete workflow for Notebook CRD generation."""
        natural_language_request = (
            "I need a Notebook CRD for our data science team. "
            "It should have a cpu field and a memory field, both strings."
        )

        with patch('openai.OpenAI') as mock_openai:
            # Mock OpenAI response for Notebook
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "command": [
                    "openapi-mcp-codegen",
                    "--output-dir", str(temp_workspace / "notebook"),
                    "--go-header-file", "hack/boilerplate.go.txt",
                    "--input-spec", json.dumps({
                        "group": "datascience.example.io",
                        "version": "v1alpha1",
                        "kind": "Notebook",
                        "spec": {
                            "properties": {
                                "cpu": {"type": "string"},
                                "memory": {"type": "string"}
                            }
                        }
                    })
                ]
            })
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(returncode=0)

                result = generator.generate_extension(
                    request=natural_language_request,
                    output_dir=str(temp_workspace)
                )

                assert result["success"] is True
                assert result["spec"]["kind"] == "Notebook"
                assert "cpu" in result["spec"]["spec"]["properties"]
                assert "memory" in result["spec"]["spec"]["properties"]

    def test_complex_microservice_api_workflow(self, generator, temp_workspace):
        """Test workflow for a complex microservice API."""
        natural_language_request = (
            "Create a comprehensive Microservice API with fields for service discovery, "
            "load balancing, health checks, circuit breakers, retries, timeouts, "
            "authentication, authorization, rate limiting, monitoring, logging, tracing, "
            "and deployment configuration"
        )

        with patch('openai.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "command": [
                    "openapi-mcp-codegen",
                    "--output-dir", str(temp_workspace / "microservice"),
                    "--go-header-file", "hack/boilerplate.go.txt",
                    "--input-spec", json.dumps({
                        "group": "microservice.example.io",
                        "version": "v1beta1",
                        "kind": "Microservice",
                        "spec": {
                            "properties": {
                                "service_discovery": {"type": "object"},
                                "load_balancing": {"type": "object"},
                                "health_checks": {"type": "object"},
                                "circuit_breakers": {"type": "object"},
                                "retries": {"type": "object"},
                                "timeouts": {"type": "object"},
                                "authentication": {"type": "object"},
                                "authorization": {"type": "object"},
                                "rate_limiting": {"type": "object"},
                                "monitoring": {"type": "object"},
                                "logging": {"type": "object"},
                                "tracing": {"type": "object"},
                                "deployment": {"type": "object"}
                            }
                        }
                    })
                ]
            })
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(returncode=0)

                result = generator.generate_extension(
                    request=natural_language_request,
                    output_dir=str(temp_workspace)
                )

                assert result["success"] is True
                assert len(result["spec"]["spec"]["properties"]) >= 13

    def test_error_handling_invalid_request(self, generator, temp_workspace):
        """Test error handling with invalid natural language requests."""
        invalid_requests = [
            "",  # Empty request
            "Create something vague",  # Too vague
            "Invalid syntax request with {unclosed bracket",  # Invalid syntax
        ]

        for invalid_request in invalid_requests:
            with patch('openai.OpenAI') as mock_openai:
                mock_client = Mock()
                # Mock OpenAI to return an error response
                mock_client.chat.completions.create.side_effect = Exception("Invalid request")
                mock_openai.return_value = mock_client

                result = generator.generate_extension(
                    request=invalid_request,
                    output_dir=str(temp_workspace)
                )

                assert result["success"] is False
                assert "error" in result

    def test_workflow_with_custom_configuration(self, generator, temp_workspace):
        """Test workflow with custom configuration."""
        custom_config = {
            "default_group": "custom.platform.io",
            "default_version": "v1beta1",
            "output_directory": str(temp_workspace / "custom-output"),
            "boilerplate_file": str(temp_workspace / "custom-boilerplate.txt")
        }

        # Create custom boilerplate file
        custom_boilerplate = temp_workspace / "custom-boilerplate.txt"
        custom_boilerplate.write_text("// Copyright 2024 Custom Platform\n")

        natural_language_request = "Create a simple ConfigMap API with data field"

        with patch('openai.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "command": [
                    "openapi-mcp-codegen",
                    "--output-dir", custom_config["output_directory"],
                    "--go-header-file", custom_config["boilerplate_file"],
                    "--input-spec", json.dumps({
                        "group": custom_config["default_group"],
                        "version": custom_config["default_version"],
                        "kind": "ConfigMap",
                        "spec": {
                            "properties": {
                                "data": {"type": "object"}
                            }
                        }
                    })
                ]
            })
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            with patch('subprocess.run') as mock_subprocess:
                mock_subprocess.return_value = Mock(returncode=0)

                result = generator.generate_extension(
                    request=natural_language_request,
                    output_dir=str(temp_workspace),
                    config=custom_config
                )

                assert result["success"] is True
                assert result["spec"]["group"] == custom_config["default_group"]
                assert result["spec"]["version"] == custom_config["default_version"]


@pytest.mark.e2e
@pytest.mark.kubernetes
class TestKubernetesIntegration:
    """End-to-end tests with Kubernetes integration."""

    @pytest.fixture
    def kind_cluster(self):
        """Create a kind cluster for testing (if available)."""
        # This fixture will be skipped if kind is not available
        try:
            subprocess.run(["kind", "version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("kind not available")

        cluster_name = "test-extension-cluster"

        # Create cluster
        subprocess.run([
            "kind", "create", "cluster",
            "--name", cluster_name,
            "--wait", "300s"
        ], check=True)

        yield cluster_name

        # Cleanup
        subprocess.run([
            "kind", "delete", "cluster",
            "--name", cluster_name
        ], check=False)

    def test_deploy_generated_controller_to_kubernetes(self, kind_cluster):
        """Test deploying a generated controller to Kubernetes."""
        temp_workspace = Path(tempfile.mkdtemp(prefix="k8s-test-"))

        try:
            # Generate a simple controller
            with patch('openai.OpenAI') as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = json.dumps({
                    "command": [
                        "openapi-mcp-codegen",
                        "--output-dir", str(temp_workspace / "test-controller"),
                        "--go-header-file", "hack/boilerplate.go.txt",
                        "--input-spec", json.dumps({
                            "group": "test.example.io",
                            "version": "v1alpha1",
                            "kind": "TestResource",
                            "spec": {
                                "properties": {
                                    "name": {"type": "string"}
                                }
                            }
                        })
                    ]
                })
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai.return_value = mock_client

                # Mock the file generation
                controller_dir = temp_workspace / "test-controller"
                controller_dir.mkdir(parents=True)

                # Create minimal generated files
                (controller_dir / "go.mod").write_text("""
module test-controller
go 1.19
""")

                (controller_dir / "main.go").write_text("""
package main
func main() {}
""")

                (controller_dir / "config" / "crd" / "bases").mkdir(parents=True)
                (controller_dir / "config" / "crd" / "bases" / "test.example.io_testresources.yaml").write_text("""
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: testresources.test.example.io
spec:
  group: test.example.io
  names:
    kind: TestResource
    plural: testresources
  scope: Namespaced
  versions:
  - name: v1alpha1
    served: true
    storage: true
""")

                # Apply CRD to the cluster
                kubectl_apply = subprocess.run([
                    "kubectl", "apply", "-f",
                    str(controller_dir / "config" / "crd" / "bases" / "test.example.io_testresources.yaml")
                ], capture_output=True, text=True)

                assert kubectl_apply.returncode == 0
                assert "customresourcedefinition" in kubectl_apply.stdout.lower()

                # Verify CRD was created
                kubectl_get = subprocess.run([
                    "kubectl", "get", "crd", "testresources.test.example.io"
                ], capture_output=True, text=True)

                assert kubectl_get.returncode == 0

        finally:
            shutil.rmtree(temp_workspace, ignore_errors=True)


@pytest.mark.e2e
@pytest.mark.docker
class TestDockerIntegration:
    """End-to-end tests with Docker integration."""

    def test_build_and_test_generated_controller_image(self):
        """Test building and testing a Docker image from generated controller."""
        temp_workspace = Path(tempfile.mkdtemp(prefix="docker-test-"))

        try:
            # Create a minimal generated project structure
            project_dir = temp_workspace / "test-controller"
            project_dir.mkdir(parents=True)

            # Create Go files
            (project_dir / "go.mod").write_text("""
module test-controller
go 1.19
""")

            (project_dir / "main.go").write_text("""
package main

import (
    "fmt"
    "os"
)

func main() {
    fmt.Println("Test controller started successfully")
    os.Exit(0)
}
""")

            # Create Dockerfile
            dockerfile_content = """
FROM golang:1.19-alpine AS builder
WORKDIR /workspace
COPY go.mod ./
RUN go mod download || true
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -o manager .

FROM gcr.io/distroless/static:nonroot
WORKDIR /
COPY --from=builder /workspace/manager .
USER 65532:65532
ENTRYPOINT ["/manager"]
"""
            (project_dir / "Dockerfile").write_text(dockerfile_content.strip())

            # Try to build Docker image
            try:
                import docker
                docker_client = docker.from_env()

                image, build_logs = docker_client.images.build(
                    path=str(project_dir),
                    tag="test-controller:latest",
                    rm=True
                )

                assert image is not None

                # Test running the container
                container = docker_client.containers.run(
                    "test-controller:latest",
                    detach=True
                )

                # Wait a moment and check the container exits successfully
                time.sleep(2)
                container.reload()

                assert container.status == "exited"
                assert container.attrs["State"]["ExitCode"] == 0

                # Get logs
                logs = container.logs().decode('utf-8')
                assert "Test controller started successfully" in logs

                # Cleanup
                container.remove()
                docker_client.images.remove("test-controller:latest")

            except docker.errors.DockerException:
                pytest.skip("Docker not available for integration test")
            except ImportError:
                pytest.skip("Docker Python library not available")

        finally:
            shutil.rmtree(temp_workspace, ignore_errors=True)


@pytest.mark.e2e
class TestRealWorldScenarios:
    """Real-world scenario tests."""

    def test_platform_engineer_workflow(self):
        """Test a realistic platform engineer workflow."""
        temp_workspace = Path(tempfile.mkdtemp(prefix="platform-test-"))

        # Scenario: Platform engineer needs to create multiple APIs
        scenarios = [
            {
                "name": "DatabaseCluster",
                "request": "Create a DatabaseCluster API with fields for engine (postgres, mysql), version (string), replicas (int), storage_size (string), and backup_enabled (boolean)"
            },
            {
                "name": "CacheCluster",
                "request": "Create a CacheCluster API for Redis/Memcached with engine_type, capacity, shard_count, and eviction_policy fields"
            },
            {
                "name": "MessageQueue",
                "request": "Create a MessageQueue API with fields for broker_type (kafka, rabbitmq), topic_count, partition_count, and retention_days"
            }
        ]

        results = []

        for scenario in scenarios:
            with patch('openai.OpenAI') as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]

                # Generate appropriate spec based on scenario
                if scenario["name"] == "DatabaseCluster":
                    spec = {
                        "group": "database.platform.io",
                        "version": "v1alpha1",
                        "kind": "DatabaseCluster",
                        "spec": {
                            "properties": {
                                "engine": {"type": "string"},
                                "version": {"type": "string"},
                                "replicas": {"type": "integer"},
                                "storage_size": {"type": "string"},
                                "backup_enabled": {"type": "boolean"}
                            }
                        }
                    }
                elif scenario["name"] == "CacheCluster":
                    spec = {
                        "group": "cache.platform.io",
                        "version": "v1alpha1",
                        "kind": "CacheCluster",
                        "spec": {
                            "properties": {
                                "engine_type": {"type": "string"},
                                "capacity": {"type": "string"},
                                "shard_count": {"type": "integer"},
                                "eviction_policy": {"type": "string"}
                            }
                        }
                    }
                else:  # MessageQueue
                    spec = {
                        "group": "messaging.platform.io",
                        "version": "v1alpha1",
                        "kind": "MessageQueue",
                        "spec": {
                            "properties": {
                                "broker_type": {"type": "string"},
                                "topic_count": {"type": "integer"},
                                "partition_count": {"type": "integer"},
                                "retention_days": {"type": "integer"}
                            }
                        }
                    }

                mock_response.choices[0].message.content = json.dumps({
                    "command": [
                        "openapi-mcp-codegen",
                        "--output-dir", str(temp_workspace / scenario["name"].lower()),
                        "--go-header-file", "hack/boilerplate.go.txt",
                        "--input-spec", json.dumps(spec)
                    ]
                })
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai.return_value = mock_client

                with patch('subprocess.run') as mock_subprocess:
                    mock_subprocess.return_value = Mock(returncode=0)

                    generator = AIPlatformExtensionGenerator()
                    result = generator.generate_extension(
                        request=scenario["request"],
                        output_dir=str(temp_workspace)
                    )

                    results.append({
                        "scenario": scenario["name"],
                        "result": result
                    })

        # Verify all scenarios completed successfully
        assert len(results) == 3
        for result in results:
            assert result["result"]["success"] is True
            assert result["result"]["spec"]["kind"] == result["scenario"]

        # Cleanup
        shutil.rmtree(temp_workspace, ignore_errors=True)

    def test_batch_api_generation(self):
        """Test batch generation of multiple APIs."""
        temp_workspace = Path(tempfile.mkdtemp(prefix="batch-test-"))

        batch_requests = [
            "Create a ConfigMap API with data field",
            "Create a Secret API with data field",
            "Create a Service API with selector and ports fields"
        ]

        results = []

        for i, request in enumerate(batch_requests):
            with patch('openai.OpenAI') as mock_openai:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = json.dumps({
                    "command": [
                        "openapi-mcp-codegen",
                        "--output-dir", str(temp_workspace / f"api-{i}"),
                        "--go-header-file", "hack/boilerplate.go.txt",
                        "--input-spec", json.dumps({
                            "group": f"batch{i}.test.io",
                            "version": "v1alpha1",
                            "kind": f"API{i}",
                            "spec": {"properties": {"name": {"type": "string"}}}
                        })
                    ]
                })
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai.return_value = mock_client

                with patch('subprocess.run') as mock_subprocess:
                    mock_subprocess.return_value = Mock(returncode=0)

                    generator = AIPlatformExtensionGenerator()
                    result = generator.generate_extension(
                        request=request,
                        output_dir=str(temp_workspace)
                    )

                    results.append(result)

        # Verify batch generation completed
        assert len(results) == len(batch_requests)
        assert all(result["success"] for result in results)

        # Cleanup
        shutil.rmtree(temp_workspace, ignore_errors=True)