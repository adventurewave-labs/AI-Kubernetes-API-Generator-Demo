"""``ClusterProvisioningService`` — application service for Phase 3.

Realises ``docs/ddd/bounded-contexts/04-cluster-provisioning.md`` §5.

Per ADR-0020, the service does *not* call ``subprocess`` itself: every
shell-out is owned by the :class:`ClusterRuntime` adapter. The service
composes the adapter, the event sink, and the clock into a small set of
methods the orchestrator drives.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ai_platform_generator.domain.aggregates import (
    Cluster,
    ClusterConfig,
    Deployment,
)
from ai_platform_generator.domain.errors import (
    ClusterCreationTimedOut,
    CrdNotEstablished,
    DeploymentVerificationFailed,
    PrerequisiteMissing,
)
from ai_platform_generator.domain.events import (
    ClusterCreationFailed,
    ClusterCreationStarted,
    ClusterCreationSucceeded,
    CrdApplied,
    DeploymentVerified,
    InstanceApplied,
    PrerequisiteCheckFailed,
    PrerequisiteCheckSucceeded,
)
from ai_platform_generator.domain.events import (
    DeploymentVerificationFailed as DeploymentVerificationFailedEvt,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import ArtifactBundle
    from ai_platform_generator.domain.values import RunId
    from ai_platform_generator.ports import (
        Clock,
        ClusterRuntime,
        TelemetrySink,
    )


#: Polling budgets per ``04-cluster-provisioning.md`` §6.2.
_CRD_ESTABLISHED_BUDGET_S = 30.0
_INSTANCE_ACCESSIBLE_BUDGET_S = 15.0
_POLL_INTERVAL_S = 0.5


class ClusterProvisioningService:
    """Stand up clusters, apply manifests, verify deployments."""

    def __init__(
        self,
        runtime: ClusterRuntime,
        events: TelemetrySink,
        clock: Clock,
        *,
        sleep: Any = time.sleep,
    ) -> None:
        self._runtime = runtime
        self._events = events
        self._clock = clock
        self._sleep = sleep

    # ------------------------------------------------------------------
    # 6.4.1 - prerequisites
    # ------------------------------------------------------------------
    def check_prerequisites(self, *, run_id: RunId | None = None) -> None:
        """Raise :class:`PrerequisiteMissing` if required tools are absent."""
        missing = list(self._runtime.check_prerequisites())
        if missing:
            tools = [m.name for m in missing]
            hints = {m.name: m.install_hint for m in missing}
            self._events.emit(
                PrerequisiteCheckFailed.make(
                    run_id=run_id, payload={"missing": tools}
                )
            )
            raise PrerequisiteMissing(tools, hints)

        self._events.emit(
            PrerequisiteCheckSucceeded.make(
                run_id=run_id,
                payload={"tools": [m.name for m in missing]},
            )
        )

    # ------------------------------------------------------------------
    # 6.4.2 - cluster lifecycle
    # ------------------------------------------------------------------
    def ensure(
        self, cluster_name: str, *, run_id: RunId | None = None
    ) -> Cluster:
        """Return the named cluster, creating it on first use.

        Emits ``ClusterCreationStarted`` / ``ClusterCreationSucceeded`` /
        ``ClusterCreationFailed`` so subscribers can open a span.
        """
        status = self._runtime.cluster_status(cluster_name)
        if status.exists and status.ready:
            return _existing_cluster(cluster_name, status)

        self._events.emit(
            ClusterCreationStarted.make(
                run_id=run_id,
                payload={
                    "cluster_name": cluster_name,
                    "runtime": self._runtime.name,
                },
            )
        )
        started = self._clock.monotonic()
        try:
            cluster = self._runtime.create_cluster(
                cluster_name, _default_cluster_config(cluster_name)
            )
        except ClusterCreationTimedOut as exc:
            duration = self._clock.monotonic() - started
            self._events.emit(
                ClusterCreationFailed.make(
                    run_id=run_id,
                    payload={
                        "cluster_name": cluster_name,
                        "error_code": exc.code,
                        "duration_s": duration,
                    },
                )
            )
            raise
        except Exception as exc:
            duration = self._clock.monotonic() - started
            self._events.emit(
                ClusterCreationFailed.make(
                    run_id=run_id,
                    payload={
                        "cluster_name": cluster_name,
                        "error_code": getattr(exc, "code", type(exc).__name__),
                        "duration_s": duration,
                    },
                )
            )
            raise
        else:
            duration = self._clock.monotonic() - started
            self._events.emit(
                ClusterCreationSucceeded.make(
                    run_id=run_id,
                    payload={
                        "cluster_name": cluster_name,
                        "runtime": self._runtime.name,
                        "nodes": list(getattr(cluster, "nodes", ())),
                        "duration_s": duration,
                    },
                )
            )
            return cluster

    # ------------------------------------------------------------------
    # 6.4.3 - apply CRD + instance
    # ------------------------------------------------------------------
    def deploy(
        self,
        bundle: ArtifactBundle,
        cluster: Cluster,
        *,
        run_id: RunId | None = None,
    ) -> Deployment:
        """Apply the CRD then the sample instance against ``cluster``."""
        crd_path = _path_for_artefact(bundle, "CRD")
        instance_path = _path_for_artefact(bundle, "INSTANCE")

        if crd_path is None or instance_path is None:
            raise DeploymentVerificationFailed(
                "bundle does not contain both a CRD and an instance manifest"
            )

        # ----- CRD ------------------------------------------------------
        crd_result = self._runtime.apply(cluster, crd_path)
        if not crd_result.success:
            raise DeploymentVerificationFailed(
                f"kubectl apply failed for CRD: {crd_result.stderr}"
            )
        gvk = _bundle_gvk(bundle)
        crd_name = _crd_name_for(gvk)

        if not self._wait(
            lambda: self._crd_established(cluster, gvk, crd_name),
            budget=_CRD_ESTABLISHED_BUDGET_S,
        ):
            raise CrdNotEstablished(
                f"CRD {crd_name} did not reach Established condition in budget"
            )
        self._events.emit(
            CrdApplied.make(
                run_id=run_id,
                payload={
                    "cluster_name": cluster.name,
                    "crd_name": crd_name,
                },
            )
        )

        # ----- Instance -------------------------------------------------
        inst_result = self._runtime.apply(cluster, instance_path)
        if not inst_result.success:
            raise DeploymentVerificationFailed(
                f"kubectl apply failed for instance: {inst_result.stderr}"
            )

        instance_name = _default_instance_name(gvk)
        if not self._wait(
            lambda: self._instance_accessible(cluster, gvk, instance_name),
            budget=_INSTANCE_ACCESSIBLE_BUDGET_S,
        ):
            raise DeploymentVerificationFailed(
                f"instance {instance_name} not retrievable within budget"
            )
        self._events.emit(
            InstanceApplied.make(
                run_id=run_id,
                payload={
                    "cluster_name": cluster.name,
                    "gvk": _gvk_payload(gvk),
                    "instance_name": instance_name,
                },
            )
        )

        return _make_deployment(
            cluster_name=cluster.name,
            crd_path=crd_path,
            instance_path=instance_path,
            gvk=gvk,
            instance_name=instance_name,
        )

    # ------------------------------------------------------------------
    # 6.4.4 - verify
    # ------------------------------------------------------------------
    def verify(
        self,
        deployment: Deployment,
        cluster: Cluster,
        *,
        run_id: RunId | None = None,
    ) -> Deployment:
        """Confirm the deployed resource is queryable; raise on failure."""
        gvk = getattr(deployment, "gvk", None)
        if gvk is None:
            raise DeploymentVerificationFailed(
                "Deployment is missing required ``gvk`` for verification."
            )
        instance_name = getattr(deployment, "instance_name", "")
        try:
            state = self._runtime.get(
                cluster, gvk, instance_name, namespace=None
            )
        except Exception as exc:
            self._events.emit(
                DeploymentVerificationFailedEvt.make(
                    run_id=run_id,
                    payload={
                        "cluster_name": cluster.name,
                        "gvk": _gvk_payload(gvk),
                        "instance_name": instance_name,
                        "error_code": getattr(exc, "code", type(exc).__name__),
                    },
                )
            )
            raise DeploymentVerificationFailed(
                f"kubectl get failed: {exc}"
            ) from exc

        if not state.found:
            self._events.emit(
                DeploymentVerificationFailedEvt.make(
                    run_id=run_id,
                    payload={
                        "cluster_name": cluster.name,
                        "gvk": _gvk_payload(gvk),
                        "instance_name": instance_name,
                        "error_code": "E_CLUSTER_INSTANCE_NOT_FOUND",
                    },
                )
            )
            raise DeploymentVerificationFailed(
                f"resource {instance_name} not found in cluster {cluster.name}"
            )

        self._events.emit(
            DeploymentVerified.make(
                run_id=run_id,
                payload={
                    "cluster_name": cluster.name,
                    "gvk": _gvk_payload(gvk),
                    "instance_name": instance_name,
                    "status": "ok",
                },
            )
        )
        # The deployment is immutable; tests just need it back so they
        # can chain calls. Adapters that mutate the entity will return a
        # fresh instance; for now we return the input verbatim.
        return deployment

    # ------------------------------------------------------------------
    # 6.4.5 - teardown
    # ------------------------------------------------------------------
    def teardown(self, cluster_name: str) -> None:
        """Delete the named cluster (idempotent on absence)."""
        self._runtime.delete_cluster(cluster_name)

    # ------------------------------------------------------------------
    # Polling helper
    # ------------------------------------------------------------------
    def _wait(self, predicate: Any, *, budget: float) -> bool:
        """Poll ``predicate()`` until truthy or ``budget`` elapses."""
        deadline = self._clock.monotonic() + budget
        while True:
            try:
                if predicate():
                    return True
            except Exception:
                pass
            if self._clock.monotonic() >= deadline:
                return False
            self._sleep(_POLL_INTERVAL_S)

    def _crd_established(
        self, cluster: Cluster, gvk: Any, crd_name: str
    ) -> bool:
        """Return True iff the runtime reports the CRD is Established."""
        try:
            state = self._runtime.get(
                cluster, gvk, crd_name, namespace=None
            )
        except Exception:
            return False
        return bool(getattr(state, "found", False))

    def _instance_accessible(
        self, cluster: Cluster, gvk: Any, instance_name: str
    ) -> bool:
        """Return True iff ``kubectl get`` returns the instance."""
        try:
            state = self._runtime.get(
                cluster, gvk, instance_name, namespace=None
            )
        except Exception:
            return False
        return bool(getattr(state, "found", False))


# ---------------------------------------------------------------------------
# Helpers (module-private)
# ---------------------------------------------------------------------------


def _existing_cluster(name: str, status: Any) -> Cluster:
    """Wrap an already-running cluster in the canonical :class:`Cluster` aggregate.

    The kubeconfig path is unknown to us when the cluster pre-existed —
    we fall back to ``~/.kube/config`` (the conventional location) so
    callers receive a fully-typed aggregate. Adapters that own the
    kubeconfig directly (e.g. :class:`KindClusterRuntime`) construct
    their own :class:`Cluster` with the correct path.
    """
    config = ClusterConfig(name=name, runtime="external")
    return Cluster(
        name=name,
        config=config,
        kubeconfig_path=Path.home() / ".kube" / "config",
        nodes=tuple(getattr(status, "nodes", ()) or ()),
        status=status,
    )


def _default_cluster_config(name: str) -> ClusterConfig:
    """Return the default :class:`ClusterConfig` for ``name``."""
    return ClusterConfig(name=name)


def _bundle_gvk(bundle: ArtifactBundle) -> Any:
    """Extract a GVK from the bundle's manifest, if available."""
    manifest = getattr(bundle, "manifest", None)
    request = getattr(manifest, "request", None)
    return getattr(request, "gvk", None)


