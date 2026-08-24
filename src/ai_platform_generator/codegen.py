"""
Code Generation Integration

This module handles the integration with external code generation tools,
particularly openapi-mcp-codegen for generating MCP servers and Kubernetes
controllers.
"""

import os
import subprocess
import shutil
from pathlib import Path
import yaml
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json

from .agent import CodegenRequest


@dataclass
class GenerationResult:
    """Result of a code generation operation."""
    success: bool
    output_path: str
    command: List[str]
    stdout: str
    stderr: str
    generated_files: List[str]


class CodeGenerator:
    """Handles code generation using external tools."""

    def __init__(self, openapi_codegen_path: Optional[str] = None):
        """Initialize the code generator."""
        try:
            self.openapi_codegen_path = openapi_codegen_path or self._find_codegen_tool()
        except FileNotFoundError:
            # Allow initialization without MCP codegen tool for K8s controller generation
            self.openapi_codegen_path = None

    def _find_codegen_tool(self) -> str:
        """Find the openapi-mcp-codegen tool."""
        # First check if it's available in PATH
        path = shutil.which("openapi_mcp_codegen")
        if path:
            return path

        # Check the cloned repository
        repo_path = Path(__file__).parent.parent.parent.parent / "openapi-mcp-codegen"
        if repo_path.exists():
            if (repo_path / "openapi_mcp_codegen" / "__main__.py").exists():
                return str(repo_path / "openapi_mcp_codegen" / "__main__.py")

        raise FileNotFoundError(
            "openapi-mcp-codegen tool not found. Please install it or clone the repository."
        )

    def generate_openapi_spec(self, request: CodegenRequest) -> Dict[str, Any]:
        """
        Generate an OpenAPI specification from the codegen request.

        Args:
            request: The code generation request

        Returns:
            Dict: OpenAPI specification
        """
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": f"{request.kind} API",
                "version": request.version,
                "description": request.description
            },
            "paths": {},
            "components": {
                "schemas": {
                    request.kind: {
                        "type": "object",
                        "properties": {
                            "apiVersion": {
                                "type": "string",
                                "description": f"API version, e.g., {request.group}/{request.version}"
                            },
                            "kind": {
                                "type": "string",
                                "description": f"Resource kind, e.g., {request.kind}"
                            },
                            "metadata": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "namespace": {"type": "string"}
                                }
                            },
                            "spec": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    }
                }
            }
        }

        # Add spec properties
        schema = spec["components"]["schemas"][request.kind]["properties"]["spec"]
        for prop_name, prop_info in request.spec_properties.items():
            if isinstance(prop_info, dict):
                schema["properties"][prop_name] = {
                    "type": prop_info.get("type", "string"),
                    "description": prop_info.get("description", f"Specification for {prop_name}")
                }
            else:
                # Handle legacy string format
                schema["properties"][prop_name] = {
                    "type": prop_info,
                    "description": f"Specification for {prop_name}"
                }

        return spec

    def generate_mcp_server(self, request: CodegenRequest) -> GenerationResult:
        """
        Generate an MCP server from the request.

        Args:
            request: The code generation request

        Returns:
            GenerationResult: Result of the generation operation
        """
        if not self.openapi_codegen_path:
            return GenerationResult(
                success=False,
                stderr="openapi-mcp-codegen tool not available. MCP server generation requires the tool to be installed."
            )

        # Create OpenAPI spec
        openapi_spec = self.generate_openapi_spec(request)

        # Write spec to temporary file
        spec_file = Path("/tmp") / f"{request.kind.lower()}_spec.json"
        with open(spec_file, 'w') as f:
            json.dump(openapi_spec, f, indent=2)

        # Prepare command
        cmd = []
        if self.openapi_codegen_path.endswith("__main__.py"):
            cmd = ["python", self.openapi_codegen_path]
        else:
            cmd = [self.openapi_codegen_path]

        cmd.extend([
            "--spec-file", str(spec_file),
            "--output-dir", request.output_dir,
            "--generate-agent",
            "--generate-eval"
        ])

        try:
            # Execute the command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            # Find generated files
            generated_files = []
            output_path = Path(request.output_dir)
            if output_path.exists():
                generated_files = [str(f) for f in output_path.rglob("*") if f.is_file()]

            return GenerationResult(
                success=True,
                output_path=request.output_dir,
                command=cmd,
                stdout=result.stdout,
                stderr=result.stderr,
                generated_files=generated_files
            )

        except subprocess.CalledProcessError as e:
            return GenerationResult(
                success=False,
                output_path=request.output_dir,
                command=cmd,
                stdout=e.stdout or "",
                stderr=e.stderr or str(e),
                generated_files=[]
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                output_path=request.output_dir,
                command=cmd,
                stdout="",
                stderr=str(e),
                generated_files=[]
            )

    def generate_kubernetes_controller(self, request: CodegenRequest) -> GenerationResult:
        """
        Generate a Kubernetes controller from the request.

        This creates a basic controller structure that can be extended.

        Args:
            request: The code generation request

        Returns:
            GenerationResult: Result of the generation operation
        """
        output_path = Path(request.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        try:
            # Generate basic project structure
            files_created = []

            # Create main.go
            main_go = output_path / "main.go"
            main_content = self._generate_main_go(request)
            main_go.write_text(main_content)
            files_created.append(str(main_go))

            # Create API types
            api_dir = output_path / "api" / request.version
            api_dir.mkdir(parents=True, exist_ok=True)

            types_file = api_dir / f"{request.kind.lower()}_types.go"
            types_content = self._generate_types_go(request)
            types_file.write_text(types_content)
            files_created.append(str(types_file))

            # Create controller
            controller_dir = output_path / "internal" / "controller"
            controller_dir.mkdir(parents=True, exist_ok=True)

            controller_file = controller_dir / f"{request.kind.lower()}_controller.go"
            controller_content = self._generate_controller_go(request)
            controller_file.write_text(controller_content)
            files_created.append(str(controller_file))

            # Create Dockerfile
            dockerfile = output_path / "Dockerfile"
            dockerfile_content = self._generate_dockerfile(request)
            dockerfile.write_text(dockerfile_content)
            files_created.append(str(dockerfile))

            # Create go.mod
            go_mod = output_path / "go.mod"
            go_mod_content = self._generate_go_mod(request)
            go_mod.write_text(go_mod_content)
            files_created.append(str(go_mod))

            return GenerationResult(
                success=True,
                output_path=str(output_path),
                command=["generate_k8s_controller"],
                stdout="Kubernetes controller generated successfully",
                stderr="",
                generated_files=files_created
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                output_path=str(output_path),
                command=["generate_k8s_controller"],
                stdout="",
                stderr=str(e),
                generated_files=[]
            )

    def _generate_main_go(self, request: CodegenRequest) -> str:
        """Generate main.go content."""
        return f'''package main

import (
	"flag"
	"os"
	"time"

	"k8s.io/apimachinery/pkg/runtime"
	utilruntime "k8s.io/apimachinery/pkg/util/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	_ "k8s.io/client-go/plugin/pkg/client/auth/gcp"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"

	{request.group.lower()}/v{request.version.replace("v", "").replace("alpha", "alpha")}
	//+kubebuilder:scaffold:imports
)

var (
	scheme   = runtime.NewScheme()
	setupLog = ctrl.Log.WithName("setup")
)

func init() {{
	utilruntime.Must(clientgoscheme.AddToScheme(scheme))
	utilruntime.Must(v{request.version.replace("v", "").replace("alpha", "alpha")}.AddToScheme(scheme))
	//+kubebuilder:scaffold:scheme
}}

func main() {{
	var metricsAddr string
	var enableLeaderElection bool
	var probeAddr string

	flag.StringVar(&metricsAddr, "metrics-bind-address", ":8080", "The address the metric endpoint binds to.")
	flag.StringVar(&probeAddr, "health-probe-bind-address", ":8081", "The address the probe endpoint binds to.")
	flag.BoolVar(&enableLeaderElection, "leader-elect", false,
		"Enable leader election for controller manager. "+
			"Enabling this will ensure there is only one active controller manager.")
	opts := zap.Options{{
		Development: true,
	}}
	opts.BindFlags(flag.CommandLine)
	flag.Parse()

	ctrl.SetLogger(zap.New(zap.UseFlagOptions(&opts)))

	mgr, err := ctrl.NewManager(ctrl.GetConfigOrDie(), ctrl.Options{{
		Scheme:                 scheme,
		MetricsBindAddress:     metricsAddr,
		Port:                   9443,
		HealthProbeBindAddress: probeAddr,
		LeaderElection:         enableLeaderElection,
		LeaderElectionID:       "{request.kind.lower()}.controller",
	}})
	if err != nil {{
		setupLog.Error(err, "unable to start manager")
		os.Exit(1)
	}}

	if err = (&{request.kind}Reconciler{{
		Client: mgr.GetClient(),
		Scheme: mgr.GetScheme(),
	}}).SetupWithManager(mgr); err != nil {{
		setupLog.Error(err, "unable to create controller", "controller", "{request.kind}")
		os.Exit(1)
	}}
	//+kubebuilder:scaffold:builder

	if err := mgr.AddHealthzCheck("healthz", healthz.Ping); err != nil {{
		setupLog.Error(err, "unable to set up health check")
		os.Exit(1)
	}}
	if err := mgr.AddReadyzCheck("readyz", healthz.Ping); err != nil {{
		setupLog.Error(err, "unable to set up ready check")
		os.Exit(1)
	}}

	setupLog.Info("starting manager")
	if err := mgr.Start(ctrl.SetupSignalHandler()); err != nil {{
		setupLog.Error(err, "problem running manager")
		os.Exit(1)
	}}
}}
'''

    def _generate_types_go(self, request: CodegenRequest) -> str:
        """Generate types.go content."""
        spec_fields = []
        for prop_name, prop_info in request.spec_properties.items():
            if isinstance(prop_info, dict):
                go_type = self._map_type_to_go(prop_info.get("type", "string"))
                spec_fields.append(f"	// {prop_name} is the {prop_info.get('description', prop_name)}")
            else:
                # Handle legacy string format
                go_type = self._map_type_to_go(prop_info)
                spec_fields.append(f"	// {prop_name} is the {prop_name}")
            spec_fields.append(f"	{prop_name} {go_type} `json:\"{prop_name}\"`")

        spec_fields_str = "\n".join(spec_fields)

        return f'''package v{request.version.replace("v", "").replace("alpha", "alpha")}

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// EDIT THIS FILE!  THIS IS SCAFFOLDING FOR YOU TO OWN!
// NOTE: json tags are required.  Any new fields you add must have json tags for the fields to be serialized.

// {request.kind}Spec defines the desired state of {request.kind}
type {request.kind}Spec struct {{
{spec_fields_str}
}}

// {request.kind}Status defines the observed state of {request.kind}
type {request.kind}Status struct {{
	// INSERT ADDITIONAL STATUS FIELD - define observed state of cluster
	// Important: Run "make" to regenerate code after modifying this file
}}

//+kubebuilder:object:root=true
//+kubebuilder:subresource:status

// {request.kind} is the Schema for the {request.kind.lower()}s API
type {request.kind} struct {{
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   {request.kind}Spec   `json:"spec,omitempty"`
	Status {request.kind}Status `json:"status,omitempty"`
}}

//+kubebuilder:object:root=true

// {request.kind}List contains a list of {request.kind}
type {request.kind}List struct {{
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []{request.kind} `json:"items"`
}}

func init() {{
	SchemeBuilder.Register(&{request.kind}{{}}, &{request.kind}List{{}})
}}
'''

    def _generate_controller_go(self, request: CodegenRequest) -> str:
        """Generate controller.go content."""
        return f'''package controller

import (
	"context"

	"k8s.io/apimachinery/pkg/runtime"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"

	"{request.group.lower()}/v{request.version.replace("v", "").replace("alpha", "alpha")}"
)

// {request.kind}Reconciler reconciles a {request.kind} object
type {request.kind}Reconciler struct {{
	client.Client
	Scheme *runtime.Scheme
}}

//+kubebuilder:rbac:groups={request.group},resources={request.kind.lower()}s,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups={request.group},resources={request.kind.lower()}s/status,verbs=get;update;patch
//+kubebuilder:rbac:groups={request.group},resources={request.kind.lower()}s/finalizers,verbs=update

// Reconcile is part of the main kubernetes reconciliation loop which aims to
// move the current state of the cluster closer to the desired state.
func (r *{request.kind}Reconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {{
	logger := log.FromContext(ctx)

	// TODO(user): your logic here

	return ctrl.Result{{}}, nil
}}

// SetupWithManager sets up the controller with the Manager.
func (r *{request.kind}Reconciler) SetupWithManager(mgr ctrl.Manager) error {{
	return ctrl.NewControllerManagedBy(mgr).
		For(&v{request.version.replace("v", "").replace("alpha", "alpha")}.{request.kind}{{}}).
		Complete(r)
}}
'''

    def _generate_dockerfile(self, request: CodegenRequest) -> str:
        """Generate Dockerfile content."""
        return f'''# Build the manager binary
FROM golang:1.21 as builder

WORKDIR /workspace
# Copy the Go Modules manifests
COPY go.mod go.mod
COPY go.sum go.sum
# cache deps before building and copying source so that we don't need to re-download as much
RUN go mod download

# Copy the go source
COPY main.go main.go
COPY api/ api/
COPY internal/ internal/

# Build
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -a -o manager main.go

# Use distroless as minimal base image to package the manager binary
FROM gcr.io/distroless/static:nonroot
WORKDIR /

COPY --from=builder /workspace/manager .
USER 65532:65532

ENTRYPOINT ["/manager"]
'''

    def _generate_go_mod(self, request: CodegenRequest) -> str:
        """Generate go.mod content."""
        return f'''module {request.group.lower()}

go 1.21

require (
	k8s.io/api v0.28.0
	k8s.io/apimachinery v0.28.0
	k8s.io/client-go v0.28.0
	sigs.k8s.io/controller-runtime v0.16.0
)
'''

    def _map_type_to_go(self, json_type: str) -> str:
        """Map JSON type to Go type."""
        type_map = {
            "string": "string",
            "integer": "int32",
            "number": "float64",
            "boolean": "bool",
            "array": "[]string",
            "object": "map[string]interface{}"
        }
        return type_map.get(json_type, "string")

def generate_crd_yaml(request) -> tuple:
    """Generate Kubernetes CRD + instance YAML from a CodegenRequest.
    
    Returns: (crd_yaml, instance_yaml, combined_yaml)
    """
    crd_dict = {
        "apiVersion": "apiextensions.k8s.io/v1",
        "kind": "CustomResourceDefinition",
        "metadata": {
            "name": f"{request.kind.lower()}s.{request.group}",
        },
        "spec": {
            "group": request.group,
            "versions": [{
                "name": request.version,
                "served": True,
                "storage": True,
                "schema": {
                    "openAPIV3Schema": {
                        "type": "object",
                        "properties": {
                            "apiVersion": {"type": "string"},
                            "kind": {"type": "string"},
                            "metadata": {"type": "object"},
                            "spec": {"type": "object", "properties": {}},
                        }
                    }
                }
            }],
            "names": {
                "kind": request.kind,
                "plural": f"{request.kind.lower()}s",
                "singular": request.kind.lower()
            },
            "scope": "Namespaced"
        }
    }

    # Add spec properties
    for field_name, field_info in request.spec_properties.items():
        field_type = field_info.get("type", "string") if isinstance(field_info, dict) else field_info
        field_desc = field_info.get("description", f"Description for {field_name}")
        property_schema = {"type": field_type, "description": field_desc}
        if field_type == "array":
            property_schema["items"] = {"type": "string"}
        elif field_type == "object":
            property_schema["additionalProperties"] = {"type": "string"}
        crd_dict["spec"]["versions"][0]["schema"]["openAPIV3Schema"]["properties"]["spec"]["properties"][field_name] = property_schema

    # Generate sample instance
    sample_spec = {}
    for field_name, field_info in request.spec_properties.items():
        field_type = field_info.get("type", "string") if isinstance(field_info, dict) else field_info
        if field_type == "string":
            sample_spec[field_name] = "example-value"
        elif field_type == "integer":
            sample_spec[field_name] = 3
        elif field_type == "boolean":
            sample_spec[field_name] = True
        elif field_type == "array":
            sample_spec[field_name] = ["item1", "item2"]
        elif field_type == "object":
            sample_spec[field_name] = {"key": "value"}
        else:
            sample_spec[field_name] = "example-value"

    instance_dict = {
        "apiVersion": f"{request.group}/{request.version}",
        "kind": request.kind,
        "metadata": {"name": f"my-{request.kind.lower()}-instance", "namespace": "default"},
        "spec": sample_spec
    }

    crd_yaml = yaml.dump(crd_dict, default_flow_style=False, sort_keys=False)
    instance_yaml = yaml.dump(instance_dict, default_flow_style=False, sort_keys=False)
    combined_yaml = crd_yaml + "---
" + instance_yaml
    return crd_yaml, instance_yaml, combined_yaml
