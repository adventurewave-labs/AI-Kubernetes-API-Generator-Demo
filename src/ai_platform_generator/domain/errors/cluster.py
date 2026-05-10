"""Cluster-provisioning errors.

These cover the kind/kubectl path. ``PrerequisiteMissing`` from
``configuration`` is re-exported here because cluster provisioning is the
context in which it is most often re-raised (kubectl/kind not installed).
"""
from __future__ import annotations

from .base import PlatformGeneratorError
from .configuration import PrerequisiteMissing  # re-exported

__all__ = [
    "ClusterCreationTimedOut",
    "ClusterProvisioningError",
    "CrdNotEstablished",
    "DeploymentVerificationFailed",
    "KubectlInvocationFailed",
    "PrerequisiteMissing",
    "ResourceVerificationFailed",
]


class ClusterProvisioningError(PlatformGeneratorError):
    """Base class for cluster-provisioning failures."""

    code = "E_CLUSTER_GENERIC"


class ClusterCreationTimedOut(ClusterProvisioningError):
    """The cluster failed to come up within the configured timeout."""

    code = "E_CLUSTER_CREATION_TIMEOUT"


class KubectlInvocationFailed(ClusterProvisioningError):
    """A ``kubectl`` invocation exited non-zero."""

    code = "E_CLUSTER_KUBECTL_FAILED"


class ResourceVerificationFailed(ClusterProvisioningError):
    """Post-apply verification of a Kubernetes resource failed."""

    code = "E_CLUSTER_RESOURCE_VERIFICATION_FAILED"


class CrdNotEstablished(ClusterProvisioningError):
    """A CRD was applied but its ``Established`` condition never went True."""

    code = "E_CLUSTER_CRD_NOT_ESTABLISHED"


class DeploymentVerificationFailed(ClusterProvisioningError):
    """Verification of a sample-instance deployment failed."""

    code = "E_CLUSTER_DEPLOYMENT_VERIFICATION_FAILED"
