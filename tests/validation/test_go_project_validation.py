"""
Validation tests for generated Go projects.
Tests that the generated Go controllers are syntactically correct, buildable, and follow best practices.
"""

import pytest
import subprocess
import tempfile
import shutil
import json
import os
import re
from pathlib import Path
from unittest.mock import Mock, patch

# Import validation modules
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from validation.go_validator import GoProjectValidator, GoLinter, GoFormatter
from validation.crd_validator import CRDValidator
from validation.dockerfile_validator import DockerfileValidator
from validation.kubernetes_validator import KubernetesValidator


@pytest.mark.validation
class TestGoProjectValidation:
    """Test validation of generated Go projects."""

    @pytest.fixture
    def go_validator(self):
        """Create a Go project validator."""
        return GoProjectValidator()

    @pytest.fixture
    def sample_go_project(self, temp_dir):
        """Create a sample Go project for validation."""
        project_dir = temp_dir / "sample-project"
        project_dir.mkdir(parents=True)

        # Create go.mod
        (project_dir / "go.mod").write_text("""
module github.com/test/sample-controller

go 1.19

require (
    k8s.io/api v0.26.0
    k8s.io/apimachinery v0.26.0
    sigs.k8s.io/controller-runtime v0.15.0
)
""")

        # Create main.go
        (project_dir / "main.go").write_text("""
package main

import (
    "os"
    "sigs.k8s.io/controller-runtime/pkg/client/config"
    "sigs.k8s.io/controller-runtime/pkg/manager"
    "sigs.k8s.io/controller-runtime/pkg/manager/signals"
    "github.com/test/sample-controller/controllers"
)

func main() {
    mgr, err := manager.New(config.GetConfigOrDie(), manager.Options{})
    if err != nil {
        os.Exit(1)
    }

    if err = (&controllers.TestResourceReconciler{
        Client: mgr.GetClient(),
        Scheme: mgr.GetScheme(),
    }).SetupWithManager(mgr); err != nil {
        os.Exit(1)
    }

    if err := mgr.Start(signals.SetupSignalHandler()); err != nil {
        os.Exit(1)
    }
}
""")

        # Create API types
        api_dir = project_dir / "api" / "v1alpha1"
        api_dir.mkdir(parents=True)

        (api_dir / "testresource_types.go").write_text("""
package v1alpha1

import (
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1/types"
)

// TestResourceSpec defines the desired state of TestResource
type TestResourceSpec struct {
    Name     string `json:"name"`
    Replicas *int32  `json:"replicas,omitempty"`
    Enabled  bool   `json:"enabled"`
}

// TestResourceStatus defines the observed state of TestResource
type TestResourceStatus struct {
    Ready   bool   `json:"ready"`
    Message string `json:"message,omitempty"`
}

//+kubebuilder:object:root=true
//+kubebuilder:subresource:status

type TestResource struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata,omitempty"`

    Spec   TestResourceSpec   `json:"spec,omitempty"`
    Status TestResourceStatus `json:"status,omitempty"`
}

//+kubebuilder:object:root=true

type TestResourceList struct {
    metav1.TypeMeta `json:",inline"`
    metav1.ListMeta `json:"metadata,omitempty"`
    Items           []TestResource `json:"items"`
}

func init() {
    SchemeBuilder.Register(&TestResource{}, &TestResourceList{})
}
""")

        # Create controller
        controller_dir = project_dir / "controllers"
        controller_dir.mkdir(parents=True)

        (controller_dir / "testresource_controller.go").write_text("""
package controllers

import (
    "context"
    "fmt"

    "k8s.io/apimachinery/pkg/runtime"
    ctrl "sigs.k8s.io/controller-runtime"
    "sigs.k8s.io/controller-runtime/pkg/client"
    "sigs.k8s.io/controller-runtime/pkg/log"

    githubv1alpha1 "github.com/test/sample-controller/api/v1alpha1"
)

type TestResourceReconciler struct {
    client.Client
    Scheme *runtime.Scheme
}

func (r *TestResourceReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
    logger := log.FromContext(ctx)

    var testResource githubv1alpha1.TestResource
    if err := r.Get(ctx, req.NamespacedName, &testResource); err != nil {
        return ctrl.Result{}, client.IgnoreNotFound(err)
    }

    logger.Info("Reconciling TestResource", "name", testResource.Name)

    // Update status
    testResource.Status.Ready = true
    testResource.Status.Message = "Resource is ready"
    if err := r.Status().Update(ctx, &testResource); err != nil {
        return ctrl.Result{}, err
    }

    return ctrl.Result{Requeue: true}, nil
}

func (r *TestResourceReconciler) SetupWithManager(mgr ctrl.Manager) error {
    return ctrl.NewControllerManagedBy(mgr).
        For(&githubv1alpha1.TestResource{}).
        Complete(r)
}
""")

        # Create CRD YAML
        crd_dir = project_dir / "config" / "crd" / "bases"
        crd_dir.mkdir(parents=True)

        (crd_dir / "test.test.io_testresources.yaml").write_text("""
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: testresources.test.test.io
  labels:
    app.kubernetes.io/name: sample-controller
    app.kubernetes.io/managed-by: kustomize
spec:
  group: test.test.io
  names:
    kind: TestResource
    listKind: TestResourceList
    plural: testresources
    singular: testresource
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
              replicas:
                type: integer
                minimum: 0
              enabled:
                type: boolean
            required:
            - name
            - enabled
          status:
            type: object
            properties:
              ready:
                type: boolean
              message:
                type: string
    subresources:
      status: {}
""")

        return project_dir

    def test_validate_go_project_structure(self, go_validator, sample_go_project):
        """Test validation of Go project structure."""
        result = go_validator.validate_project_structure(sample_go_project)

        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert len(result["warnings"]) == 0

        # Check that all required files are found
        expected_files = [
            "go.mod",
            "main.go",
            "api/v1alpha1/testresource_types.go",
            "controllers/testresource_controller.go",
            "config/crd/bases/test.test.io_testresources.yaml"
        ]

        for expected_file in expected_files:
            assert expected_file in result["files_found"]

    def test_validate_go_syntax(self, go_validator, sample_go_project):
        """Test validation of Go syntax."""
        result = go_validator.validate_syntax(sample_go_project)

        assert result["valid"] is True
        assert len(result["syntax_errors"]) == 0

        # Check that all Go files are syntactically correct
        for go_file in sample_go_project.rglob("*.go"):
            file_result = go_validator.validate_file_syntax(go_file)
            assert file_result["valid"] is True

    def test_validate_go_dependencies(self, go_validator, sample_go_project):
        """Test validation of Go dependencies."""
        result = go_validator.validate_dependencies(sample_go_project)

        assert result["valid"] is True
        assert len(result["dependency_errors"]) == 0

        # Check for required dependencies
        required_deps = [
            "k8s.io/api",
            "k8s.io/apimachinery",
            "sigs.k8s.io/controller-runtime"
        ]

        for dep in required_deps:
            assert dep in result["dependencies_found"]

    def test_validate_go_build(self, go_validator, sample_go_project):
        """Test that the Go project builds successfully."""
        result = go_validator.validate_build(sample_go_project)

        assert result["buildable"] is True
        assert len(result["build_errors"]) == 0

    def test_validate_go_mod_consistency(self, go_validator, sample_go_project):
        """Test go.mod consistency and version compatibility."""
        result = go_validator.validate_go_mod(sample_go_project)

        assert result["valid"] is True
        assert len(result["mod_errors"]) == 0

        # Check Go version
        assert result["go_version"] == "1.19"

        # Check that all imports have corresponding dependencies
        assert len(result["missing_dependencies"]) == 0

    def test_validate_kubernetes_conventions(self, go_validator, sample_go_project):
        """Test Kubernetes controller conventions."""
        result = go_validator.validate_kubernetes_conventions(sample_go_project)

        assert result["valid"] is True
        assert len(result["convention_errors"]) == 0

        # Check for proper controller patterns
        assert "Reconcile method found" in result["conventions_verified"]
        assert "Status subresource enabled" in result["conventions_verified"]
        assert "Proper RBAC annotations" in result["conventions_verified"]

    def test_validate_error_handling(self, go_validator, sample_go_project):
        """Test error handling in generated code."""
        result = go_validator.validate_error_handling(sample_go_project)

        assert result["valid"] is True
        assert len(result["error_handling_issues"]) == 0

        # Check for proper error handling patterns
        assert "Error wrapping in Reconcile" in result["patterns_found"]
        assert "Client.IgnoreNotFound usage" in result["patterns_found"]

    def test_validate_resource_management(self, go_validator, sample_go_project):
        """Test resource management in the controller."""
        result = go_validator.validate_resource_management(sample_go_project)

        assert result["valid"] is True
        assert len(result["resource_management_issues"]) == 0

        # Check for proper resource patterns
        assert "Status updates" in result["patterns_found"]
        assert "Resource ownership" in result["patterns_found"]

    def test_validate_invalid_go_project(self, go_validator, temp_dir):
        """Test validation of an invalid Go project."""
        invalid_project = temp_dir / "invalid-project"
        invalid_project.mkdir()

        # Create invalid Go file with syntax error
        (invalid_project / "main.go").write_text("""
package main

import "fmt"

func main() {
    fmt.Println("Hello World"
    // Missing closing parenthesis - syntax error
}
""")

        result = go_validator.validate_syntax(invalid_project)

        assert result["valid"] is False
        assert len(result["syntax_errors"]) > 0

    def test_validate_missing_dependencies(self, go_validator, temp_dir):
        """Test validation when dependencies are missing."""
        project_missing_deps = temp_dir / "missing-deps"
        project_missing_deps.mkdir()

        # Create go.mod with non-existent dependency
        (project_missing_deps / "go.mod").write_text("""
module github.com/test/missing-deps

go 1.19

require (
    non-existent/pkg v1.0.0
)
""")

        (project_missing_deps / "main.go").write_text("""
package main

import "non-existent/pkg"

func main() {}
""")

        result = go_validator.validate_dependencies(project_missing_deps)

        assert result["valid"] is False
        assert len(result["dependency_errors"]) > 0
        assert "non-existent/pkg" in str(result["dependency_errors"])


