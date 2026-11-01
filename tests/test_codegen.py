"""
Tests for the Code Generation module
"""

import pytest
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call
from src.ai_platform_generator.codegen import CodeGenerator, GenerationResult
from src.ai_platform_generator.agent import CodegenRequest


class TestCodeGenerator:
    """Test cases for CodeGenerator"""

    def setup_method(self):
        """Set up test fixtures"""
        self.generator = CodeGenerator()
        self.sample_request = CodegenRequest(
            group="platform.test.io",
            version="v1alpha1",
            kind="TestResource",
            spec_properties={
                "name": {"type": "string"},
                "count": {"type": "integer"}
            },
            output_dir="/tmp/testresource",
            description="Test resource for testing"
        )

    def test_initialization(self):
        """Generator initializes without the MCP tool (graceful degradation to K8s-only mode)."""
        assert self.generator.openapi_codegen_path is None or \
            Path(self.generator.openapi_codegen_path).exists()

    @patch('shutil.which')
    def test_find_codegen_tool_in_path(self, mock_which):
        """Test finding codegen tool in PATH"""
        mock_which.return_value = "/usr/bin/openapi_mcp_codegen"

        generator = CodeGenerator()
        assert generator.openapi_codegen_path == "/usr/bin/openapi_mcp_codegen"

    @patch('shutil.which')
    def test_find_codegen_tool_in_repo(self, mock_which, tmp_path):
        """Test finding codegen tool in a cloned sibling repository"""
        mock_which.return_value = None

        main_py = tmp_path / "openapi-mcp-codegen" / "openapi_mcp_codegen" / "__main__.py"
        main_py.parent.mkdir(parents=True)
        main_py.touch()

        generator = CodeGenerator()
        assert generator._find_codegen_tool(search_root=tmp_path).endswith("__main__.py")

    @patch('shutil.which')
    def test_find_codegen_tool_not_found(self, mock_which, tmp_path):
        """Without the tool anywhere, _find_codegen_tool raises and __init__ degrades to None"""
        mock_which.return_value = None

        with pytest.raises(FileNotFoundError, match="openapi-mcp-codegen tool not found"):
            CodeGenerator()._find_codegen_tool(search_root=tmp_path)

        generator = CodeGenerator()
        assert generator.openapi_codegen_path is None

    def test_generate_openapi_spec(self):
        """Test OpenAPI specification generation"""
        spec = self.generator.generate_openapi_spec(self.sample_request)

        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["title"] == "TestResource API"
        assert spec["info"]["version"] == "v1alpha1"
        assert "TestResource" in spec["components"]["schemas"]

        schema = spec["components"]["schemas"]["TestResource"]
        assert "spec" in schema["properties"]
        assert "name" in schema["properties"]["spec"]["properties"]
        assert "count" in schema["properties"]["spec"]["properties"]

    def test_generate_openapi_spec_complex_properties(self):
        """Test OpenAPI spec with complex property types"""
        request = CodegenRequest(
            group="platform.test.io",
            version="v1alpha1",
            kind="ComplexResource",
            spec_properties={
                "tags": {"type": "array", "description": "List of tags"},
                "config": {"type": "object", "description": "Configuration object"},
                "enabled": {"type": "boolean", "description": "Enable flag"}
            },
            output_dir="/tmp/complex",
            description="Complex resource"
        )

        spec = self.generator.generate_openapi_spec(request)
        schema = spec["components"]["schemas"]["ComplexResource"]["properties"]["spec"]

        assert schema["properties"]["tags"]["type"] == "array"
        assert schema["properties"]["config"]["type"] == "object"
        assert schema["properties"]["enabled"]["type"] == "boolean"

    @patch('subprocess.run')
    def test_generate_mcp_server_success(self, mock_subprocess, tmp_path):
        """Test successful MCP server generation"""
        mock_subprocess.return_value.stdout = "Generation successful"
        mock_subprocess.return_value.stderr = ""

        # A file the generator should discover in the output directory
        (tmp_path / "server.py").touch()
        request = self.sample_request
        request.output_dir = str(tmp_path)

        # Inject a tool path so the graceful-degradation early-return is bypassed
        generator = CodeGenerator(openapi_codegen_path="/fake/openapi_mcp_codegen")
        result = generator.generate_mcp_server(request)

        assert result.success is True
        assert result.stdout == "Generation successful"
        assert len(result.generated_files) > 0

    @patch('subprocess.run')
    def test_generate_mcp_server_failure(self, mock_subprocess, tmp_path):
        """Test MCP server generation failure"""
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, 'cmd', stderr="simulated tool failure")

        request = self.sample_request
        request.output_dir = str(tmp_path)

        # Inject a tool path so the graceful-degradation early-return is bypassed
        generator = CodeGenerator(openapi_codegen_path="/fake/openapi_mcp_codegen")
        result = generator.generate_mcp_server(request)

        assert result.success is False
        assert "simulated tool failure" in result.stderr

    def test_generate_kubernetes_controller_success(self):
        """Test successful Kubernetes controller generation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.sample_request.output_dir = temp_dir

            result = self.generator.generate_kubernetes_controller(self.sample_request)

            assert result.success is True
            assert len(result.generated_files) > 0

            # Check that expected files were created
            output_path = Path(temp_dir)
            assert (output_path / "main.go").exists()
            assert (output_path / "Dockerfile").exists()
            assert (output_path / "go.mod").exists()
            assert (output_path / "api" / "v1alpha1" / "testresource_types.go").exists()
            assert (output_path / "internal" / "controller" / "testresource_controller.go").exists()

    def test_generate_main_go_content(self):
        """Test main.go content generation"""
        content = self.generator._generate_main_go(self.sample_request)

        assert "package main" in content
        assert "TestResourceReconciler" in content
        assert "platform.test.io/v1alpha1" in content
        assert "controller-runtime" in content

    def test_generate_types_go_content(self):
        """Test types.go content generation"""
        content = self.generator._generate_types_go(self.sample_request)

        assert "package v1alpha1" in content
        assert "TestResourceSpec" in content
        assert "TestResourceStatus" in content
        assert "name string" in content
        assert "count int32" in content

    def test_generate_controller_go_content(self):
        """Test controller.go content generation"""
        content = self.generator._generate_controller_go(self.sample_request)

        assert "package controller" in content
        assert "TestResourceReconciler" in content
        assert "Reconcile" in content
        assert "SetupWithManager" in content

    def test_generate_dockerfile_content(self):
        """Test Dockerfile content generation"""
        content = self.generator._generate_dockerfile(self.sample_request)

        assert "FROM golang:1.21 as builder" in content
        assert "FROM gcr.io/distroless/static:nonroot" in content
        assert "WORKDIR /workspace" in content

    def test_generate_go_mod_content(self):
        """Test go.mod content generation"""
        content = self.generator._generate_go_mod(self.sample_request)

        assert "module platform.test.io" in content
        assert "go 1.21" in content
        assert "k8s.io/api" in content
        assert "sigs.k8s.io/controller-runtime" in content

    def test_map_type_to_go(self):
        """Test type mapping from JSON to Go"""
        assert self.generator._map_type_to_go("string") == "string"
        assert self.generator._map_type_to_go("integer") == "int32"
        assert self.generator._map_type_to_go("number") == "float64"
        assert self.generator._map_type_to_go("boolean") == "bool"
        assert self.generator._map_type_to_go("array") == "[]string"
        assert self.generator._map_type_to_go("object") == "map[string]interface{}"
        assert self.generator._map_type_to_go("unknown") == "string"  # default

    def test_generate_kubernetes_controller_creates_directories(self):
        """Test that controller generation creates proper directory structure"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self.sample_request.output_dir = temp_dir

            self.generator.generate_kubernetes_controller(self.sample_request)

            output_path = Path(temp_dir)
            assert output_path.exists()
            assert (output_path / "api").exists()
            assert (output_path / "api" / "v1alpha1").exists()
            assert (output_path / "internal").exists()
            assert (output_path / "internal" / "controller").exists()

    def test_generate_result_object(self):
        """Test GenerationResult object creation"""
        result = GenerationResult(
            success=True,
            output_path="/tmp/test",
            command=["echo", "test"],
            stdout="success",
            stderr="",
            generated_files=["/tmp/test/main.go"]
        )

        assert result.success is True
        assert result.output_path == "/tmp/test"
        assert result.command == ["echo", "test"]
        assert result.stdout == "success"
        assert len(result.generated_files) == 1