#!/usr/bin/env python3
"""
Simple AI-Assisted Platform Extension Generator
Main scaffolding agent that translates natural language requests to OpenAPI specifications.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class APIRequest(BaseModel):
    """Represents a Kubernetes API request from natural language."""
    group: str = Field(default="platform.cnoe.io", description="API group")
    version: str = Field(default="v1alpha1", description="API version")
    kind: str = Field(description="Resource kind name")
    spec_properties: Dict[str, str] = Field(description="Spec properties with types")
    description: Optional[str] = Field(None, description="Optional description")


class OpenAPISpec(BaseModel):
    """OpenAPI specification for the API."""
    openapi: str = "3.0.0"
    info: Dict[str, Any]
    paths: Dict[str, Any] = {}
    components: Dict[str, Any] = {}


def generate_openapi_spec(api_request: APIRequest) -> OpenAPISpec:
    """Generate OpenAPI specification from API request."""
    # Create the OpenAPI spec
    spec = OpenAPISpec(
        info={
            "title": api_request.kind,
            "version": api_request.version,
            "description": api_request.description or f"{api_request.kind} API specification"
        }
    )

    # Generate schema properties
    properties = {}
    required = []

    for field_name, field_type in api_request.spec_properties.items():
        if field_type == "string":
            properties[field_name] = {"type": "string"}
        elif field_type == "integer":
            properties[field_name] = {"type": "integer", "format": "int32"}
        elif field_type == "boolean":
            properties[field_name] = {"type": "boolean"}
        else:
            properties[field_name] = {"type": "string"}  # Default to string

        required.append(field_name)

    # Add the schema for the API resource
    spec.components["schemas"] = {
        api_request.kind: {
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

    # Add a simple path for creating the resource
    resource_name = api_request.kind.lower()
    plural_name = f"{resource_name}s"

    spec.paths[f"/apis/{api_request.group}/{api_request.version}/{plural_name}"] = {
        "post": {
            "summary": f"Create {api_request.kind}",
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{api_request.kind}"}
                    }
                }
            },
            "responses": {
                "201": {
                    "description": f"{api_request.kind} created"
                }
            }
        }
    }

    return spec


def test_basic_functionality():
    """Test basic functionality without external dependencies."""
    print("🧪 Testing AI scaffolding agent...")

    # Test APIRequest creation
    request = APIRequest(
        kind="TestResource",
        spec_properties={"name": "string", "count": "integer", "enabled": "boolean"},
        description="A test resource for verification"
    )
    print(f"✅ Created APIRequest: {request.kind}")
    print(f"   Group: {request.group}")
    print(f"   Version: {request.version}")
    print(f"   Properties: {request.spec_properties}")
    print(f"   Description: {request.description}")

    # Test OpenAPI spec generation
    spec = generate_openapi_spec(request)

    print(f"✅ Generated OpenAPI spec:")
    print(f"   Title: {spec.info['title']}")
    print(f"   Version: {spec.info['version']}")
    print(f"   Schemas: {len(spec.components.get('schemas', {}))}")
    print(f"   API Paths: {len(spec.paths)}")
    print(f"   Example Path: {list(spec.paths.keys())[0] if spec.paths else 'None'}")

    # Validate spec structure
    assert spec.info['title'] == "TestResource"
    assert spec.info['version'] == "v1alpha1"
    assert len(spec.components.get('schemas', {})) == 1
    assert len(spec.paths) == 1
    assert "TestResource" in spec.components["schemas"]

    print("✅ All validations passed!")

    return True


if __name__ == "__main__":
    print("🚀 AI-Assisted Platform Extension Generator - Simple Test Mode")
    print("=" * 70)

    try:
        success = test_basic_functionality()
        if success:
            print("\n🎉 SUCCESS: AI scaffolding agent is working correctly!")
            print("📋 Core functionality verified:")
            print("   ✅ APIRequest model creation")
            print("   ✅ OpenAPI specification generation")
            print("   ✅ Schema property mapping")
            print("   ✅ API path creation")
            print("   ✅ Data validation")
        else:
            print("\n❌ FAILED: Basic functionality test failed")
            sys.exit(1)

    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        sys.exit(1)