@pytest.mark.validation
class TestCRDValidation:
    """Test validation of generated CRDs."""

    @pytest.fixture
    def crd_validator(self):
        """Create a CRD validator."""
        return CRDValidator()

    def test_validate_crd_structure(self, crd_validator, sample_go_project):
        """Test CRD YAML structure validation."""
        crd_file = sample_go_project / "config" / "crd" / "bases" / "test.test.io_testresources.yaml"
        result = crd_validator.validate_crd_file(crd_file)

        assert result["valid"] is True
        assert len(result["validation_errors"]) == 0

        # Check required CRD fields
        assert "apiVersion" in result["fields_found"]
        assert "kind" in result["fields_found"]
        assert "metadata" in result["fields_found"]
        assert "spec" in result["fields_found"]

    def test_validate_crd_openapi_schema(self, crd_validator, sample_go_project):
        """Test CRD OpenAPI schema validation."""
        crd_file = sample_go_project / "config" / "crd" / "bases" / "test.test.io_testresources.yaml"
        result = crd_validator.validate_openapi_schema(crd_file)

        assert result["valid"] is True
        assert len(result["schema_errors"]) == 0

        # Check schema structure
        assert "spec schema found" in result["schema_verified"]
        assert "status schema found" in result["schema_verified"]
        assert "status subresource enabled" in result["schema_verified"]

    def test_validate_crd_versioning(self, crd_validator, sample_go_project):
        """Test CRD versioning conventions."""
        crd_file = sample_go_project / "config" / "crd" / "bases" / "test.test.io_testresources.yaml"
        result = crd_validator.validate_versioning(crd_file)

        assert result["valid"] is True
        assert len(result["versioning_errors"]) == 0

        # Check versioning
        assert "served version found" in result["versioning_verified"]
        assert "storage version found" in result["versioning_verified"]

    def test_validate_crd_kubernetes_compatibility(self, crd_validator, sample_go_project):
        """Test CRD compatibility with Kubernetes."""
        crd_file = sample_go_project / "config" / "crd" / "bases" / "test.test.io_testresources.yaml"
        result = crd_validator.validate_kubernetes_compatibility(crd_file)

        assert result["compatible"] is True
        assert len(result["compatibility_issues"]) == 0

    def test_validate_invalid_crd(self, crd_validator, temp_dir):
        """Test validation of an invalid CRD."""
        invalid_crd = temp_dir / "invalid-crd.yaml"
        invalid_crd.write_text("""
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: invalid.test.io
spec:
  group: test.io
  names:
    kind: InvalidResource
  scope: Namespaced
  # Missing versions section - invalid
""")

        result = crd_validator.validate_crd_file(invalid_crd)

        assert result["valid"] is False
        assert len(result["validation_errors"]) > 0


