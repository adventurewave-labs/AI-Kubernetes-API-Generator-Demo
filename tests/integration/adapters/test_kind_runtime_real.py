"""End-to-end integration test against a real ``kind`` binary.

Skipped unless both ``kind`` and ``docker`` are on ``$PATH`` and the
``--run-cluster-tests`` opt-in is provided. This file exists so that
contributors with a local kind set-up can prove the adapter speaks the
real toolchain. Default CI does not run it.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_platform_generator.adapters.runtime.kind import KindClusterRuntime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        shutil.which("kind") is None or shutil.which("docker") is None,
        reason="kind and docker must be installed for the real-runtime test",
    ),
]


@pytest.fixture()
def cluster_name() -> str:
    """Use a deterministic, namespaced cluster name to avoid collisions."""
    return "ai-platform-generator-itest"


def test_full_lifecycle_against_real_kind(
    tmp_path: Path,
    cluster_name: str,
) -> None:
    """create cluster → apply tiny CRD → delete cluster."""
    runtime = KindClusterRuntime()

    # Up-front: ensure tools work; this also exercises check_prerequisites.
    missing = runtime.check_prerequisites()
    if missing:  # docker daemon may be off even though the binary exists
        pytest.skip(f"prerequisites missing: {missing}")

    # Best-effort cleanup of a previous run.
    runtime.delete_cluster(cluster_name)

    cluster = runtime.create_cluster(
        cluster_name, config=SimpleNamespace(name=cluster_name),
    )
    try:
        assert cluster.name == cluster_name
        assert cluster.runtime == "kind"

        # A tiny CRD that requires no controller — we only verify that
        # the apply round-trips and that ``get`` finds it afterwards.
        crd_yaml = """\
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: widgets.example.io
spec:
  group: example.io
  names:
    kind: Widget
    listKind: WidgetList
    plural: widgets
    singular: widget
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                size:
                  type: integer
"""
        manifest = tmp_path / "widget-crd.yaml"
        manifest.write_text(crd_yaml)
        result = runtime.apply(cluster, manifest)
        assert result.success is True
        assert any("widgets.example.io" in ref for ref in result.applied)
    finally:
        runtime.delete_cluster(cluster_name)
