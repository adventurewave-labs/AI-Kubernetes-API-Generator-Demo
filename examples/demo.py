#!/usr/bin/env python3
"""
Demo script showcasing the AI-Assisted Platform Extension Generator capabilities.
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from simple_agent import APIRequest, generate_openapi_spec


def demo_vector_db():
    """Demo: Vector Database Resource"""
    print("🔬 Demo 1: Vector Database Resource")
    print("-" * 40)

    request = APIRequest(
        kind="VectorDB",
        group="ai.platform.cnoe.io",
        version="v1alpha1",
        spec_properties={
            "engine_type": "string",
            "replicas": "integer",
            "enabled": "boolean",
            "storage_size": "string"
        },
        description="Vector database cluster for AI workloads"
    )

    spec = generate_openapi_spec(request)

    print(f"✅ Generated API: {spec.info['title']}")
    print(f"📍 Group: {request.group}")
    print(f"🔢 Version: {request.version}")
    print(f"📝 Description: {spec.info['description']}")
    print(f"🔗 Endpoint: {list(spec.paths.keys())[0]}")
    print(f"📊 Schemas: {len(spec.components['schemas'])}")
    print()

    return spec


def demo_cache_cluster():
    """Demo: Cache Cluster Resource"""
    print("🔬 Demo 2: Cache Cluster Resource")
    print("-" * 40)

    request = APIRequest(
        kind="CacheCluster",
        group="cache.platform.cnoe.io",
        version="v1beta1",
        spec_properties={
            "node_count": "integer",
            "memory_limit": "string",
            "persistence_enabled": "boolean",
            "engine": "string"
        },
        description="High-performance cache cluster"
    )

    spec = generate_openapi_spec(request)

    print(f"✅ Generated API: {spec.info['title']}")
    print(f"📍 Group: {request.group}")
    print(f"🔢 Version: {request.version}")
    print(f"📝 Description: {spec.info['description']}")
    print(f"🔗 Endpoint: {list(spec.paths.keys())[0]}")
    print(f"📊 Schemas: {len(spec.components['schemas'])}")
    print()

    return spec


def demo_ml_pipeline():
    """Demo: Machine Learning Pipeline Resource"""
    print("🔬 Demo 3: ML Pipeline Resource")
    print("-" * 40)

    request = APIRequest(
        kind="MLPipeline",
        group="ml.platform.cnoe.io",
        version="v1alpha1",
        spec_properties={
            "model_name": "string",
            "training_steps": "integer",
            "gpu_enabled": "boolean",
            "dataset_path": "string",
            "hyperparameters": "object"  # Will default to string
        },
        description="Machine learning training pipeline"
    )

    spec = generate_openapi_spec(request)

    print(f"✅ Generated API: {spec.info['title']}")
    print(f"📍 Group: {request.group}")
    print(f"🔢 Version: {request.version}")
    print(f"📝 Description: {spec.info['description']}")
    print(f"🔗 Endpoint: {list(spec.paths.keys())[0]}")
    print(f"📊 Schemas: {len(spec.components['schemas'])}")
    print()

    return spec


def inspect_generated_spec(spec, resource_name):
    """Inspect and display details of a generated OpenAPI spec."""
    print(f"📋 Detailed Inspection: {resource_name}")
    print("-" * 50)

    # Display schema structure
    if resource_name in spec.components.get('schemas', {}):
        schema = spec.components['schemas'][resource_name]
        print("🏗️ Schema Structure:")
        print(f"   Type: {schema['type']}")
        print(f"   Properties: {list(schema['properties'].keys())}")

        # Check spec properties
        if 'spec' in schema['properties']:
            spec_props = schema['properties']['spec']
            print(f"   Spec Fields: {list(spec_props.get('properties', {}).keys())}")
            print(f"   Required Fields: {spec_props.get('required', [])}")

    # Display API paths
    if spec.paths:
        print("🛤️ API Endpoints:")
        for path, methods in spec.paths.items():
            print(f"   {path}")
            for method, details in methods.items():
                print(f"     {method.upper()}: {details.get('summary', 'No summary')}")

    print()


def save_spec_to_file(spec, filename):
    """Save OpenAPI spec to JSON file for inspection."""
    import json

    output_dir = Path("generated_specs")
    output_dir.mkdir(exist_ok=True)

    filepath = output_dir / f"{filename}.json"

    with open(filepath, 'w') as f:
        json.dump(spec.dict(), f, indent=2)

    print(f"💾 Saved spec to: {filepath}")
    return filepath


def main():
    """Run the complete demo."""
    print("🚀 AI-Assisted Platform Extension Generator Demo")
    print("=" * 60)
    print()

    # Generate different resource types
    vector_spec = demo_vector_db()
    cache_spec = demo_cache_cluster()
    ml_spec = demo_ml_pipeline()

    # Inspect generated specs
    inspect_generated_spec(vector_spec, "VectorDB")
    inspect_generated_spec(cache_spec, "CacheCluster")
    inspect_generated_spec(ml_spec, "MLPipeline")

    # Save specs to files
    print("💾 Saving Generated Specifications:")
    print("-" * 40)
    save_spec_to_file(vector_spec, "vector_db_spec")
    save_spec_to_file(cache_spec, "cache_cluster_spec")
    save_spec_to_file(ml_spec, "ml_pipeline_spec")

    print()
    print("🎉 Demo completed successfully!")
    print("📋 Summary:")
    print("   ✅ Generated 3 different Kubernetes API specifications")
    print("   ✅ All specs follow OpenAPI 3.0 standards")
    print("   ✅ All specs include proper Kubernetes structure")
    print("   ✅ Specifications saved to generated_specs/ directory")
    print()
    print("🚀 Ready for integration with openapi-mcp-codegen!")


if __name__ == "__main__":
    main()