@pytest.mark.validation
class TestDockerfileValidation:
    """Test validation of Dockerfile for generated projects."""

    @pytest.fixture
    def dockerfile_validator(self):
        """Create a Dockerfile validator."""
        return DockerfileValidator()

    @pytest.fixture
    def sample_dockerfile(self, temp_dir):
        """Create a sample Dockerfile."""
        dockerfile = temp_dir / "Dockerfile"
        dockerfile.write_text("""
# Build stage
FROM golang:1.19-alpine AS builder

WORKDIR /workspace

# Copy go mod and sum files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the binary
RUN CGO_ENABLED=0 GOOS=linux go build -a -o manager .

# Final stage
FROM gcr.io/distroless/static:nonroot

WORKDIR /

# Copy the binary from builder stage
COPY --from=builder /workspace/manager .

# User to run the container
USER 65532:65532

# Entry point
ENTRYPOINT ["/manager"]
""")
        return dockerfile

    def test_validate_dockerfile_structure(self, dockerfile_validator, sample_dockerfile):
        """Test Dockerfile structure validation."""
        result = dockerfile_validator.validate_structure(sample_dockerfile)

        assert result["valid"] is True
        assert len(result["structure_errors"]) == 0

        # Check for multi-stage build
        assert "multi-stage build" in result["patterns_found"]

        # Check for distroless base image
        assert "distroless base image" in result["patterns_found"]

    def test_validate_dockerfile_security(self, dockerfile_validator, sample_dockerfile):
        """Test Dockerfile security validation."""
        result = dockerfile_validator.validate_security(sample_dockerfile)

        assert result["secure"] is True
        assert len(result["security_issues"]) == 0

        # Check for security best practices
        assert "non-root user" in result["security_practices"]
        assert "minimal base image" in result["security_practices"]

    def test_validate_dockerfile_optimization(self, dockerfile_validator, sample_dockerfile):
        """Test Dockerfile optimization."""
        result = dockerfile_validator.validate_optimization(sample_dockerfile)

        assert result["optimized"] is True
        assert len(result["optimization_issues"]) == 0

        # Check for optimization patterns
        assert "layer caching" in result["optimizations_found"]
        assert "static binary" in result["optimizations_found"]

    def test_validate_invalid_dockerfile(self, dockerfile_validator, temp_dir):
        """Test validation of an invalid Dockerfile."""
        invalid_dockerfile = temp_dir / "Dockerfile"
        invalid_dockerfile.write_text("""
FROM ubuntu:latest

RUN apt-get update && apt-get install -y wget curl

# Run as root - security issue
USER root

# Copy everything including unnecessary files
COPY . .

CMD ["./app"]
""")

        result = dockerfile_validator.validate_security(invalid_dockerfile)

        assert result["secure"] is False
        assert len(result["security_issues"]) > 0
        assert "root user" in str(result["security_issues"]).lower()


