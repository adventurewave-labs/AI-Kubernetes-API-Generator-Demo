"""Built-in catalogue for the :class:`DemoModeLlmAdapter`.

Per :doc:`../../../docs/adr/0009-graceful-degradation-to-demo-mode` and
``docs/ddd/08-implementation-roadmap.md`` §10, the system ships eight
canonical scenarios. The :class:`DemoCatalog` matches a free-text query
against per-scenario keywords (case-insensitive substring) and returns
the corresponding :class:`DemoScenario`. The ``vector-db`` scenario is
the fallback when no keywords match.

Each scenario's ``request`` payload is shaped exactly like
:meth:`CodegenRequest.to_dict` output, so it can be round-tripped via
:meth:`CodegenRequest.from_dict` without any further translation.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DemoScenario(BaseModel):
    """A single curated demo scenario.

    Attributes
    ----------
    name:
        Stable identifier (e.g. ``"postgres-cluster"``).
    keywords:
        Tuple of substrings; a query matches the scenario iff at least
        one keyword is a case-insensitive substring of the query.
    request:
        A dict shaped like :meth:`CodegenRequest.to_dict`. Frozen.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    keywords: tuple[str, ...] = Field(min_length=1)
    request: dict[str, Any]


def _build_request(
    *,
    group: str,
    version: str,
    kind: str,
    description: str,
    spec_properties: Sequence[dict[str, Any]],
    output_dir: str,
) -> dict[str, Any]:
    """Materialise a ``CodegenRequest.to_dict``-shaped payload."""
    return {
        "gvk": {"group": group, "version": version, "kind": kind},
        "spec_properties": list(spec_properties),
        "output_path": {
            "root": str(Path.cwd().resolve()),
            "relative": output_dir,
        },
        "description": description,
        "provider_mode": "demo",
    }


def _prop(
    name: str,
    type_: str,
    description: str,
    *,
    constraints: dict[str, Any] | None = None,
    item_type: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": name,
        "type": type_,
        "description": description,
        "constraints": dict(constraints or {}),
    }
    if item_type is not None:
        out["item_type"] = item_type
    return out


# ---------------------------------------------------------------------------
# Built-in scenarios (eight)
# ---------------------------------------------------------------------------

_POSTGRES_CLUSTER = DemoScenario(
    name="postgres-cluster",
    keywords=("postgres", "postgresql", "psql", "postgrescluster"),
    request=_build_request(
        group="database.cnoe.io",
        version="v1alpha1",
        kind="PostgresCluster",
        description="A managed PostgreSQL cluster with replication, TLS and scheduled backups.",
        spec_properties=[
            _prop(
                "replicas",
                "integer",
                "Number of PostgreSQL replicas in the cluster.",
                constraints={"minimum": 1, "maximum": 7},
            ),
            _prop("tlsEnabled", "boolean", "Whether TLS is enforced for client connections."),
            _prop(
                "backupSchedule",
                "string",
                "Cron expression controlling the backup schedule.",
                constraints={"pattern": r"^[\\d\\*/, -]+$"},
            ),
            _prop(
                "storageGiB",
                "integer",
                "Per-replica persistent volume size in GiB.",
                constraints={"minimum": 1, "maximum": 16384},
            ),
        ],
        output_dir="generated/postgres-cluster",
    ),
)

_REDIS_CLUSTER = DemoScenario(
    name="redis-cluster",
    keywords=("redis", "rediscluster"),
    request=_build_request(
        group="cache.cnoe.io",
        version="v1alpha1",
        kind="RedisCluster",
        description="A Redis cluster with configurable memory, port and persistence.",
        spec_properties=[
            _prop(
                "memoryGiB",
                "integer",
                "Memory budget per node, in GiB.",
                constraints={"minimum": 1, "maximum": 1024},
            ),
            _prop(
                "port",
                "integer",
                "TCP port the Redis cluster listens on.",
                constraints={"minimum": 1, "maximum": 65535},
            ),
            _prop("persistence", "boolean", "Whether AOF persistence is enabled."),
        ],
        output_dir="generated/redis-cluster",
    ),
)

_VECTOR_DB = DemoScenario(
    name="vector-db",
    keywords=("vector", "vectordb", "embedding", "embeddings"),
    request=_build_request(
        group="ai.platform.cnoe.io",
        version="v1alpha1",
        kind="VectorDB",
        description="A vector database used to store and query embeddings for AI workloads.",
        spec_properties=[
            _prop(
                "engineType",
                "string",
                "Backing vector engine.",
                constraints={"enum": ("milvus", "qdrant", "weaviate", "pinecone")},
            ),
            _prop(
                "replicas",
                "integer",
                "Number of replica pods.",
                constraints={"minimum": 1, "maximum": 10},
            ),
            _prop(
                "dimensions",
                "integer",
                "Embedding vector dimensionality.",
                constraints={"minimum": 1, "maximum": 65536},
            ),
        ],
        output_dir="generated/vector-db",
    ),
)

_NOTEBOOK = DemoScenario(
    name="notebook",
    keywords=("notebook", "jupyter"),
    request=_build_request(
        group="datascience.cnoe.io",
        version="v1alpha1",
        kind="Notebook",
        description="A Jupyter notebook environment with configurable CPU, memory and GPU.",
        spec_properties=[
            _prop("cpu", "string", "CPU request, e.g. '500m' or '2'."),
            _prop("memory", "string", "Memory request, e.g. '4Gi'."),
            _prop("gpu", "boolean", "Whether to attach a GPU to the notebook pod."),
        ],
        output_dir="generated/notebook",
    ),
)

