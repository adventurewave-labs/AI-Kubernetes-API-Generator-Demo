"""
Test data for agent requests and responses.
Contains sample natural language requests and expected outputs.
"""

import json
from typing import Dict, List, Any


# Sample natural language requests for testing
SAMPLE_REQUESTS = {
    "simple_vector_db": {
        "input": "I need to create a VectorDB API for our new AI platform. The spec should include a string for engine_type (like 'pinecone' or 'weaviate') and an integer for the number of replicas.",
        "expected_spec": {
            "group": "platform.ai.example.io",
            "version": "v1alpha1",
            "kind": "VectorDB",
            "spec": {
                "properties": {
                    "engine_type": {"type": "string"},
                    "replicas": {"type": "integer"}
                }
            }
        },
        "category": "database",
        "complexity": "simple"
    },

    "notebook_crd": {
        "input": "I need a Notebook CRD for our data science team. It should have a cpu field and a memory field, both strings.",
        "expected_spec": {
            "group": "datascience.example.io",
            "version": "v1alpha1",
            "kind": "Notebook",
            "spec": {
                "properties": {
                    "cpu": {"type": "string"},
                    "memory": {"type": "string"}
                }
            }
        },
        "category": "compute",
        "complexity": "simple"
    },

    "cluster_claim": {
        "input": "Make me a simple ClusterClaim API with a clusterId string field.",
        "expected_spec": {
            "group": "platform.example.io",
            "version": "v1alpha1",
            "kind": "ClusterClaim",
            "spec": {
                "properties": {
                    "clusterId": {"type": "string"}
                }
            }
        },
        "category": "infrastructure",
        "complexity": "simple"
    },

    "database_cluster": {
        "input": "Create a DatabaseCluster API with fields for engine (postgres, mysql), version (string), replicas (int), storage_size (string), and backup_enabled (boolean)",
        "expected_spec": {
            "group": "database.example.io",
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
        },
        "category": "database",
        "complexity": "medium"
    },

    "cache_cluster": {
        "input": "Create a CacheCluster API for Redis/Memcached with engine_type, capacity, shard_count, and eviction_policy fields",
        "expected_spec": {
            "group": "cache.example.io",
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
        },
        "category": "cache",
        "complexity": "medium"
    },

    "message_queue": {
        "input": "Create a MessageQueue API with fields for broker_type (kafka, rabbitmq), topic_count, partition_count, and retention_days",
        "expected_spec": {
            "group": "messaging.example.io",
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
        },
        "category": "messaging",
        "complexity": "medium"
    },

    "microservice": {
        "input": "Create a comprehensive microservice API with fields for service discovery, load balancing, health checks, circuit breakers, retries, timeouts, authentication, authorization, rate limiting, monitoring, logging, tracing, and deployment configuration",
        "expected_spec": {
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
        },
        "category": "microservice",
        "complexity": "complex"
    }
}


# Invalid requests for error testing
INVALID_REQUESTS = {
    "empty": {
        "input": "",
        "expected_error": "Empty request",
        "error_type": "ValidationError"
    },

    "too_vague": {
        "input": "Make something cool",
        "expected_error": "Request too vague",
        "error_type": "ValidationError"
    },

    "invalid_syntax": {
        "input": "Create API with {invalid json syntax",
        "expected_error": "Invalid syntax in request",
        "error_type": "ParseError"
    },

    "no_spec_fields": {
        "input": "Create a simple API without any fields",
        "expected_error": "No spec fields specified",
        "error_type": "ValidationError"
    },

    "malformed_json": {
        "input": "Create API with spec: {invalid: json, missing: quotes}",
        "expected_error": "Malformed JSON in request",
        "error_type": "ParseError"
    }
}