@pytest.mark.validation
class TestKubernetesValidation:
    """Test Kubernetes deployment validation."""

    @pytest.fixture
    def k8s_validator(self):
        """Create a Kubernetes validator."""
        return KubernetesValidator()

    @pytest.fixture
    def sample_k8s_manifests(self, temp_dir):
        """Create sample Kubernetes manifests."""
        manifests_dir = temp_dir / "k8s-manifests"
        manifests_dir.mkdir()

        # Create deployment manifest
        deployment = manifests_dir / "deployment.yaml"
        deployment.write_text("""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sample-controller
  labels:
    app: sample-controller
spec:
  replicas: 1
  selector:
    matchLabels:
      app: sample-controller
  template:
    metadata:
      labels:
        app: sample-controller
    spec:
      containers:
      - name: controller
        image: sample-controller:latest
        imagePullPolicy: IfNotPresent
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
          readOnlyRootFilesystem: true
          allowPrivilegeEscalation: false
""")

        # Create RBAC manifest
        rbac = manifests_dir / "rbac.yaml"
        rbac.write_text("""
apiVersion: v1
kind: ServiceAccount
metadata:
  name: sample-controller
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: sample-controller
rules:
- apiGroups: [""]
  resources: ["events"]
  verbs: ["create", "patch"]
- apiGroups: ["test.test.io"]
  resources: ["testresources"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["test.test.io"]
  resources: ["testresources/status"]
  verbs: ["get", "update", "patch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: sample-controller
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: sample-controller
subjects:
- kind: ServiceAccount
  name: sample-controller
  namespace: default
""")

        return manifests_dir

    def test_validate_deployment_manifest(self, k8s_validator, sample_k8s_manifests):
        """Test deployment manifest validation."""
        deployment_file = sample_k8s_manifests / "deployment.yaml"
        result = k8s_validator.validate_deployment(deployment_file)

        assert result["valid"] is True
        assert len(result["validation_errors"]) == 0

        # Check for best practices
        assert "resource limits" in result["best_practices_found"]
        assert "security context" in result["best_practices_found"]
        assert "non-root user" in result["best_practices_found"]

    def test_validate_rbac_manifest(self, k8s_validator, sample_k8s_manifests):
        """Test RBAC manifest validation."""
        rbac_file = sample_k8s_manifests / "rbac.yaml"
        result = k8s_validator.validate_rbac(rbac_file)

        assert result["valid"] is True
        assert len(result["validation_errors"]) == 0

        # Check for proper RBAC
        assert "service account" in result["rbac_components"]
        assert "cluster role" in result["rbac_components"]
        assert "role binding" in result["rbac_components"]

    def test_validate_kubernetes_security(self, k8s_validator, sample_k8s_manifests):
        """Test Kubernetes security validation."""
        deployment_file = sample_k8s_manifests / "deployment.yaml"
        result = k8s_validator.validate_security(deployment_file)

        assert result["secure"] is True
        assert len(result["security_issues"]) == 0

        # Check security practices
        assert "non-root container" in result["security_practices"]
        assert "read-only filesystem" in result["security_practices"]
        assert "no privilege escalation" in result["security_practices"]

    def test_validate_kubernetes_resources(self, k8s_validator, sample_k8s_manifests):
        """Test Kubernetes resource configuration."""
        deployment_file = sample_k8s_manifests / "deployment.yaml"
        result = k8s_validator.validate_resources(deployment_file)

        assert result["resources_configured"] is True
        assert len(result["resource_issues"]) == 0

        # Check resource specifications
        assert "memory requests" in result["resources_found"]
        assert "cpu requests" in result["resources_found"]
        assert "memory limits" in result["resources_found"]
        assert "cpu limits" in result["resources_found"]


