#!/usr/bin/env python3
"""
Tests for the AI Scaffolding Agent

These tests follow TDD principles and verify the agent's functionality
without using mocks for external systems.
"""

import pytest
import json
import yaml
import tempfile
import shutil
import os
import subprocess
from pathlib import Path
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai_scaffolding_agent import (
    AIScaffoldingAgent,
    OpenAPIGenerator,
    ConfigGenerator,
    APIInfo,
    APISchema,
    APIEndpoint
)


class TestAPIInfo:
    """Test APIInfo dataclass"""

    def test_api_info_creation(self):
        """Test creating APIInfo with valid data"""
        info = APIInfo(
            title="Test API",
            description="A test API",
            version="1.0.0",
            base_url="/api/v1"
        )
        assert info.title == "Test API"
        assert info.description == "A test API"
        assert info.version == "1.0.0"
        assert info.base_url == "/api/v1"


class TestAPISchema:
    """Test APISchema dataclass"""

    def test_schema_creation(self):
        """Test creating APISchema with valid data"""
        schema = APISchema(
            name="TestSchema",
            properties={
                "id": {"type": "integer"},
                "name": {"type": "string"}
            },
            required=["name"],
            description="A test schema"
        )
        assert schema.name == "TestSchema"
        assert len(schema.properties) == 2
        assert "name" in schema.required
        assert schema.description == "A test schema"


class TestAPIEndpoint:
    """Test APIEndpoint dataclass"""

    def test_endpoint_creation(self):
        """Test creating APIEndpoint with valid data"""
        endpoint = APIEndpoint(
            path="/test",
            method="get",
            operation_id="getTest",
            summary="Get test resource",
            description="Returns a test resource",
            parameters=[],
            request_body=None,
            responses={"200": {"description": "Success"}}
        )
        assert endpoint.path == "/test"
        assert endpoint.method == "get"
        assert endpoint.operation_id == "getTest"


class TestOpenAPIGenerator:
    """Test OpenAPIGenerator class"""

    def test_create_basic_openapi_spec(self):
        """Test creating a basic OpenAPI specification"""
        generator = OpenAPIGenerator()
        info = APIInfo(
            title="Test API",
            description="A test API",
            version="1.0.0",
            base_url="/api/v1"
        )

        spec = generator.create_basic_openapi_spec(info)

        assert spec["openapi"] == "3.0.4"
        assert spec["info"]["title"] == "Test API"
        assert spec["info"]["description"] == "A test API"
        assert spec["info"]["version"] == "1.0.0"
        assert len(spec["servers"]) == 1
        assert spec["servers"][0]["url"] == "/api/v1"
        assert "paths" in spec
        assert "components" in spec
        assert "schemas" in spec["components"]

    def test_add_schema(self):
        """Test adding schemas to the generator"""
        generator = OpenAPIGenerator()
        generator.api_info = APIInfo(
            title="Test API",
            description="A test API",
            version="1.0.0",
            base_url="/api/v1"
        )

        schema = APISchema(
            name="TestSchema",
            properties={"name": {"type": "string"}},
            required=["name"],
            description="Test schema"
        )

        generator.add_schema(schema)
        assert len(generator.schemas) == 1
        assert generator.schemas[0].name == "TestSchema"

    def test_add_endpoint(self):
        """Test adding endpoints to the generator"""
        generator = OpenAPIGenerator()
        generator.api_info = APIInfo(
            title="Test API",
            description="A test API",
            version="1.0.0",
            base_url="/api/v1"
        )

        endpoint = APIEndpoint(
            path="/test",
            method="get",
            operation_id="getTest",
            summary="Get test resource",
            description="Returns a test resource",
            parameters=[],
            request_body=None,
            responses={"200": {"description": "Success"}}
        )

        generator.add_endpoint(endpoint)
        assert len(generator.endpoints) == 1
        assert generator.endpoints[0].path == "/test"

    def test_generate_spec_with_schemas_and_endpoints(self):
        """Test generating a complete OpenAPI spec with schemas and endpoints"""
        generator = OpenAPIGenerator()
        generator.api_info = APIInfo(
            title="Test API",
            description="A test API",
            version="1.0.0",
            base_url="/api/v1"
        )

        # Add schema
        schema = APISchema(
            name="TestSchema",
            properties={
                "id": {"type": "integer"},
                "name": {"type": "string"}
            },
            required=["name"],
            description="Test schema"
        )
        generator.add_schema(schema)

        # Add endpoint
        endpoint = APIEndpoint(
            path="/test",
            method="get",
            operation_id="getTest",
            summary="Get test resource",
            description="Returns a test resource",
            parameters=[],
            request_body=None,
            responses={
                "200": {
                    "description": "Success",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TestSchema"}
                        }
                    }
                }
            }
        )
        generator.add_endpoint(endpoint)

        spec = generator.generate_spec()

        # Check that schema is included
        assert "TestSchema" in spec["components"]["schemas"]
        assert spec["components"]["schemas"]["TestSchema"]["properties"]["name"]["type"] == "string"

        # Check that endpoint is included
        assert "/test" in spec["paths"]
        assert "get" in spec["paths"]["/test"]
        assert spec["paths"]["/test"]["get"]["operationId"] == "getTest"

    def test_generate_spec_without_api_info_raises_error(self):
        """Test that generating spec without API info raises ValueError"""
        generator = OpenAPIGenerator()

        with pytest.raises(ValueError, match="API info must be set before generating spec"):
            generator.generate_spec()