# OpenAI API response mocks
MOCK_OPENAI_RESPONSES = {
    "simple_vector_db": {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "command": [
                        "openapi-mcp-codegen",
                        "--output-dir", "/tmp/vectordb",
                        "--go-header-file", "hack/boilerplate.go.txt",
                        "--input-spec", json.dumps(SAMPLE_REQUESTS["simple_vector_db"]["expected_spec"])
                    ]
                })
            }
        }]
    },

    "notebook_crd": {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "command": [
                        "openapi-mcp-codegen",
                        "--output-dir", "/tmp/notebook",
                        "--go-header-file", "hack/boilerplate.go.txt",
                        "--input-spec", json.dumps(SAMPLE_REQUESTS["notebook_crd"]["expected_spec"])
                    ]
                })
            }
        }]
    },

    "error_response": {
        "choices": [{
            "message": {
                "content": "invalid json response"
            }
        }]
    },

    "missing_command": {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "response": "No command here"
                })
            }
        }]
    }
}


# Performance test data
PERFORMANCE_REQUESTS = {
    "simple": "Create a simple API with name field",
    "medium": "Create a database API with fields for engine, version, replicas, storage, and configuration",
    "large": (
        "Create a comprehensive microservice API with fields for service discovery, load balancing, "
        "health checks, circuit breakers, retries, timeouts, authentication, authorization, "
        "rate limiting, monitoring, logging, tracing, deployment configuration"
    ),
    "complex_nested": (
        "Create a complex application API with nested structures including infrastructure config, "
        "application settings, security policies, monitoring configuration, and deployment strategies"
    )
}


