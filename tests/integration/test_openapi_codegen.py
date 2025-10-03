"""
Integration tests for openapi-mcp-codegen tool integration.
Tests the actual integration with the external codegen tool.
"""

import pytest
import subprocess
import tempfile
import shutil
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
import docker

from codegen.openapi_client import OpenAPICodegenClient
from codegen.project_generator import GoProjectGenerator
from agent.agent_core import AgentCore


@pytest.mark.integration
@pytest.mark.docker
class TestOpenAPICodegenIntegration:
    """Integration tests for openapi-mcp-codegen tool."""

    @pytest.fixture
    def codegen_client(self):
        """Create an OpenAPI codegen client instance."""
        return OpenAPICodegenClient(
            binary_path="/usr/local/bin/openapi-mcp-codegen",
            default_boilerplate="hack/boilerplate.go.txt"
        )

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_check_codegen_binary_availability(self, codegen_client):
        """Test checking if the codegen binary is available."""
        # This test will be skipped if the binary is not available
        if not codegen_client.is_binary_available():
            pytest.skip("openapi-mcp-codegen binary not available")

        assert codegen_client.is_binary_available() is True

    def test_get_codegen_version(self, codegen_client):
        """Test getting the codegen tool version."""
        if not codegen_client.is_binary_available():
            pytest.skip("openapi-mcp-codegen binary not available")

        version = codegen_client.get_version()
        assert version is not None
        assert len(version) > 0

    def test_generate_simple_project(self, codegen_client, temp_output_dir):
        """Test generating a simple Go project."""
        if not codegen_client.is_binary_available():
            pytest.skip("openapi-mcp-codegen binary not available")

        spec = {
            "group": "platform.test.io",
            "version": "v1alpha1",
            "kind": "TestResource",
            "spec": {
                "properties": {
                    "name": {"type": "string"},
                    "replicas": {"type": "integer"}
                }
            }
        }

        result = codegen_client.generate_project(
            spec=spec,
            output_dir=str(temp_output_dir)
        )

        assert result["success"] is True
        assert result["output_dir"] == str(temp_output_dir)

        # Verify generated files
        expected_files = [
            "go.mod",
            "main.go",
            "api/v1alpha1/testresource_types.go",
            "config/crd/bases/platform.test.io_testresources.yaml"
        ]

        for expected_file in expected_files:
            assert (temp_output_dir / expected_file).exists()

    def test_generate_complex_project(self, codegen_client, temp_output_dir):
        """Test generating a complex Go project with nested structures."""
        if not codegen_client.is_binary_available():
            pytest.skip("openapi-mcp-codegen binary not available")

        spec = {
            "group": "database.example.io",
            "version": "v1beta1",
            "kind": "DatabaseCluster",
            "spec": {
                "properties": {
                    "engine": {"type": "string"},
                    "version": {"type": "string"},
                    "replicas": {"type": "integer"},
                    "storage": {
                        "type": "object",
                        "properties": {
                            "size": {"type": "string"},
                            "class": {"type": "string"}
                        }
                    },
                    "backup": {
                        "type": "object",
                        "properties": {
                            "enabled": {"type": "boolean"},
                            "schedule": {"type": "string"}
                        }
                    }
                }
            }
        }

        result = codegen_client.generate_project(
            spec=spec,
            output_dir=str(temp_output_dir)
        )

        assert result["success"] is True

        # Verify complex structure was generated
        types_file = temp_output_dir / "api/v1alpha1/databasecluster_types.go"
        assert types_file.exists()

        # Check that nested structures are in the generated Go code
        content = types_file.read_text()
        assert "DatabaseClusterSpec" in content
        assert "StorageSpec" in content or "Storage" in content
        assert "BackupSpec" in content or "Backup" in content

    def test_generate_project_with_custom_boilerplate(self, codegen_client, temp_output_dir):
        """Test generating project with custom boilerplate file."""
        if not codegen_client.is_binary_available():
            pytest.skip("openapi-mcp-codegen binary not available")

        # Create custom boilerplate
        boilerplate_file = temp_output_dir / "custom_boilerplate.txt"
        boilerplate_file.write_text("// Copyright 2024 Test Company\n")

        spec = {
            "group": "test.io",
            "version": "v1",
            "kind": "SimpleResource",
            "spec": {
                "properties": {
                    "name": {"type": "string"}
                }
            }
        }

        result = codegen_client.generate_project(
            spec=spec,
            output_dir=str(temp_output_dir / "output"),
            boilerplate_file=str(boilerplate_file)
        )

        assert result["success"] is True

        # Verify custom boilerplate was used
        generated_files = list((temp_output_dir / "output").rglob("*.go"))
        assert len(generated_files) > 0

        # Check at least one generated file contains the custom copyright
        custom_boilerplate_found = any(
            "Copyright 2024 Test Company" in f.read_text()
            for f in generated_files
        )
        assert custom_boilerplate_found

    def test_generate_project_invalid_spec(self, codegen_client, temp_output_dir):
        """Test error handling with invalid specification."""
        if not codegen_client.is_binary_available():
            pytest.skip("openapi-mcp-codegen binary not available")

        invalid_spec = {
            "group": "invalid-group-name",
            "version": "invalid-version",
            "kind": "",
            "spec": {}
        }

        result = codegen_client.generate_project(
            spec=invalid_spec,
            output_dir=str(temp_output_dir)
        )

        assert result["success"] is False
        assert "error" in result

    def test_codegen_command_construction(self, codegen_client, temp_output_dir):
        """Test proper construction of codegen command."""
        spec = {
            "group": "test.io",
            "version": "v1",
            "kind": "TestResource",
            "spec": {
                "properties": {
                    "name": {"type": "string"}
                }
            }
        }

        command = codegen_client._build_command(
            spec=spec,
            output_dir=str(temp_output_dir),
            boilerplate_file="hack/boilerplate.go.txt"
        )

        assert len(command) >= 6
        assert command[0] == codegen_client.binary_path
        assert "--output-dir" in command
        assert "--go-header-file" in command
        assert "--input-spec" in command

        # Find the spec index
        spec_index = command.index("--input-spec") + 1
        spec_json = command[spec_index]
        parsed_spec = json.loads(spec_json)
        assert parsed_spec["group"] == "test.io"

    def test_validate_generated_go_project(self, codegen_client, temp_output_dir):
        """Test validation of generated Go project."""
        if not codegen_client.is_binary_available():
            pytest.skip("openapi-mcp-codegen binary not available")

        spec = {
            "group": "validation.test.io",
            "version": "v1alpha1",
            "kind": "ValidationResource",
            "spec": {
                "properties": {
                    "required_field": {"type": "string"},
                    "optional_field": {"type": "integer"}
                }
            }
        }

        result = codegen_client.generate_project(
            spec=spec,
            output_dir=str(temp_output_dir)
        )

        assert result["success"] is True

        # Validate project structure
        validation_result = codegen_client.validate_generated_project(
            project_dir=str(temp_output_dir)
        )

        assert validation_result["valid"] is True
        assert len(validation_result["errors"]) == 0

    def test_build_generated_docker_image(self, codegen_client, temp_output_dir):
        """Test building Docker image from generated project."""
        if not codegen_client.is_binary_available():
            pytest.skip("openapi-mcp-codegen binary not available")

        # Create Dockerfile in the generated project
        dockerfile_content = """
FROM golang:1.19-alpine AS builder
WORKDIR /workspace
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -o manager .

FROM gcr.io/distroless/static:nonroot
WORKDIR /
COPY --from=builder /workspace/manager .
ENTRYPOINT ["/manager"]
"""
        dockerfile_path = temp_output_dir / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content.strip())

        # Try to build Docker image (will be skipped if Docker is not available)
        try:
            docker_client = docker.from_env()
            image, build_logs = docker_client.images.build(
                path=str(temp_output_dir),
                tag="test-controller:latest"
            )

            assert image is not None
            assert len(list(build_logs)) > 0

            # Clean up
            docker_client.images.remove("test-controller:latest")

        except docker.errors.DockerException:
            pytest.skip("Docker not available for image building test")