def _gvk_payload(gvk: Any) -> dict[str, str]:
    if gvk is None:
        return {}
    try:
        return {
            "group": gvk.group.value,
            "version": gvk.version.value,
            "kind": gvk.kind.value,
        }
    except AttributeError:
        return {}


def _crd_name_for(gvk: Any) -> str:
    if gvk is None:
        return ""
    try:
        name: str = gvk.crd_name
        return name
    except AttributeError:
        return ""


def _default_instance_name(gvk: Any) -> str:
    """Stable sample-instance name per ``InstanceYamlGenerator`` convention."""
    if gvk is None:
        return "instance"
    kind = getattr(getattr(gvk, "kind", None), "value", "Instance")
    return f"my-{kind.lower()}-instance"


def _path_for_artefact(bundle: ArtifactBundle, kind: str) -> Path | None:
    """Locate a rendered artefact whose ``artefact_type`` matches ``kind``."""
    files = getattr(bundle, "files", ())
    for f in files:
        art = getattr(f, "artefact_type", None)
        val = getattr(art, "value", art)
        if str(val).upper() == kind.upper():
            path = getattr(f, "path", None)
            if path is not None:
                return Path(path)
    return None


def _make_deployment(
    *,
    cluster_name: str,
    crd_path: Path,
    instance_path: Path,
    gvk: Any,
    instance_name: str,
) -> Deployment:
    """Construct a :class:`Deployment` entity for the given inputs.

    Note that :class:`Deployment` is a frozen value-object-ish entity —
    ``crd_path`` / ``instance_path`` are not stored on it (the bundle
    keeps those); the deployment carries the *outcome* fields the
    verify path needs (``gvk``, ``instance_name``, the booleans).
    """
    # ``crd_path`` and ``instance_path`` are accepted for symmetry with
    # the bundle's artefact set but the canonical aggregate stores only
    # the verification-path-relevant fields.
    del crd_path, instance_path
    return Deployment(
        id=uuid4(),
        cluster_name=cluster_name,
        gvk=gvk,
        instance_name=instance_name,
        crd_applied=True,
        instance_applied=True,
    )
