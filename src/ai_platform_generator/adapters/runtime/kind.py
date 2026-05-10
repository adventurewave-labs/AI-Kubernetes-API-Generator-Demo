"""Real ``ClusterRuntime`` adapter that drives the local ``kind`` toolchain.

This adapter shells out to ``kind``, ``kubectl`` and ``docker`` to manage a
local Kubernetes cluster. It implements the
:class:`ai_platform_generator.ports.cluster_runtime.ClusterRuntime`
Protocol so the application service is unaware of the underlying CLI.

Design points (per ADR-0006 and ADR-0020):

* All subprocesses run with ``shell=False`` and a mandatory timeout.
* The argv list is constructed from validated value objects only —
  *never* via f-string interpolation against user input. Cluster names
  containing shell metacharacters are passed verbatim as a single argv
  entry, which means the OS treats them as literal data.
* Stdout and stderr are both captured; on non-zero exit the truncated
  output is folded into the typed ``KubectlInvocationFailed.user_message``.
* ``FileNotFoundError`` from ``subprocess.run`` (the binary itself is
  missing) is translated to :class:`PrerequisiteMissing`.
* The default ``subprocess_runner`` is :func:`_run_subprocess`. Tests
  inject a fake to capture argv and return canned responses without
  touching the OS. This is the single seam used by every method.

See ``docs/ddd/bounded-contexts/04-cluster-provisioning.md`` for the
context's place in the wider architecture.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from ai_platform_generator.domain.errors import (
    ClusterCreationTimedOut,
    KubectlInvocationFailed,
    PrerequisiteMissing,
)
from ai_platform_generator.ports.cluster_runtime import (
    ApplyResult,
    ClusterEvent,
    ClusterStatus,
    MissingTool,
    ResourceDescription,
    ResourceState,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import Cluster, ClusterConfig
    from ai_platform_generator.domain.values import GVK


# Truncate captured subprocess output baked into error messages to keep
# user-facing strings reasonable. 2 KiB is plenty for a kubectl error.
_OUTPUT_TRUNCATE_BYTES = 2 * 1024


# Heuristics for "cluster not found" stderr coming back from ``kind delete
# cluster`` so we can be idempotent without parsing exit codes that are
# not stable across kind versions.
_NOT_FOUND_PATTERNS: tuple[str, ...] = (
    "no such cluster",
    "could not find a cluster",
    "no kind clusters found",
    "not found",
)


_INSTALL_HINTS: dict[str, str] = {
    "kind": (
        "Install kind: 'brew install kind' on macOS, "
        "or see https://kind.sigs.k8s.io/docs/user/quick-start/#installation"
    ),
    "kubectl": (
        "Install kubectl: 'brew install kubectl' on macOS, "
        "'apt-get install -y kubectl' on Debian/Ubuntu, "
        "or see https://kubernetes.io/docs/tasks/tools/"
    ),
    "docker": (
        "Install Docker Engine or Docker Desktop: "
        "https://docs.docker.com/get-docker/"
    ),
}


# Inline kind cluster config, rendered with the cluster name substituted
# in via a *literal* string operation (the name is never piped into a
# shell). This config matches docs/ddd/bounded-contexts/04-cluster-provisioning.md
# section 6.1.
_KIND_CONFIG_TEMPLATE = """\
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
"""


SubprocessRunner = Callable[..., "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True, slots=True)
class _RealCluster:
    """Lightweight stand-in for ``domain.aggregates.Cluster``.

    The ``Cluster`` aggregate is duck-typed across the codebase (see
    ``application/services/cluster_provisioning.py``); all this adapter
    needs is something with ``.name`` and ``.runtime``. Once a concrete
    aggregate lands, callers may pass it through unchanged.
    """

    name: str
    runtime: str
    nodes: tuple[str, ...] = ()


def _run_subprocess(
    argv: list[str],
    *,
    timeout_s: float,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with the hardening rules from ADR-0020.

    * ``shell=False`` always — argv is interpreted directly by the OS,
      never by ``/bin/sh``.
    * Every argv entry must already be a string. We refuse non-strings
      *before* invoking the kernel so a programmer error in the calling
      code cannot silently produce an injection.
    * Timeouts are mandatory — a hung kubectl must not stall the whole
      run.
    """
    if not argv:
        raise ValueError("argv must not be empty")
    for index, entry in enumerate(argv):
        if not isinstance(entry, str):
            raise ValueError(
                f"argv[{index}] must be str, got {type(entry).__name__}: {entry!r}"
            )
    return subprocess.run(
        argv,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env=dict(env) if env is not None else None,
    )


