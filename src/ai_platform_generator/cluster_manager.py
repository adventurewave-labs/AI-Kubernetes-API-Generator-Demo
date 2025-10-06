"""
Kind Cluster Manager for automatic Kubernetes cluster setup and deployment.

This module provides functionality to automatically create Kind clusters,
deploy generated Kubernetes resources, and verify deployment status.
"""

import os
import subprocess
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import yaml

@dataclass
class ClusterStatus:
    """Status of the Kind cluster."""
    name: str
    exists: bool
    running: bool
    nodes: List[str]
    kubectl_accessible: bool

@dataclass
class DeploymentStatus:
    """Status of deployed resources."""
    crd_applied: bool
    instance_applied: bool
    resource_accessible: bool
    resource_name: str
    resource_status: Optional[str] = None

class KindClusterManager:
    """Manages Kind cluster operations for the AI demo."""

    def __init__(self, cluster_name: str = "ai-platform-demo"):
        """Initialize the cluster manager."""
        self.cluster_name = cluster_name
        self.kubeconfig_path = self._get_kubeconfig_path()

    def _get_kubeconfig_path(self) -> str:
        """Get the kubeconfig path for this cluster."""
        kubeconfig_dir = Path.home() / ".kube"
        kubeconfig_dir.mkdir(exist_ok=True)
        return str(kubeconfig_dir / f"config-{self.cluster_name}")

    def check_prerequisites(self) -> Tuple[bool, List[str]]:
        """Check if prerequisites are installed."""
        issues = []

        # Check if kind is installed
        try:
            result = subprocess.run(["kind", "version"],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                issues.append("Kind CLI is not installed or not in PATH")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            issues.append("Kind CLI is not installed")

        # Check if kubectl is installed
        try:
            result = subprocess.run(["kubectl", "version", "--client"],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                issues.append("kubectl is not installed or not in PATH")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            issues.append("kubectl is not installed")

        # Check if Docker is running
        try:
            result = subprocess.run(["docker", "version"],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                issues.append("Docker is not running or not accessible")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            issues.append("Docker is not installed or not running")

        return len(issues) == 0, issues

    def get_cluster_status(self) -> ClusterStatus:
        """Get the current status of the Kind cluster."""
        try:
            # Check if cluster exists
            result = subprocess.run(
                ["kind", "get", "clusters"],
                capture_output=True, text=True, timeout=10
            )

            cluster_exists = self.cluster_name in result.stdout
            cluster_running = False
            nodes = []
            kubectl_accessible = False

            if cluster_exists:
                # Check if cluster is running by trying to get nodes
                try:
                    node_result = subprocess.run(
                        ["kubectl", "get", "nodes", "--context", f"kind-{self.cluster_name}"],
                        capture_output=True, text=True, timeout=15
                    )

                    if node_result.returncode == 0:
                        cluster_running = True
                        # Parse node names
                        lines = node_result.stdout.strip().split('\n')[1:]  # Skip header
                        nodes = [line.split()[0] for line in lines if line.strip()]

                        # Test kubectl accessibility
                        test_result = subprocess.run(
                            ["kubectl", "cluster-info", "--context", f"kind-{self.cluster_name}"],
                            capture_output=True, text=True, timeout=15
                        )
                        kubectl_accessible = test_result.returncode == 0
                except subprocess.TimeoutExpired:
                    pass

            return ClusterStatus(
                name=self.cluster_name,
                exists=cluster_exists,
                running=cluster_running,
                nodes=nodes,
                kubectl_accessible=kubectl_accessible
            )

        except Exception as e:
            return ClusterStatus(
                name=self.cluster_name,
                exists=False,
                running=False,
                nodes=[],
                kubectl_accessible=False
            )

    def create_cluster(self) -> Tuple[bool, str]:
        """Create a new Kind cluster."""
        try:
            # Create Kind cluster configuration
            kind_config = {
                "kind": "Cluster",
                "apiVersion": "kind.x-k8s.io/v1alpha4",
                "nodes": [
                    {
                        "role": "control-plane",
                        "kubeadmConfigPatches": [
                            """
                            kind: InitConfiguration
                            nodeRegistration:
                                kubeletExtraArgs:
                                    node-labels: "ingress-ready=true"
                            """
                        ],
                        "extraPortMappings": [
                            {"containerPort": 80, "hostPort": 80, "protocol": "TCP"},
                            {"containerPort": 443, "hostPort": 443, "protocol": "TCP"}
                        ]
                    }
                ]
            }

            config_file = Path(f"/tmp/kind-config-{self.cluster_name}.yaml")
            with open(config_file, 'w') as f:
                yaml.dump(kind_config, f)

            # Create the cluster
            result = subprocess.run(
                ["kind", "create", "cluster",
                 "--name", self.cluster_name,
                 "--config", str(config_file),
                 "--wait", "300s"],
                capture_output=True, text=True, timeout=300
            )

            # Clean up config file
            config_file.unlink(missing_ok=True)

            if result.returncode == 0:
                return True, "Kind cluster created successfully"
            else:
                return False, f"Failed to create cluster: {result.stderr}"

        except subprocess.TimeoutExpired:
            return False, "Cluster creation timed out after 5 minutes"
        except Exception as e:
            return False, f"Error creating cluster: {str(e)}"

    def deploy_resources(self, crd_path: str, instance_path: str, resource_kind: str) -> Tuple[bool, str]:
        """Deploy generated Kubernetes resources to the cluster."""
        try:
            # Apply CRD first
            crd_result = subprocess.run(
                ["kubectl", "apply", "-f", crd_path,
                 "--context", f"kind-{self.cluster_name}"],
                capture_output=True, text=True, timeout=30
            )

            if crd_result.returncode != 0:
                return False, f"Failed to apply CRD: {crd_result.stderr}"

            # Wait a moment for CRD to be established
            time.sleep(3)

            # Apply instance
            instance_result = subprocess.run(
                ["kubectl", "apply", "-f", instance_path,
                 "--context", f"kind-{self.cluster_name}"],
                capture_output=True, text=True, timeout=30
            )

            if instance_result.returncode != 0:
                return False, f"Failed to apply instance: {instance_result.stderr}"

            return True, "Resources deployed successfully"

        except subprocess.TimeoutExpired:
            return False, "Deployment timed out"
        except Exception as e:
            return False, f"Error deploying resources: {str(e)}"

    def verify_deployment(self, resource_kind: str, instance_name: str) -> DeploymentStatus:
        """Verify that deployed resources are working."""
        try:
            # Check CRD
            crd_result = subprocess.run(
                ["kubectl", "get", "crd", f"{instance_name}s.cnoe.io",
                 "--context", f"kind-{self.cluster_name}"],
                capture_output=True, text=True, timeout=15
            )
            crd_applied = crd_result.returncode == 0

            # Check instance
            instance_result = subprocess.run(
                ["kubectl", "get", resource_kind, instance_name,
                 "--context", f"kind-{self.cluster_name}"],
                capture_output=True, text=True, timeout=15
            )
            instance_applied = instance_result.returncode == 0

            # Get resource status
            resource_status = None
            if instance_applied:
                try:
                    desc_result = subprocess.run(
                        ["kubectl", "describe", resource_kind, instance_name,
                         "--context", f"kind-{self.cluster_name}"],
                        capture_output=True, text=True, timeout=15
                    )
                    if desc_result.returncode == 0:
                        # Extract status from describe output
                        for line in desc_result.stdout.split('\n'):
                            if 'Status:' in line and not line.strip().startswith('Conditions:'):
                                resource_status = line.split('Status:')[-1].strip()
                                break
                except Exception:
                    pass

            return DeploymentStatus(
                crd_applied=crd_applied,
                instance_applied=instance_applied,
                resource_accessible=instance_applied,
                resource_name=instance_name,
                resource_status=resource_status
            )

        except Exception as e:
            return DeploymentStatus(
                crd_applied=False,
                instance_applied=False,
                resource_accessible=False,
                resource_name=instance_name,
                resource_status=f"Error: {str(e)}"
            )

    def delete_cluster(self) -> Tuple[bool, str]:
        """Delete the Kind cluster."""
        try:
            result = subprocess.run(
                ["kind", "delete", "cluster", "--name", self.cluster_name],
                capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0:
                return True, "Kind cluster deleted successfully"
            else:
                return False, f"Failed to delete cluster: {result.stderr}"

        except Exception as e:
            return False, f"Error deleting cluster: {str(e)}"

    def get_resource_info(self, resource_kind: str, instance_name: str) -> Dict:
        """Get detailed information about deployed resources."""
        info = {"crd": None, "instance": None, "events": None}

        try:
            # Get CRD info
            crd_result = subprocess.run(
                ["kubectl", "get", "crd", f"{instance_name}s.cnoe.io", "-o", "yaml",
                 "--context", f"kind-{self.cluster_name}"],
                capture_output=True, text=True, timeout=15
            )
            if crd_result.returncode == 0:
                info["crd"] = crd_result.stdout

            # Get instance info
            instance_result = subprocess.run(
                ["kubectl", "get", resource_kind, instance_name, "-o", "yaml",
                 "--context", f"kind-{self.cluster_name}"],
                capture_output=True, text=True, timeout=15
            )
            if instance_result.returncode == 0:
                info["instance"] = instance_result.stdout

            # Get events
            events_result = subprocess.run(
                ["kubectl", "get", "events", "--context", f"kind-{self.cluster_name}"],
                capture_output=True, text=True, timeout=15
            )
            if events_result.returncode == 0:
                info["events"] = events_result.stdout

        except Exception:
            pass

        return info