_DATABASE_BACKUP = DemoScenario(
    name="database-backup",
    keywords=("backup", "databasebackup"),
    request=_build_request(
        group="database.cnoe.io",
        version="v1alpha1",
        kind="DatabaseBackup",
        description="A scheduled backup job for an upstream database.",
        spec_properties=[
            _prop(
                "schedule",
                "string",
                "Cron expression controlling when the backup job runs.",
            ),
            _prop(
                "retentionDays",
                "integer",
                "How long to retain backups, in days.",
                constraints={"minimum": 1, "maximum": 3650},
            ),
            _prop("enabled", "boolean", "Whether this backup schedule is active."),
        ],
        output_dir="generated/database-backup",
    ),
)

_CACHE_CLUSTER = DemoScenario(
    name="cache-cluster",
    keywords=("cache", "cachecluster"),
    request=_build_request(
        group="platform.cnoe.io",
        version="v1alpha1",
        kind="CacheCluster",
        description="A generic cache cluster with size, memory and port settings.",
        spec_properties=[
            _prop(
                "size",
                "string",
                "T-shirt size, e.g. 'small', 'medium', 'large'.",
                constraints={"enum": ("small", "medium", "large")},
            ),
            _prop("memory", "string", "Memory budget per node, e.g. '8Gi'."),
            _prop(
                "port",
                "integer",
                "TCP port the cache listens on.",
                constraints={"minimum": 1, "maximum": 65535},
            ),
        ],
        output_dir="generated/cache-cluster",
    ),
)

_MONITORING_SERVICE = DemoScenario(
    name="monitoring-service",
    keywords=("monitor", "monitoring", "monitoringservice", "observability"),
    request=_build_request(
        group="observability.cnoe.io",
        version="v1alpha1",
        kind="MonitoringService",
        description=(
            "A monitoring service that scrapes targets at a fixed interval "
            "and emits alerts."
        ),
        spec_properties=[
            _prop("interval", "string", "Scrape interval, e.g. '30s' or '1m'."),
            _prop(
                "targets",
                "array",
                "List of target hostnames or service URIs to monitor.",
                item_type="string",
            ),
            _prop(
                "alertEnabled",
                "boolean",
                "Whether alert routing is enabled for this monitor.",
            ),
        ],
        output_dir="generated/monitoring-service",
    ),
)

_ML_PIPELINE = DemoScenario(
    name="ml-pipeline",
    keywords=("pipeline", "mlpipeline", "ml ", "machine learning"),
    request=_build_request(
        group="ai.platform.cnoe.io",
        version="v1alpha1",
        kind="MLPipeline",
        description="A multi-stage machine-learning pipeline with optional GPU acceleration.",
        spec_properties=[
            _prop(
                "stages",
                "array",
                "Ordered list of pipeline stage names.",
                item_type="string",
            ),
            _prop(
                "parallelism",
                "integer",
                "Maximum number of stages to run concurrently.",
                constraints={"minimum": 1, "maximum": 64},
            ),
            _prop("gpuEnabled", "boolean", "Whether GPU-backed nodes are used."),
        ],
        output_dir="generated/ml-pipeline",
    ),
)


_DEFAULT_SCENARIOS: tuple[DemoScenario, ...] = (
    _POSTGRES_CLUSTER,
    _REDIS_CLUSTER,
    _VECTOR_DB,
    _NOTEBOOK,
    _DATABASE_BACKUP,
    _CACHE_CLUSTER,
    _MONITORING_SERVICE,
    _ML_PIPELINE,
)


_FALLBACK_NAME = "vector-db"


class DemoCatalog:
    """In-process keyword-keyed catalogue of :class:`DemoScenario`s.

    Constructed with the eight built-in scenarios by default. Tests may
    pass a custom tuple to exercise edge cases without mutating the
    module-level defaults.
    """

    def __init__(
        self,
        scenarios: Iterable[DemoScenario] | None = None,
        *,
        fallback_name: str = _FALLBACK_NAME,
    ) -> None:
        self._scenarios: tuple[DemoScenario, ...] = (
            tuple(scenarios) if scenarios is not None else _DEFAULT_SCENARIOS
        )
        if not self._scenarios:
            raise ValueError("DemoCatalog requires at least one scenario")
        # Validate uniqueness of names, since callers index by name.
        names = [s.name for s in self._scenarios]
        if len(set(names)) != len(names):
            raise ValueError(f"DemoCatalog scenario names must be unique, got {names!r}")
        try:
            self._fallback: DemoScenario = next(
                s for s in self._scenarios if s.name == fallback_name
            )
        except StopIteration as exc:
            raise ValueError(
                f"fallback scenario {fallback_name!r} is not in the provided "
                f"catalogue (have {names!r})",
            ) from exc

    @property
    def scenarios(self) -> tuple[DemoScenario, ...]:
        """Return the catalogue's scenarios in insertion order."""
        return self._scenarios

    @property
    def fallback(self) -> DemoScenario:
        """Return the scenario served when nothing matches."""
        return self._fallback

    def find(self, query: str) -> DemoScenario:
        """Return the first scenario whose keywords match ``query``.

        Matching is case-insensitive substring. If no scenario matches,
        the fallback (default ``vector-db``) is returned. The lookup is
        deterministic — scenarios are visited in catalogue order.
        """
        if not isinstance(query, str):
            return self._fallback
        haystack = query.casefold()
        for scenario in self._scenarios:
            for keyword in scenario.keywords:
                if keyword.casefold() in haystack:
                    return scenario
        return self._fallback

    def by_name(self, name: str) -> DemoScenario:
        """Return the scenario with this exact ``name``.

        Raises :class:`KeyError` if the name is not present.
        """
        for scenario in self._scenarios:
            if scenario.name == name:
                return scenario
        raise KeyError(name)


__all__ = [
    "DemoCatalog",
    "DemoScenario",
]