def _truncate(s: str, *, limit: int = _OUTPUT_TRUNCATE_BYTES) -> str:
    if len(s) <= limit:
        return s
    head = s[: limit - 16]
    return f"{head}…<truncated {len(s) - len(head)} bytes>"


def _is_not_found(stderr: str) -> bool:
    haystack = (stderr or "").lower()
    return any(pat in haystack for pat in _NOT_FOUND_PATTERNS)


class KindClusterRuntime:
    """``ClusterRuntime`` backed by the real ``kind`` + ``kubectl`` CLIs.

    The constructor takes everything that might vary between hosts so
    tests (and CI) can swap binaries, kubeconfig directories, timeouts,
    and crucially the ``subprocess_runner`` itself.
    """

    name: str = "kind"

    def __init__(
        self,
        *,
        kind_bin: str = "kind",
        kubectl_bin: str = "kubectl",
        docker_bin: str = "docker",
        kubeconfig_dir: Path | None = None,
        default_timeout_s: float = 30.0,
        cluster_create_timeout_s: float = 300.0,
        subprocess_runner: SubprocessRunner | None = None,
    ) -> None:
        self.kind_bin = kind_bin
        self.kubectl_bin = kubectl_bin
        self.docker_bin = docker_bin
        self.kubeconfig_dir: Path = (
            kubeconfig_dir if kubeconfig_dir is not None else Path.home() / ".kube"
        )
        self.default_timeout_s = default_timeout_s
        self.cluster_create_timeout_s = cluster_create_timeout_s
        self._run: SubprocessRunner = subprocess_runner or _run_subprocess

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _invoke(
        self,
        argv: list[str],
        *,
        timeout_s: float,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a subprocess, translating low-level failures to typed errors.

        Translation rules:

        * ``FileNotFoundError`` (binary itself missing) →
          :class:`PrerequisiteMissing`.
        * ``subprocess.TimeoutExpired`` is re-raised verbatim so callers
          can decide whether it is a "cluster create" timeout or a
          generic kubectl timeout.
        """
        try:
            return self._run(argv, timeout_s=timeout_s, env=env)
        except FileNotFoundError as exc:
            tool = argv[0] if argv else "<unknown>"
            raise PrerequisiteMissing(
                missing_tools=[tool],
                install_hint={tool: _INSTALL_HINTS.get(tool, "")},
                cause=exc,
            ) from exc

    def _kubectl_failed(
        self,
        action: str,
        result: subprocess.CompletedProcess[str],
    ) -> KubectlInvocationFailed:
        """Build a :class:`KubectlInvocationFailed` from a non-zero result.

        The error class name is generic to *all* subprocess calls in the
        runtime adapter (kind, kubectl, docker). We reuse it for kind
        invocations too.
        """
        stdout = _truncate((result.stdout or "").strip())
        stderr = _truncate((result.stderr or "").strip())
        message = (
            f"{action} failed (exit={result.returncode}). "
            f"stderr: {stderr or '<empty>'}"
        )
        if stdout:
            message = f"{message}\nstdout: {stdout}"
        return KubectlInvocationFailed(
            user_message=message,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    @staticmethod
    def _context_for(cluster_name: str) -> str:
        return f"kind-{cluster_name}"

    @staticmethod
    def _kubectl_namespace_args(namespace: str | None) -> list[str]:
        if namespace is None or namespace == "":
            return []
        return ["-n", namespace]

    # ------------------------------------------------------------------
    # ClusterRuntime protocol implementation
    # ------------------------------------------------------------------

    def check_prerequisites(self) -> list[MissingTool]:
        """Probe ``kind``, ``kubectl`` and ``docker`` and report what's missing."""
        missing: list[MissingTool] = []
        # Each tool gets a *small* probe argv. ``kubectl`` does not have
        # a plain ``version`` subcommand on newer releases that succeeds
        # without a server, so we use ``--client``.
        probes: tuple[tuple[str, list[str]], ...] = (
            (self.kind_bin, [self.kind_bin, "version"]),
            (self.kubectl_bin, [self.kubectl_bin, "version", "--client"]),
            (self.docker_bin, [self.docker_bin, "version"]),
        )
        for tool, argv in probes:
            try:
                result = self._run(argv, timeout_s=10.0)
            except FileNotFoundError:
                missing.append(self._missing_tool(tool))
                continue
            except subprocess.TimeoutExpired:
                missing.append(self._missing_tool(tool))
                continue
            if result.returncode != 0:
                missing.append(self._missing_tool(tool))
        return missing

    def _missing_tool(self, tool: str) -> MissingTool:
        return MissingTool(
            name=tool,
            expected_version_range=None,
            install_hint=_INSTALL_HINTS.get(tool, ""),
        )

    def cluster_status(self, name: str) -> ClusterStatus:
        """Snapshot the named cluster: existence, readiness, node list."""
        # 1. Ask kind whether the cluster exists at all.
        list_argv = [self.kind_bin, "get", "clusters"]
        list_result = self._invoke(list_argv, timeout_s=self.default_timeout_s)
        if list_result.returncode != 0:
            raise self._kubectl_failed("kind get clusters", list_result)

        clusters = {
            line.strip()
            for line in (list_result.stdout or "").splitlines()
            if line.strip()
        }
        if name not in clusters:
            return ClusterStatus(name=name, exists=False, ready=False, nodes=())

        ctx = self._context_for(name)
        nodes_argv = [
            self.kubectl_bin,
            "get",
            "nodes",
            "--context",
            ctx,
            "-o",
            "jsonpath={range .items[*]}{.metadata.name}{'\\n'}{end}",
        ]
        nodes_result = self._invoke(nodes_argv, timeout_s=self.default_timeout_s)
        if nodes_result.returncode != 0:
            return ClusterStatus(
                name=name,
                exists=True,
                ready=False,
                nodes=(),
                message=_truncate((nodes_result.stderr or "").strip()),
            )
        nodes = tuple(
            line.strip()
            for line in (nodes_result.stdout or "").splitlines()
            if line.strip()
        )

        # Confirm kubectl is actually connected by hitting cluster-info.
        info_argv = [
            self.kubectl_bin,
            "cluster-info",
            "--context",
            ctx,
        ]
        info_result = self._invoke(info_argv, timeout_s=self.default_timeout_s)
        ready = info_result.returncode == 0 and bool(nodes)
        return ClusterStatus(
            name=name,
            exists=True,
            ready=ready,
            nodes=nodes,
            message=None
            if ready
            else _truncate((info_result.stderr or "").strip()) or None,
        )

    def create_cluster(
        self,
        name: str,
        config: ClusterConfig,
    ) -> Cluster:
        """Create a kind cluster and return a populated ``Cluster``.

        ``config`` is accepted to satisfy the port contract but is
        currently unused — the rendered kind config is hard-coded to the
        defaults documented in
        ``docs/ddd/bounded-contexts/04-cluster-provisioning.md`` §6.1.
        Future revisions will read node count and port mappings from it.
        """
        del config  # tolerated until the ``ClusterConfig`` aggregate lands
        # Render the inline config to a real file because ``kind create
        # cluster --config`` does not accept stdin reliably across versions.
        # ``delete=False`` so we control lifetime — Windows in particular
        # cannot reopen a NamedTemporaryFile that is still open.
        config_yaml = _KIND_CONFIG_TEMPLATE
        tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115 — handled in try/finally
            mode="w",
            suffix=".yaml",
            prefix=f"kind-{name}-",
            delete=False,
        )
        try:
            tmp.write(config_yaml)
            tmp.flush()
            tmp.close()
            argv = [
                self.kind_bin,
                "create",
                "cluster",
                "--name",
                name,
                "--config",
                tmp.name,
                "--wait",
                "300s",
            ]
            try:
                result = self._invoke(
                    argv, timeout_s=self.cluster_create_timeout_s,
                )
            except subprocess.TimeoutExpired as exc:
                raise ClusterCreationTimedOut(
                    user_message=(
                        f"kind create cluster '{name}' did not finish within "
                        f"{self.cluster_create_timeout_s:.0f}s — see "
                        "'docker ps' / 'kind get clusters' for a stuck node."
                    ),
                    cluster_name=name,
                    timeout_s=self.cluster_create_timeout_s,
                    cause=exc,
                ) from exc
            # NB: KubectlInvocationFailed is the generic name for *any*
            # non-zero subprocess in this adapter, including kind itself.
            if result.returncode != 0:
                raise self._kubectl_failed(f"kind create cluster '{name}'", result)
        finally:
            with contextlib.suppress(OSError):  # best-effort cleanup
                os.unlink(tmp.name)

        status = self.cluster_status(name)
        return _RealCluster(name=name, runtime=self.name, nodes=tuple(status.nodes))

    def delete_cluster(self, name: str) -> None:
        """Delete a kind cluster, tolerating already-absent state."""
        argv = [self.kind_bin, "delete", "cluster", "--name", name]
        try:
            result = self._invoke(argv, timeout_s=60.0)
        except subprocess.TimeoutExpired as exc:
            raise ClusterCreationTimedOut(
                user_message=(
                    f"kind delete cluster '{name}' timed out after 60s. "
                    "Inspect 'docker ps' for stuck containers."
                ),
                cluster_name=name,
                timeout_s=60.0,
                cause=exc,
            ) from exc
        if result.returncode == 0:
            return
        if _is_not_found(result.stderr or ""):
            return
        raise self._kubectl_failed(f"kind delete cluster '{name}'", result)

    def apply(self, cluster: Cluster, manifest_path: Path) -> ApplyResult:
        """Apply a manifest with ``kubectl apply -f`` against ``cluster``."""
        cluster_name = str(getattr(cluster, "name", ""))
        ctx = self._context_for(cluster_name) if cluster_name else ""
        argv: list[str] = [
            self.kubectl_bin,
            "apply",
            "-f",
            str(manifest_path),
        ]
        if ctx:
            argv.extend(["--context", ctx])
        result = self._invoke(argv, timeout_s=self.default_timeout_s)
        applied = _parse_apply_stdout(result.stdout or "")
        if result.returncode != 0:
            return ApplyResult(
                success=False,
                applied=applied,
                stdout=_truncate((result.stdout or "").strip()),
                stderr=_truncate((result.stderr or "").strip()),
            )
        return ApplyResult(
            success=True,
            applied=applied,
            stdout=_truncate((result.stdout or "").strip()),
            stderr=_truncate((result.stderr or "").strip()),
        )

    def get(
        self,
        cluster: Cluster,
        gvk: GVK,
        name: str,
        namespace: str | None,
    ) -> ResourceState:
        """Read a single resource via ``kubectl get -o jsonpath``."""
        cluster_name = str(getattr(cluster, "name", ""))
        kind = str(getattr(gvk, "kind", "") or "")
        api_version = str(getattr(gvk, "api_version", "v1") or "v1")
        argv: list[str] = [
            self.kubectl_bin,
            "get",
            kind,
            name,
            "-o",
            "jsonpath={.metadata.name}{\"\\t\"}{.status}",
        ]
        argv.extend(self._kubectl_namespace_args(namespace))
        if cluster_name:
            argv.extend(["--context", self._context_for(cluster_name)])
        result = self._invoke(argv, timeout_s=15.0)
        if result.returncode != 0:
            return ResourceState(
                name=name,
                namespace=namespace,
                api_version=api_version,
                kind=kind,
                found=False,
                raw={"stderr": _truncate((result.stderr or "").strip())},
            )
        parsed_name, status_text = _parse_get_jsonpath(result.stdout or "")
        return ResourceState(
            name=parsed_name or name,
            namespace=namespace,
            api_version=api_version,
            kind=kind,
            found=True,
            raw={
                "stdout": _truncate((result.stdout or "").strip()),
                "status_text": status_text,
            },
        )

    def describe(
        self,
        cluster: Cluster,
        gvk: GVK,
        name: str,
        namespace: str | None,
    ) -> ResourceDescription:
        """Capture ``kubectl describe`` output as text."""
        cluster_name = str(getattr(cluster, "name", ""))
        kind = str(getattr(gvk, "kind", "") or "")
        argv: list[str] = [self.kubectl_bin, "describe", kind, name]
        argv.extend(self._kubectl_namespace_args(namespace))
        if cluster_name:
            argv.extend(["--context", self._context_for(cluster_name)])
        result = self._invoke(argv, timeout_s=15.0)
        if result.returncode != 0:
            raise self._kubectl_failed(
                f"kubectl describe {kind}/{name}", result,
            )
        return ResourceDescription(
            name=name,
            namespace=namespace,
            text=result.stdout or "",
        )

    def events(self, cluster: Cluster) -> list[ClusterEvent]:
        """Return cluster events parsed from ``kubectl get events -o json``."""
        cluster_name = str(getattr(cluster, "name", ""))
        argv = [self.kubectl_bin, "get", "events", "-o", "json"]
        if cluster_name:
            argv.extend(["--context", self._context_for(cluster_name)])
        result = self._invoke(argv, timeout_s=15.0)
        if result.returncode != 0:
            raise self._kubectl_failed("kubectl get events", result)
        try:
            payload: Any = json.loads(result.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise KubectlInvocationFailed(
                user_message=(
                    "kubectl get events returned non-JSON output: "
                    f"{_truncate(str(exc))}"
                ),
                cause=exc,
            ) from exc
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return [_parse_event(item) for item in items if isinstance(item, dict)]


# ----------------------------------------------------------------------
# stdout parsing helpers (free functions so tests can import them)
# ----------------------------------------------------------------------


def _parse_apply_stdout(stdout: str) -> tuple[str, ...]:
    """Parse lines like ``crd.apiextensions.k8s.io/widgets created`` into refs."""
    refs: list[str] = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        # kubectl emits "<resource> <verb>" — pull the resource ref.
        parts = line.split()
        if len(parts) >= 2 and parts[-1] in {
            "created",
            "configured",
            "unchanged",
            "deleted",
            "patched",
        }:
            refs.append(parts[0])
    return tuple(refs)


def _parse_get_jsonpath(stdout: str) -> tuple[str, str]:
    """Split ``<name>\\t<status>`` jsonpath output into (name, status_text)."""
    text = stdout or ""
    if "\t" in text:
        name, _, status = text.partition("\t")
        return name.strip(), status.strip()
    return text.strip(), ""


def _parse_event(raw: Mapping[str, Any]) -> ClusterEvent:
    """Reduce a Kubernetes Event JSON object to our :class:`ClusterEvent`."""
    metadata = raw.get("metadata") or {}
    involved = raw.get("involvedObject") or {}
    timestamp_raw = (
        raw.get("eventTime")
        or raw.get("lastTimestamp")
        or raw.get("firstTimestamp")
        or metadata.get("creationTimestamp")
    )
    timestamp = _parse_timestamp(timestamp_raw)
    return ClusterEvent(
        timestamp=timestamp,
        type=str(raw.get("type") or "Normal"),
        reason=str(raw.get("reason") or ""),
        message=str(raw.get("message") or ""),
        involved_object=str(involved.get("name") or metadata.get("name") or ""),
    )


def _parse_timestamp(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str) and raw:
        try:
            # k8s emits RFC3339 with a trailing Z that fromisoformat does
            # not handle on Python <3.11; normalise it.
            normalised = raw.replace("Z", "+00:00")
            return datetime.fromisoformat(normalised)
        except ValueError:  # pragma: no cover - tolerate weird inputs
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


# Re-exported so consumers wiring composition can refer to the duck-typed
# config without forcing the as-yet-unwritten ``ClusterConfig`` aggregate.
def default_cluster_config(name: str) -> Any:
    """Build a placeholder ``ClusterConfig`` until the aggregate lands."""
    return SimpleNamespace(name=name, runtime="kind")


__all__ = [
    "KindClusterRuntime",
    "default_cluster_config",
]