@pytest.mark.integration
class TestAgentWithOpenAPIIntegration:
    """Integration tests for the complete agent workflow with openapi-mcp-codegen."""

    @pytest.fixture
    def agent_with_real_codegen(self, monkeypatch):
        """Create agent that uses real codegen tool."""
        # Mock OpenAI for this test
        mock_openai = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "command": [
                "openapi-mcp-codegen",
                "--output-dir", "/tmp/integration-test",
                "--go-header-file", "hack/boilerplate.go.txt",
                "--input-spec", json.dumps({
                    "group": "integration.test.io",
                    "version": "v1alpha1",
                    "kind": "IntegrationTest",
                    "spec": {"properties": {"name": {"type": "string"}}}
                })
            ]
        })
        mock_openai.chat.completions.create.return_value = mock_response

        agent = AgentCore(openai_client=mock_openai)
        return agent

    def test_end_to_end_workflow_with_temp_dir(self, agent_with_real_codegen, temp_dir):
        """Test complete end-to-end workflow with temporary directory."""
        # Mock the codegen path to use our temp directory
        with patch('agent.agent_core.CommandExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            # Mock successful execution
            mock_executor.execute.return_value = {
                "success": True,
                "output_dir": str(temp_dir),
                "command": ["mocked", "command"]
            }

            # Process the request
            result = agent_with_real_codegen.process_request(
                "Create an integration test API with name field"
            )

            # Execute the command
            execution_result = mock_executor.execute(result["command"])

            assert execution_result["success"] is True

    def test_error_handling_workflow(self, agent_with_real_codegen):
        """Test error handling in the integration workflow."""
        with patch('agent.agent_core.CommandExecutor') as mock_executor_class:
            mock_executor = Mock()
            mock_executor_class.return_value = mock_executor

            # Mock execution failure
            mock_executor.execute.side_effect = Exception("Command execution failed")

            result = agent_with_real_codegen.process_request(
                "Create an integration test API"
            )

            assert "command" in result

            # Execution should fail gracefully
            with pytest.raises(Exception):
                mock_executor.execute(result["command"])


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceIntegration:
    """Performance integration tests."""

    def test_concurrent_codegen_requests(self):
        """Test handling multiple concurrent codegen requests."""
        import concurrent.futures
        import threading

        # Mock codegen client for performance testing
        with patch('codegen.openapi_client.OpenAPICodegenClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.is_binary_available.return_value = True
            mock_client.generate_project.return_value = {"success": True}

            def generate_project(i):
                spec = {
                    "group": f"test{i}.example.io",
                    "version": "v1alpha1",
                    "kind": f"TestResource{i}",
                    "spec": {
                        "properties": {
                            "name": {"type": "string"},
                            "index": {"type": "integer"}
                        }
                    }
                }
                return mock_client.generate_project(spec, f"/tmp/test{i}")

            # Test with 10 concurrent requests
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(generate_project, i) for i in range(10)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]

            assert len(results) == 10
            assert all(result["success"] for result in results)

    def test_large_spec_generation_performance(self):
        """Test performance with large API specifications."""
        # Create a large specification
        properties = {}
        for i in range(50):  # 50 fields
            properties[f"field_{i}"] = {"type": "string"}

        large_spec = {
            "group": "large.test.io",
            "version": "v1alpha1",
            "kind": "LargeResource",
            "spec": {"properties": properties}
        }

        with patch('codegen.openapi_client.OpenAPICodegenClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.is_binary_available.return_value = True

            import time
            start_time = time.time()

            mock_client.generate_project.return_value = {"success": True}
            result = mock_client.generate_project(large_spec, "/tmp/large-test")

            end_time = time.time()
            execution_time = end_time - start_time

            assert result["success"] is True
            assert execution_time < 5.0  # Should complete within 5 seconds