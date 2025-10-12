#!/usr/bin/env python3
"""
CRD Validation Fix Script
This module provides a robust CRD generation function that handles array types correctly.
"""

import yaml
from typing import Dict, Any

def create_fixed_monitoring_service_crd():
    """Create a properly formatted MonitoringService CRD that passes validation"""

    crd_spec = {
        "apiVersion": "apiextensions.k8s.io/v1",
        "kind": "CustomResourceDefinition",
        "metadata": {
            "name": "monitoringservices.cnoe.io",
            "annotations": {
                "cert-manager.io/inject-ca-from": "cnoe-io/monitoringservice-serving-cert"
            }
        },
        "spec": {
            "group": "cnoe.io",
            "versions": [{
                "name": "v1alpha1",
                "served": True,
                "storage": True,
                "schema": {
                    "openAPIV3Schema": {
                        "type": "object",
                        "properties": {
                            "apiVersion": {
                                "type": "string"
                            },
                            "kind": {
                                "type": "string"
                            },
                            "metadata": {
                                "type": "object"
                            },
                            "spec": {
                                "type": "object",
                                "properties": {
                                    "interval": {
                                        "type": "string",
                                        "description": "Metrics collection interval"
                                    },
                                    "retention": {
                                        "type": "string",
                                        "description": "Data retention period"
                                    },
                                    "endpoints": {
                                        "type": "array",
                                        "description": "Monitoring endpoints",
                                        "items": {
                                            "type": "string",
                                            "description": "Endpoint URL"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }],
            "names": {
                "kind": "MonitoringService",
                "plural": "monitoringservices",
                "singular": "monitoringservice"
            },
            "scope": "Namespaced"
        }
    }

    return crd_spec

def generate_crd_yaml(request_dict: Dict[str, Any]) -> str:
    """
    Generate a properly formatted CRD YAML from a request dictionary.
    This function ensures all array types have proper items schema.
    """

    # Extract request details
    group = request_dict["group"]
    version = request_dict["version"]
    kind = request_dict["kind"]
    spec_properties = request_dict["spec_properties"]

    # Build CRD structure
    crd_dict = {
        "apiVersion": "apiextensions.k8s.io/v1",
        "kind": "CustomResourceDefinition",
        "metadata": {
            "name": f"{kind.lower()}s.{group}",
            "annotations": {
                "cert-manager.io/inject-ca-from": f"{group.split('.')[0]}/{kind.lower()}-serving-cert"
            }
        },
        "spec": {
            "group": group,
            "versions": [{
                "name": version,
                "served": True,
                "storage": True,
                "schema": {
                    "openAPIV3Schema": {
                        "type": "object",
                        "properties": {
                            "apiVersion": {
                                "type": "string"
                            },
                            "kind": {
                                "type": "string"
                            },
                            "metadata": {
                                "type": "object"
                            },
                            "spec": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    }
                }
            }],
            "names": {
                "kind": kind,
                "plural": f"{kind.lower()}s",
                "singular": kind.lower()
            },
            "scope": "Namespaced"
        }
    }

    # Add spec properties with proper array handling
    for field_name, field_info in spec_properties.items():
        field_type = field_info["type"]
        field_desc = field_info.get("description", f"Description for {field_name}")

        property_schema = {
            "type": field_type,
            "description": field_desc
        }

        # Critical fix: Always add items for array types
        if field_type == "array":
            property_schema["items"] = {
                "type": "string",
                "description": f"Array item for {field_name}"
            }

        crd_dict["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"][field_name] = property_schema

    # Convert to YAML
    return yaml.dump(crd_dict, default_flow_style=False, sort_keys=False)

if __name__ == "__main__":
    # Test the fixed MonitoringService CRD
    print("🔧 Creating fixed MonitoringService CRD...")

    monitoring_request = {
        "group": "monitoring.cnoe.io",
        "version": "v1alpha1",
        "kind": "MonitoringService",
        "spec_properties": {
            "interval": {"type": "string", "description": "Metrics collection interval"},
            "retention": {"type": "string", "description": "Data retention period"},
            "endpoints": {"type": "array", "description": "Monitoring endpoints"}
        }
    }

    crd_yaml = generate_crd_yaml(monitoring_request)

    # Save the fixed CRD
    with open("fixed_monitoringservice-crd.yaml", "w") as f:
        f.write(crd_yaml)

    print("✅ Fixed CRD saved to: fixed_monitoringservice-crd.yaml")

    # Test with kubectl
    import subprocess
    try:
        result = subprocess.run(
            ["kubectl", "apply", "--dry-run=client", "-f", "fixed_monitoringservice-crd.yaml"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✅ Fixed CRD passes kubectl validation")
        else:
            print(f"❌ Validation failed: {result.stderr}")
    except Exception as e:
        print(f"❌ Error testing with kubectl: {e}")