# Test specifications for codegen validation
VALID_SPECIFICATIONS = [
    {
        "group": "platform.example.io",
        "version": "v1alpha1",
        "kind": "TestResource",
        "spec": {
            "properties": {
                "name": {"type": "string"}
            }
        }
    },
    {
        "group": "database.example.io",
        "version": "v1beta1",
        "kind": "Database",
        "spec": {
            "properties": {
                "engine": {"type": "string"},
                "replicas": {"type": "integer"},
                "storage": {"type": "object"},
                "backup": {"type": "boolean"}
            }
        }
    },
    {
        "group": "complex.example.io",
        "version": "v1alpha1",
        "kind": "ComplexResource",
        "spec": {
            "properties": {
                "config": {
                    "type": "object",
                    "properties": {
                        "nested": {"type": "string"}
                    }
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }
        }
    }
]


# Invalid specifications for validation testing
INVALID_SPECIFICATIONS = [
    {
        "description": "Empty spec",
        "spec": {}
    },
    {
        "description": "Missing group",
        "spec": {
            "version": "v1",
            "kind": "Test",
            "spec": {"properties": {}}
        }
    },
    {
        "description": "Invalid group format",
        "spec": {
            "group": "invalid-group-name",
            "version": "v1",
            "kind": "Test",
            "spec": {"properties": {}}
        }
    },
    {
        "description": "Invalid version format",
        "spec": {
            "group": "test.io",
            "version": "invalid-version",
            "kind": "Test",
            "spec": {"properties": {}}
        }
    },
    {
        "description": "Invalid kind format",
        "spec": {
            "group": "test.io",
            "version": "v1",
            "kind": "invalid_kind",
            "spec": {"properties": {}}
        }
    },
    {
        "description": "Too many fields",
        "spec": {
            "group": "test.io",
            "version": "v1",
            "kind": "Test",
            "spec": {
                "properties": {
                    f"field_{i}": {"type": "string"}
                    for i in range(100)  # Exceeds reasonable limit
                }
            }
        }
    ]
]


# Go project templates for validation testing
GO_PROJECT_TEMPLATES = {
    "minimal": {
        "files": {
            "go.mod": "module github.com/test/minimal\ngo 1.19\n",
            "main.go": "package main\n\nfunc main() {}\n"
        },
        "description": "Minimal Go project"
    },

    "kubernetes_controller": {
        "files": {
            "go.mod": """
module github.com/test/controller

go 1.19

require (
    k8s.io/api v0.26.0
    k8s.io/apimachinery v0.26.0
    sigs.k8s.io/controller-runtime v0.15.0
)
""",
            "main.go": """
package main

import (
    "os"
    "sigs.k8s.io/controller-runtime/pkg/client/config"
    "sigs.k8s.io/controller-runtime/pkg/manager"
    "sigs.k8s.io/controller-runtime/pkg/manager/signals"
)

func main() {
    mgr, err := manager.New(config.GetConfigOrDie(), manager.Options{})
    if err != nil {
        os.Exit(1)
    }

    if err := mgr.Start(signals.SetupSignalHandler()); err != nil {
        os.Exit(1)
    }
}
""",
            "api/v1alpha1/testresource_types.go": """
package v1alpha1

import (
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1/types"
)

// TestResourceSpec defines the desired state of TestResource
type TestResourceSpec struct {
    Name string `json:"name"`
}

//+kubebuilder:object:root=true

type TestResource struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`
    Spec   TestResourceSpec `json:"spec,omitempty"`
}

func init() {
    SchemeBuilder.Register(&TestResource{}, &TestResourceList{})
}
"""
        },
        "description": "Kubernetes controller project"
    }
}


# Dockerfile templates for testing
DOCKERFILE_TEMPLATES = {
    "valid_multistage": """
# Build stage
FROM golang:1.19-alpine AS builder
WORKDIR /workspace
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -o manager .

# Final stage
FROM gcr.io/distroless/static:nonroot
COPY --from=builder /workspace/manager .
USER 65532:65532
ENTRYPOINT ["/manager"]
""",

    "invalid_root_user": """
FROM ubuntu:latest
RUN apt-get update && apt-get install -y wget
COPY . .
USER root
CMD ["./app"]
""",

    "missing_multistage": """
FROM golang:1.19-alpine
WORKDIR /app
COPY . .
RUN go build -o app .
CMD ["./app"]
"""
}


# Kubernetes manifest templates
KUBERNETES_TEMPLATES = {
    "valid_deployment": """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-controller
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-controller
  template:
    metadata:
      labels:
        app: test-controller
    spec:
      containers:
      - name: controller
        image: test-controller:latest
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "100m"
        securityContext:
          runAsNonRoot: true
          runAsUser: 65532
""",
    "valid_rbac": """
apiVersion: v1
kind: ServiceAccount
metadata:
  name: test-controller
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: test-controller
rules:
- apiGroups: [""]
  resources: ["events"]
  verbs: ["create", "patch"]
- apiGroups: ["test.example.io"]
  resources: ["testresources"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: test-controller
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: test-controller
subjects:
- kind: ServiceAccount
  name: test-controller
  namespace: default
""",
    "valid_crd": """
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
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              name:
                type: string
            required:
            - name
"""
}


# Test configuration data
TEST_CONFIGURATIONS = {
    "default": {
        "default_group": "platform.test.io",
        "default_version": "v1alpha1",
        "openai_model": "gpt-4",
        "temperature": 0.1,
        "max_tokens": 1000
    },

    "custom": {
        "default_group": "custom.example.io",
        "default_version": "v1beta1",
        "openai_model": "gpt-3.5-turbo",
        "temperature": 0.2,
        "max_tokens": 1500
    },

    "production": {
        "default_group": "platform.production.io",
        "default_version": "v1",
        "openai_model": "gpt-4",
        "temperature": 0.0,
        "max_tokens": 2000
    }
}


# Error scenarios for testing
ERROR_SCENARIOS = {
    "openai_api_error": {
        "exception": Exception("OpenAI API error: rate limit exceeded"),
        "expected_message": "Error communicating with OpenAI API",
        "error_code": "OPENAI_API_ERROR"
    },

    "subprocess_error": {
        "exception": Exception("Command failed with exit code 1"),
        "expected_message": "Error executing codegen command",
        "error_code": "COMMAND_EXECUTION_ERROR"
    },

    "json_parse_error": {
        "exception": json.JSONDecodeError("Expecting value", "", 0),
        "expected_message": "Error parsing LLM response",
        "error_code": "JSON_PARSE_ERROR"
    },

    "validation_error": {
        "exception": ValueError("Invalid API specification"),
        "expected_message": "Invalid API specification",
        "error_code": "VALIDATION_ERROR"
    },

    "file_not_found": {
        "exception": FileNotFoundError("No such file or directory: 'openapi-mcp-codegen'"),
        "expected_message": "openapi-mcp-codegen not found in PATH",
        "error_code": "BINARY_NOT_FOUND"
    }
}


# Benchmark data for performance testing
BENCHMARK_DATA = {
    "request_complexity_levels": {
        "level_1": {
            "description": "Simple single field",
            "request": "Create API with name field",
            "expected_fields": 1
        },
        "level_2": {
            "description": "Multiple basic fields",
            "request": "Create API with name, description, and enabled fields",
            "expected_fields": 3
        },
        "level_3": {
            "description": "Mixed field types",
            "request": "Create API with string name, integer replicas, boolean enabled, and object config",
            "expected_fields": 4
        },
        "level_4": {
            "description": "Complex nested structures",
            "request": "Create API with nested config objects, arrays, and multiple levels of nesting",
            "expected_fields": 10
        },
        "level_5": {
            "description": "Very complex enterprise API",
            "request": "Create enterprise API with comprehensive configuration, security, monitoring, and deployment settings",
            "expected_fields": 25
        }
    },

    "concurrency_levels": [1, 2, 4, 8, 16, 32],

    "performance_thresholds": {
        "simple_request_max_time": 1.0,  # seconds
        "medium_request_max_time": 2.0,
        "complex_request_max_time": 5.0,
        "max_memory_usage": 50 * 1024 * 1024,  # 50MB
        "min_throughput": 2.0,  # requests per second
        "max_cpu_usage": 80.0  # percentage
    }
}


# Helper functions for test data
def get_sample_request(request_name: str) -> Dict[str, Any]:
    """Get a sample request by name."""
    return SAMPLE_REQUESTS.get(request_name, {})


def get_invalid_request(request_name: str) -> Dict[str, Any]:
    """Get an invalid request by name."""
    return INVALID_REQUESTS.get(request_name, {})


def get_mock_openai_response(response_name: str) -> Dict[str, Any]:
    """Get a mock OpenAI response by name."""
    return MOCK_OPENAI_RESPONSES.get(response_name, {})


def get_valid_specification(index: int = 0) -> Dict[str, Any]:
    """Get a valid specification by index."""
    return VALID_SPECIFICATIONS[index % len(VALID_SPECIFICATIONS)]


def get_invalid_specification(index: int = 0) -> Dict[str, Any]:
    """Get an invalid specification by index."""
    invalid_specs = INVALID_SPECIFICATIONS[index % len(INVALID_SPECIFICATIONS)]
    return invalid_specs["spec"]


def get_go_project_template(template_name: str) -> Dict[str, Any]:
    """Get a Go project template by name."""
    return GO_PROJECT_TEMPLATES.get(template_name, {})


def get_dockerfile_template(template_name: str) -> str:
    """Get a Dockerfile template by name."""
    return DOCKERFILE_TEMPLATES.get(template_name, "")


def get_kubernetes_template(template_name: str) -> str:
    """Get a Kubernetes manifest template by name."""
    return KUBERNETES_TEMPLATES.get(template_name, "")


def get_test_configuration(config_name: str) -> Dict[str, Any]:
    """Get test configuration by name."""
    return TEST_CONFIGURATIONS.get(config_name, {})


def get_error_scenario(scenario_name: str) -> Dict[str, Any]:
    """Get error scenario by name."""
    return ERROR_SCENARIOS.get(scenario_name, {})


def get_benchmark_data(data_path: str) -> Any:
    """Get benchmark data by path."""
    keys = data_path.split('.')
    data = BENCHMARK_DATA
    for key in keys:
        data = data.get(key, {})
    return data


def get_all_sample_requests() -> List[Dict[str, Any]]:
    """Get all sample requests."""
    return list(SAMPLE_REQUESTS.values())


def get_all_invalid_requests() -> List[Dict[str, Any]]:
    """Get all invalid requests."""
    return list(INVALID_REQUESTS.values())


def get_requests_by_category(category: str) -> List[Dict[str, Any]]:
    """Get all requests in a specific category."""
    return [req for req in SAMPLE_REQUESTS.values() if req.get("category") == category]


def get_requests_by_complexity(complexity: str) -> List[Dict[str, Any]]:
    """Get all requests with a specific complexity level."""
    return [req for req in SAMPLE_REQUESTS.values() if req.get("complexity") == complexity]