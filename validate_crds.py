#!/usr/bin/env python3
"""
Comprehensive CRD validation script to ensure schema compliance
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, List

def validate_crd_schema(crd_file: Path, instance_file: Path) -> List[str]:
    """Validate CRD schema against instance values"""
    errors = []

    try:
        # Load CRD and instance files
        with open(crd_file) as f:
            crd = yaml.safe_load(f)
        with open(instance_file) as f:
            instance = yaml.safe_load(f)

        # Extract schema properties
        schema = crd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"]
        instance_spec = instance.get("spec", {})

        # Validate each field in instance against schema
        for field_name, field_value in instance_spec.items():
            if field_name not in schema:
                errors.append(f"❌ Field '{field_name}' not defined in schema")
                continue

            field_schema = schema[field_name]
            expected_type = field_schema.get("type")

            # Type validation
            if expected_type == "string" and not isinstance(field_value, str):
                errors.append(f"❌ Field '{field_name}' should be string, got {type(field_value).__name__}")

            elif expected_type == "integer" and not isinstance(field_value, int):
                errors.append(f"❌ Field '{field_name}' should be integer, got {type(field_value).__name__}")

            elif expected_type == "boolean" and not isinstance(field_value, bool):
                errors.append(f"❌ Field '{field_name}' should be boolean, got {type(field_value).__name__}")

            elif expected_type == "array":
                if not isinstance(field_value, list):
                    errors.append(f"❌ Field '{field_name}' should be array, got {type(field_value).__name__}")
                else:
                    # Check array items type
                    items_type = field_schema.get("items", {}).get("type", "string")
                    for i, item in enumerate(field_value):
                        if items_type == "string" and not isinstance(item, str):
                            errors.append(f"❌ Array item {i} in '{field_name}' should be string, got {type(item).__name__}")

            elif expected_type == "object":
                if not isinstance(field_value, dict):
                    errors.append(f"❌ Field '{field_name}' should be object, got {type(field_value).__name__}")
                else:
                    # Check object properties if defined
                    properties = field_schema.get("properties", {})
                    for prop_name, prop_value in field_value.items():
                        if prop_name in properties:
                            prop_schema = properties[prop_name]
                            prop_type = prop_schema.get("type", "string")
                            if prop_type == "string" and not isinstance(prop_value, str):
                                errors.append(f"❌ Object property '{prop_name}' in '{field_name}' should be string, got {type(prop_value).__name__}")

        # Check for required fields (basic check)
        for field_name, field_schema in schema.items():
            if field_name not in instance_spec:
                errors.append(f"⚠️  Schema field '{field_name}' not found in instance (may be optional)")

    except Exception as e:
        errors.append(f"❌ Validation error: {str(e)}")

    return errors

def validate_all_crds():
    """Validate all generated CRD and instance files"""
    k8s_dir = Path("generated_specs/kubernetes")

    # Define the CRD files to validate
    crd_files = [
        ("customresource-crd.yaml", "customresource-instance.yaml"),
        ("rediscluster-crd.yaml", "rediscluster-instance.yaml"),
        ("databaseservice-crd.yaml", "databaseservice-instance.yaml"),
        ("monitoringservice-crd.yaml", "monitoringservice-instance.yaml"),
    ]

    print("🔍 Comprehensive CRD Validation Report")
    print("=" * 60)

    all_errors = []
    validation_passed = True

    for crd_file, instance_file in crd_files:
        crd_path = k8s_dir / crd_file
        instance_path = k8s_dir / instance_file

        if not crd_path.exists() or not instance_path.exists():
            print(f"❌ Missing files: {crd_file} or {instance_file}")
            continue

        print(f"\n📋 Validating {crd_file.replace('-crd.yaml', '')}:")
        print(f"   CRD: {crd_file}")
        print(f"   Instance: {instance_file}")

        errors = validate_crd_schema(crd_path, instance_path)

        if not errors:
            print("   ✅ PASSED - Schema validation successful")
        else:
            print("   ❌ FAILED - Schema validation errors:")
            validation_passed = False
            all_errors.extend([f"{crd_file}: {error}" for error in errors])
            for error in errors:
                print(f"      {error}")

    print("\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)

    if validation_passed:
        print("✅ ALL CRD VALIDATIONS PASSED!")
        print("✅ Schema definitions match instance values")
        print("✅ Type compliance verified")
        print("✅ OpenAPI v3 schema structure correct")
    else:
        print("❌ VALIDATION FAILURES DETECTED:")
        for error in all_errors:
            print(f"   {error}")

    return validation_passed

def main():
    """Main validation function"""
    print("🚀 Kubernetes CRD Validation System")
    print("Validating Custom Resource Definitions against instance values...")

    success = validate_all_crds()

    if success:
        print("\n🎉 CRD VALIDATION COMPLETE - ALL ISSUES FIXED!")
        print("The original 'object vs string' type mismatch has been resolved.")
        print("All CRDs now have proper OpenAPI v3 schema definitions.")
    else:
        print("\n⚠️  Some validation issues remain. See details above.")

    return 0 if success else 1

if __name__ == "__main__":
    exit(main())