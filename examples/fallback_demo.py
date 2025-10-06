#!/usr/bin/env python3
"""
Fallback Demo - Shows what the AI system would do with a working API key
This demonstrates the full workflow without requiring API calls.
"""

import json
import os
from pathlib import Path

def demo_fallback_functionality():
    """Demo the full functionality without requiring API keys."""
    print("🚀 AI Platform Extension Generator - Fallback Demo")
    print("=" * 60)
    print("🔧 This demo shows the complete workflow without API calls")
    print()

    # Mock AI response for PostgreSQL cluster API
    mock_parsed_request = {
        "group": "database.platform.cnoe.io",
        "version": "v1alpha1",
        "kind": "PostgreSQLCluster",
        "spec_properties": {
            "database_version": "string",
            "replicas": "integer",
            "storage_size": "string",
            "backup_enabled": "boolean",
            "connection_limit": "integer"
        }
    }

    print("📝 Input: I want to create a Kubernetes API for managing PostgreSQL database clusters. The API should support setting the database version, number of replicas, storage size, backup enabled flag, and connection limits.")
    print()

    print("✅ AI successfully parsed your request!")
    print(f"🎯 Detected API: {mock_parsed_request['kind']}")
    print(f"📍 Group: {mock_parsed_request['group']}")
    print(f"🔢 Version: {mock_parsed_request['version']}")

    print("📊 Detected fields:")
    for field, field_type in mock_parsed_request['spec_properties'].items():
        print(f"   • {field}: {field_type}")

    # Generate mock OpenAPI spec
    mock_spec = {
        "openapi": "3.0.0",
        "info": {
            "title": mock_parsed_request["kind"],
            "version": mock_parsed_request["version"],
            "description": "Kubernetes API for managing PostgreSQL database clusters"
        },
        "paths": {
            f"/apis/{mock_parsed_request['group']}/{mock_parsed_request['version']}/postgresqlclusters": {
                "post": {
                    "summary": f"Create {mock_parsed_request['kind']}",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/PostgreSQLCluster"
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": f"{mock_parsed_request['kind']} created"
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "PostgreSQLCluster": {
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
                            "properties": {
                                "database_version": {"type": "string"},
                                "replicas": {"type": "integer", "format": "int32"},
                                "storage_size": {"type": "string"},
                                "backup_enabled": {"type": "boolean"},
                                "connection_limit": {"type": "integer", "format": "int32"}
                            },
                            "required": [
                                "database_version",
                                "replicas",
                                "storage_size",
                                "backup_enabled",
                                "connection_limit"
                            ]
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
        }
    }

    print(f"\n🏗️  Generated OpenAPI specification...")
    print("✅ Successfully generated OpenAPI specification!")

    print(f"\n📋 Generated API Details:")
    print(f"   Title: {mock_spec['info']['title']}")
    print(f"   Version: {mock_spec['info']['version']}")
    print(f"   Description: {mock_spec['info']['description']}")

    print(f"   Endpoints: {len(mock_spec['paths'])}")
    for path in mock_spec['paths']:
        print(f"     • {path}")

    print(f"   Schemas: {len(mock_spec['components']['schemas'])}")
    for schema_name in mock_spec['components']['schemas']:
        print(f"     • {schema_name}")

    # Save the spec to a file
    output_dir = Path("generated_specs")
    output_dir.mkdir(exist_ok=True)
    spec_file = output_dir / "postgresql_cluster_fallback.json"

    with open(spec_file, 'w') as f:
        json.dump(mock_spec, f, indent=2)

    print(f"   💾 Saved to: {spec_file}")

    print("\n🎉 What you just saw:")
    print("   • Natural language input → Structured API definition")
    print("   • Automatic OpenAPI 3.0 specification generation")
    print("   • Kubernetes-compatible schema structure")
    print("   • Ready for use with openapi-mcp-codegen")
    print("   • Complete with validation rules and data types")

    print(f"\n🔧 Next steps when API key is working:")
    print(f"   1. Fix your OpenRouter account status")
    print(f"   2. Use the generated spec with: openapi-mcp-codegen generate {spec_file}")
    print(f"   3. Deploy to your Kubernetes cluster")

    return True

if __name__ == "__main__":
    demo_fallback_functionality()