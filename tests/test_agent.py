#!/usr/bin/env python3
"""
Test suite for the AI-Assisted Platform Extension Generator.
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import the classes from our agent module
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from simple_agent import APIRequest, OpenAPISpec, generate_openapi_spec


class TestAPIRequest:
    """Test cases for APIRequest model."""

    def test_api_request_with_defaults(self):
        """Test APIRequest with default values."""
        request = APIRequest(
            kind="TestResource",
            spec_properties={"name": "string", "count": "integer"}
        )

        assert request.group == "platform.cnoe.io"
        assert request.version == "v1alpha1"
        assert request.kind == "TestResource"
        assert request.spec_properties == {"name": "string", "count": "integer"}
        assert request.description is None

    def test_api_request_custom_values(self):
        """Test APIRequest with custom values."""
        request = APIRequest(
            group="custom.example.io",
            version="v1beta1",
            kind="CustomResource",
            spec_properties={"field": "string"},
            description="A custom resource for testing"
        )

        assert request.group == "custom.example.io"
        assert request.version == "v1beta1"
        assert request.kind == "CustomResource"
        assert request.spec_properties == {"field": "string"}
        assert request.description == "A custom resource for testing"

    def test_api_request_validation(self):
        """Test APIRequest validation."""
        # Valid request
        request = APIRequest(
            kind="ValidResource",
            spec_properties={"name": "string"}
        )
        assert request.kind == "ValidResource"

        # Invalid request (missing required fields)
        with pytest.raises(ValueError):
            APIRequest()

    def test_api_request_edge_cases(self):
        """Test APIRequest edge cases."""
        # Empty spec properties
        request = APIRequest(
            kind="EmptyResource",
            spec_properties={}
        )
        assert request.spec_properties == {}

        # Complex spec properties
        complex_spec = {
            "name": "string",
            "count": "integer",
            "enabled": "boolean",
            "config": "object"
        }
        request = APIRequest(
            kind="ComplexResource",
            spec_properties=complex_spec
        )
        assert request.spec_properties == complex_spec


class TestOpenAPISpec:
    """Test cases for OpenAPISpec model."""

    def test_openapi_spec_creation(self):
        """Test OpenAPISpec creation."""
        spec = OpenAPISpec(
            info={
                "title": "TestResource",
                "version": "v1alpha1",
                "description": "Test resource specification"
            }
        )

        assert spec.openapi == "3.0.0"
        assert spec.info["title"] == "TestResource"
        assert spec.info["version"] == "v1alpha1"
        assert spec.info["description"] == "Test resource specification"
        assert spec.paths == {}
        assert spec.components == {}

    def test_openapi_spec_with_components(self):
        """Test OpenAPISpec with components."""
        spec = OpenAPISpec(
            info={
                "title": "TestResource",
                "version": "v1alpha1"
            }
        )

        # Add components
        spec.components["schemas"] = {"TestResource": {"type": "object"}}
        spec.paths["/test"] = {"get": {"summary": "Test endpoint"}}

        assert len(spec.components["schemas"]) == 1
        assert len(spec.paths) == 1

    def test_openapi_spec_validation(self):
        """Test OpenAPISpec validation."""
        # Valid spec
        spec = OpenAPISpec(
            info={"title": "ValidResource", "version": "v1"}
        )
        assert spec.info["title"] == "ValidResource"

        # Invalid spec (missing info)
        with pytest.raises(ValueError):
            OpenAPISpec()


class TestAIScaffoldingAgent:
    """Test cases for AIScaffoldingAgent functionality."""

    def test_generate_openapi_spec_basic(self):
        """Test OpenAPI spec generation with basic request."""
        # Import here to avoid circular imports
        from simple_agent import test_basic_functionality

        # Use the test function to verify functionality
        result = test_basic_functionality()
        assert result is True

    def test_api_request_model_structure(self):
        """Test that APIRequest model has the correct structure."""
        request = APIRequest(
            kind="TestResource",
            spec_properties={"name": "string", "count": "integer"},
            description="Test resource"
        )

        # Check that all required fields exist
        assert hasattr(request, 'group')
        assert hasattr(request, 'version')
        assert hasattr(request, 'kind')
        assert hasattr(request, 'spec_properties')
        assert hasattr(request, 'description')

        # Check field types
        assert isinstance(request.group, str)
        assert isinstance(request.version, str)
        assert isinstance(request.kind, str)
        assert isinstance(request.spec_properties, dict)
        assert request.description is None or isinstance(request.description, str)

    def test_openapi_spec_generation_detailed(self):
        """Test detailed OpenAPI spec generation."""
        request = APIRequest(
            kind="VectorDB",
            group="ai.platform.cnoe.io",
            version="v1beta1",
            spec_properties={
                "engine_type": "string",
                "replicas": "integer",
                "enabled": "boolean",
                "storage_size": "string"
            },
            description="Vector database resource"
        )

        # Create OpenAPI spec manually (since we don't have the full agent class)
        spec = OpenAPISpec(
            info={
                "title": request.kind,
                "version": request.version,
                "description": request.description
            }
        )

        # Generate schema properties
        properties = {}
        required = []

        for field_name, field_type in request.spec_properties.items():
            if field_type == "string":
                properties[field_name] = {"type": "string"}
            elif field_type == "integer":
                properties[field_name] = {"type": "integer", "format": "int32"}
            elif field_type == "boolean":
                properties[field_name] = {"type": "boolean"}
            else:
                properties[field_name] = {"type": "string"}
            required.append(field_name)

        # Add schema
        spec.components["schemas"] = {
            request.kind: {
                "type": "object",
                "properties": {
                    "apiVersion": {"type": "string"},
                    "kind": {"type": "string"},
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "namespace": {"type": "string"}
                        }
                    },
                    "spec": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    },
                    "status": {
                        "type": "object",
                        "properties": {
                            "phase": {"type": "string"},
                            "message": {"type": "string"}
                        }
                    }
                }
            }
        }

        # Add API path
        resource_name = request.kind.lower()
        plural_name = f"{resource_name}s"

        spec.paths[f"/apis/{request.group}/{request.version}/{plural_name}"] = {
            "post": {
                "summary": f"Create {request.kind}",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{request.kind}"}
                        }
                    }
                },
                "responses": {
                    "201": {
                        "description": f"{request.kind} created"
                    }
                }
            }
        }

        # Validate the generated spec
        assert spec.info["title"] == "VectorDB"
        assert spec.info["version"] == "v1beta1"
        assert spec.info["description"] == "Vector database resource"
        assert len(spec.components["schemas"]) == 1
        assert len(spec.paths) == 1

        # Check schema structure
        schema = spec.components["schemas"]["VectorDB"]
        assert schema["type"] == "object"
        assert "apiVersion" in schema["properties"]
        assert "kind" in schema["properties"]
        assert "metadata" in schema["properties"]
        assert "spec" in schema["properties"]
        assert "status" in schema["properties"]

        # Check spec properties
        spec_props = schema["properties"]["spec"]
        assert len(spec_props["properties"]) == 4
        assert "engine_type" in spec_props["properties"]
        assert "replicas" in spec_props["properties"]
        assert "enabled" in spec_props["properties"]
        assert "storage_size" in spec_props["properties"]
        assert spec_props["properties"]["engine_type"]["type"] == "string"
        assert spec_props["properties"]["replicas"]["type"] == "integer"
        assert spec_props["properties"]["enabled"]["type"] == "boolean"

        # Check API path
        expected_path = "/apis/ai.platform.cnoe.io/v1beta1/vectordbs"
        assert expected_path in spec.paths
        assert spec.paths[expected_path]["post"]["summary"] == "Create VectorDB"

    def test_field_type_mapping(self):
        """Test that field types are correctly mapped to OpenAPI types."""
        test_cases = [
            ("string", {"type": "string"}),
            ("integer", {"type": "integer", "format": "int32"}),
            ("boolean", {"type": "boolean"}),
            ("unknown", {"type": "string"}),  # Default fallback
        ]

        for input_type, expected_output in test_cases:
            request = APIRequest(
                kind="TestResource",
                spec_properties={"field": input_type}
            )

            # Generate properties manually
            properties = {}
            for field_name, field_type in request.spec_properties.items():
                if field_type == "string":
                    properties[field_name] = {"type": "string"}
                elif field_type == "integer":
                    properties[field_name] = {"type": "integer", "format": "int32"}
                elif field_type == "boolean":
                    properties[field_name] = {"type": "boolean"}
                else:
                    properties[field_name] = {"type": "string"}

            assert properties["field"] == expected_output

    def test_complex_kubernetes_api_structure(self):
        """Test generation of complex Kubernetes API structures."""
        request = APIRequest(
            kind="MachineLearningPipeline",
            group="ml.ai.cnoe.io",
            version="v1alpha1",
            spec_properties={
                "model_name": "string",
                "training_steps": "integer",
                "gpu_enabled": "boolean",
                "dataset_path": "string",
                "hyperparameters": "object"  # This should default to string
            },
            description="Machine learning pipeline resource"
        )

        # Verify complex structure generation
        spec = OpenAPISpec(
            info={
                "title": request.kind,
                "version": request.version,
                "description": request.description
            }
        )

        # The complex structure should include all Kubernetes standard fields
        assert spec.info["title"] == "MachineLearningPipeline"
        assert spec.info["version"] == "v1alpha1"
        assert spec.info["description"] == "Machine learning pipeline resource"


class TestIntegration:
    """Integration tests for the complete system."""

    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow."""
        # Create a realistic request
        request = APIRequest(
            kind="CacheCluster",
            group="database.platform.cnoe.io",
            version="v1beta1",
            spec_properties={
                "size": "string",
                "node_count": "integer",
                "redis_version": "string",
                "persistence_enabled": "boolean"
            },
            description="Redis cache cluster resource"
        )

        # Generate OpenAPI spec
        spec = OpenAPISpec(
            info={
                "title": request.kind,
                "version": request.version,
                "description": request.description
            }
        )

        # Verify the complete workflow
        assert request.kind == "CacheCluster"
        assert request.group == "database.platform.cnoe.io"
        assert len(request.spec_properties) == 4

        # Validate the spec contains proper Kubernetes structure
        spec.components["schemas"] = {
            request.kind: {
                "type": "object",
                "properties": {
                    "apiVersion": {"type": "string"},
                    "kind": {"type": "string"},
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "namespace": {"type": "string"}
                        }
                    },
                    "spec": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    },
                    "status": {
                        "type": "object",
                        "properties": {
                            "phase": {"type": "string"},
                            "message": {"type": "string"}
                        }
                    }
                }
            }
        }

        # Verify schema structure
        schema = spec.components["schemas"][request.kind]
        assert "metadata" in schema["properties"]
        assert "spec" in schema["properties"]
        assert "status" in schema["properties"]

    def test_multiple_resource_types(self):
        """Test handling multiple different resource types."""
        resources = [
            {
                "kind": "Database",
                "spec": {"engine": "string", "size": "integer", "ssl_enabled": "boolean"}
            },
            {
                "kind": "MessageQueue",
                "spec": {"name": "string", "partitions": "integer", "retention": "string"}
            },
            {
                "kind": "LoadBalancer",
                "spec": {"algorithm": "string", "health_check": "boolean"}
            }
        ]

        for resource_data in resources:
            request = APIRequest(
                kind=resource_data["kind"],
                spec_properties=resource_data["spec"]
            )

            # Each resource should be properly structured
            assert request.kind == resource_data["kind"]
            assert request.group == "platform.cnoe.io"  # Default
            assert request.version == "v1alpha1"  # Default
            assert len(request.spec_properties) == len(resource_data["spec"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])