@pytest.mark.validation
class TestEndToEndValidation:
    """End-to-end validation of generated projects."""

    def test_complete_project_validation(self, temp_dir):
        """Test complete validation of a generated project."""
        # Create validator instances
        go_validator = GoProjectValidator()
        crd_validator = CRDValidator()
        dockerfile_validator = DockerfileValidator()
        k8s_validator = KubernetesValidator()

        # Create complete project structure
        project_dir = temp_dir / "complete-project"
        project_dir.mkdir()

        # Add all required files (simplified version)
        (project_dir / "go.mod").write_text("""
module github.com/test/complete

go 1.19
""")

        (project_dir / "main.go").write_text("""
package main
func main() {}
""")

        api_dir = project_dir / "api" / "v1alpha1"
        api_dir.mkdir(parents=True)
        (api_dir / "types.go").write_text("""
package v1alpha1
type CompleteResource struct{}
""")

        config_dir = project_dir / "config" / "crd" / "bases"
        config_dir.mkdir(parents=True)
        (config_dir / "crd.yaml").write_text("""
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: completeresources.test.io
spec:
  group: test.io
  names:
    kind: CompleteResource
    plural: completeresources
  scope: Namespaced
  versions:
  - name: v1alpha1
    served: true
    storage: true
""")

        (project_dir / "Dockerfile").write_text("""
FROM golang:1.19-alpine AS builder
WORKDIR /workspace
COPY go.mod ./
RUN go mod download
COPY . .
RUN go build -a -o manager .
FROM gcr.io/distroless/static:nonroot
COPY --from=builder /workspace/manager .
ENTRYPOINT ["/manager"]
""")

        k8s_dir = project_dir / "k8s"
        k8s_dir.mkdir()
        (k8s_dir / "deployment.yaml").write_text("""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: complete-controller
spec:
  replicas: 1
  selector:
    matchLabels:
      app: complete-controller
  template:
    spec:
      containers:
      - name: controller
        image: complete-controller:latest
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
""")

        # Run complete validation
        validation_results = {
            "go_project": go_validator.validate_project_structure(project_dir),
            "go_syntax": go_validator.validate_syntax(project_dir),
            "crd": crd_validator.validate_crd_file(config_dir / "crd.yaml"),
            "dockerfile": dockerfile_validator.validate_structure(project_dir / "Dockerfile"),
            "k8s_deployment": k8s_validator.validate_deployment(k8s_dir / "deployment.yaml")
        }

        # Verify all validations pass
        for validation_type, result in validation_results.items():
            assert result["valid"] is True, f"Validation failed for {validation_type}: {result.get('errors', [])}"

        # Generate validation report
        validation_report = {
            "project_name": "complete-project",
            "validation_summary": {
                "total_validations": len(validation_results),
                "passed_validations": sum(1 for r in validation_results.values() if r["valid"]),
                "failed_validations": sum(1 for r in validation_results.values() if not r["valid"])
            },
            "detailed_results": validation_results
        }

        assert validation_report["validation_summary"]["passed_validations"] == validation_report["validation_summary"]["total_validations"]