class TestConfigGenerator:
    """Test ConfigGenerator class"""

    def test_create_config(self):
        """Test creating a basic configuration"""
        generator = ConfigGenerator()
        config = generator.create_config(
            title="Test API",
            description="A test API",
            author="Test Author"
        )

        assert config["title"] == "test_api"
        assert config["description"] == "A test API MCP Server"
        assert config["author"] == "Test Author"
        assert config["email"] == "agent@cnoe.io"
        assert config["version"] == "0.1.0"
        assert config["license"] == "Apache-2.0"
        assert "headers" in config
        assert "poetry_dependencies" in config
        assert "file_headers" in config

    def test_create_config_with_defaults(self):
        """Test creating config with default author"""
        generator = ConfigGenerator()
        config = generator.create_config(
            title="Test API",
            description="A test API"
        )

        assert config["author"] == "AI Agent"


class TestAIScaffoldingAgent:
    """Test AIScaffoldingAgent class"""

    def test_agent_initialization(self):
        """Test initializing the agent"""
        agent = AIScaffoldingAgent()
        assert agent.openapi_codegen_path == "python -m openapi_mcp_codegen"
        assert agent.temp_dir is None

    def test_agent_initialization_with_custom_path(self):
        """Test initializing the agent with custom codegen path"""
        custom_path = "/usr/local/bin/openapi_mcp_codegen"
        agent = AIScaffoldingAgent(openapi_codegen_path=custom_path)
        assert agent.openapi_codegen_path == custom_path

    def test_parse_petstore_request(self):
        """Test parsing a petstore request"""
        agent = AIScaffoldingAgent()
        request = "I want to create a pet store API"

        parsed = agent.parse_natural_language_request(request)

        assert "info" in parsed
        assert parsed["info"].title == "Pet Store API"
        assert "schemas" in parsed
        assert "endpoints" in parsed

        # Check for expected schemas
        schema_names = [schema.name for schema in parsed["schemas"]]
        assert "Pet" in schema_names
        assert "Category" in schema_names
        assert "Tag" in schema_names

        # Check for expected endpoints
        assert len(parsed["endpoints"]) >= 3  # At least list, create, get by ID

    def test_parse_user_api_request(self):
        """Test parsing a user API request"""
        agent = AIScaffoldingAgent()
        request = "Create a user management API"

        parsed = agent.parse_natural_language_request(request)

        assert "info" in parsed
        assert parsed["info"].title == "User Management API"
        assert "schemas" in parsed
        assert "endpoints" in parsed

        # Check for User schema
        schema_names = [schema.name for schema in parsed["schemas"]]
        assert "User" in schema_names

        # Check for expected endpoints
        assert len(parsed["endpoints"]) >= 2  # At least list and create

    def test_parse_blog_api_request(self):
        """Test parsing a blog API request"""
        agent = AIScaffoldingAgent()
        request = "Build a blog API"

        parsed = agent.parse_natural_language_request(request)

        assert "info" in parsed
        assert parsed["info"].title == "Blog API"
        assert "schemas" in parsed
        assert "endpoints" in parsed

        # Check for Post schema
        schema_names = [schema.name for schema in parsed["schemas"]]
        assert "Post" in schema_names

    def test_parse_generic_api_request(self):
        """Test parsing a generic API request"""
        agent = AIScaffoldingAgent()
        request = "Create a product API"

        parsed = agent.parse_natural_language_request(request)

        assert "info" in parsed
        assert parsed["info"].title == "Product API"
        assert "schemas" in parsed
        assert "endpoints" in parsed

        # Check for Product schema
        schema_names = [schema.name for schema in parsed["schemas"]]
        assert "Product" in schema_names

    def test_generate_openapi_spec_from_parsed_request(self):
        """Test generating an OpenAPI spec from a parsed request"""
        agent = AIScaffoldingAgent()
        request = "I want a simple task API"

        parsed = agent.parse_natural_language_request(request)

        # Create OpenAPI generator and populate it
        openapi_gen = OpenAPIGenerator()
        openapi_gen.api_info = parsed["info"]

        for schema in parsed["schemas"]:
            openapi_gen.add_schema(schema)

        for endpoint in parsed["endpoints"]:
            openapi_gen.add_endpoint(endpoint)

        spec = openapi_gen.generate_spec()

        # Verify the spec structure
        assert "openapi" in spec
        assert "info" in spec
        assert "paths" in spec
        assert "components" in spec
        assert "schemas" in spec["components"]

        # Verify the content
        assert spec["info"]["title"] == "Simple API"
        assert len(spec["components"]["schemas"]) > 0
        assert len(spec["paths"]) > 0

    def test_generate_temp_files(self):
        """Test that temporary files are generated correctly"""
        agent = AIScaffoldingAgent()
        request = "Create a simple test API"

        parsed = agent.parse_natural_language_request(request)

        # Create temporary directory manually for this test
        temp_dir = tempfile.mkdtemp(prefix="test_ai_scaffolding_")

        try:
            # Create OpenAPI specification
            openapi_gen = OpenAPIGenerator()
            openapi_gen.api_info = parsed["info"]

            for schema in parsed["schemas"]:
                openapi_gen.add_schema(schema)

            for endpoint in parsed["endpoints"]:
                openapi_gen.add_endpoint(endpoint)

            openapi_spec = openapi_gen.generate_spec()

            # Write files
            openapi_file = os.path.join(temp_dir, "openapi.json")
            with open(openapi_file, 'w') as f:
                json.dump(openapi_spec, f, indent=2)

            config_gen = ConfigGenerator()
            config = config_gen.create_config(
                title=parsed["info"].title,
                description=parsed["info"].description
            )

            config_file = os.path.join(temp_dir, "config.yaml")
            with open(config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)

            # Verify files exist and contain expected content
            assert os.path.exists(openapi_file)
            assert os.path.exists(config_file)

            # Verify OpenAPI file content
            with open(openapi_file, 'r') as f:
                loaded_spec = json.load(f)
                assert loaded_spec["info"]["title"] == "Simple API"

            # Verify config file content
            with open(config_file, 'r') as f:
                loaded_config = yaml.safe_load(f)
                assert loaded_config["title"] == "simple_api"

        finally:
            # Clean up
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    def test_validate_openapi_spec_structure(self):
        """Test that generated OpenAPI specs have valid structure"""
        agent = AIScaffoldingAgent()
        request = "Create a contact management API"

        parsed = agent.parse_natural_language_request(request)

        # Generate OpenAPI spec
        openapi_gen = OpenAPIGenerator()
        openapi_gen.api_info = parsed["info"]

        for schema in parsed["schemas"]:
            openapi_gen.add_schema(schema)

        for endpoint in parsed["endpoints"]:
            openapi_gen.add_endpoint(endpoint)

        spec = openapi_gen.generate_spec()

        # Validate required fields
        required_fields = ["openapi", "info", "paths"]
        for field in required_fields:
            assert field in spec, f"Missing required field: {field}"

        # Validate info object
        info_fields = ["title", "description", "version"]
        for field in info_fields:
            assert field in spec["info"], f"Missing info field: {field}"

        # Validate components
        if "components" in spec:
            assert "schemas" in spec["components"]

    def test_error_handling_missing_api_info(self):
        """Test error handling when API info is missing"""
        generator = OpenAPIGenerator()

        with pytest.raises(ValueError, match="API info must be set"):
            generator.generate_spec()

    def test_integration_parse_and_generate(self):
        """Integration test: parse request and generate complete spec"""
        agent = AIScaffoldingAgent()

        # Test various request types
        test_requests = [
            "I want a pet store API",
            "Create a user management system",
            "Build a blog platform API",
            "Make an inventory tracking API"
        ]

        for request in test_requests:
            # Parse the request
            parsed = agent.parse_natural_language_request(request)

            # Verify parsing worked
            assert "info" in parsed
            assert "schemas" in parsed
            assert "endpoints" in parsed

            # Generate OpenAPI spec
            openapi_gen = OpenAPIGenerator()
            openapi_gen.api_info = parsed["info"]

            for schema in parsed["schemas"]:
                openapi_gen.add_schema(schema)

            for endpoint in parsed["endpoints"]:
                openapi_gen.add_endpoint(endpoint)

            spec = openapi_gen.generate_spec()

            # Verify the generated spec
            assert "openapi" in spec
            assert spec["info"]["title"] != ""
            assert len(spec["components"]["schemas"]) > 0
            assert len(spec["paths"]) > 0


class TestFileOperations:
    """Test file operations and cleanup"""

    def test_temp_file_cleanup(self):
        """Test that temporary files are cleaned up properly"""
        agent = AIScaffoldingAgent()

        # Create a temporary directory manually
        temp_dir = tempfile.mkdtemp(prefix="test_cleanup_")

        # Create some test files
        test_file = os.path.join(temp_dir, "test.json")
        with open(test_file, 'w') as f:
            json.dump({"test": "data"}, f)

        # Verify files exist
        assert os.path.exists(temp_dir)
        assert os.path.exists(test_file)

        # Clean up
        shutil.rmtree(temp_dir)

        # Verify cleanup
        assert not os.path.exists(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])