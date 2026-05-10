"""Metric records and the event-to-metric translation table.

Implements section 7 ("Metric catalogue") of
``docs/ddd/bounded-contexts/06-observability.md``.

The :class:`MetricsRecorder` is intentionally a thin domain helper:
it produces :class:`MetricRecord` value objects from
:class:`DomainEvent` envelopes but does not export them. Adapters
(``StructlogSink`` / ``OtelSink``) are responsible for shipping the
records to whatever backend they speak.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.events.envelope import DomainEvent
    from ai_platform_generator.ports.clock import Clock


MetricKind = Literal["counter", "histogram", "gauge"]


@dataclass(frozen=True)
class MetricRecord:
    """One observation in the metric catalogue.

    Attributes
    ----------
    name:        Stable metric name (e.g. ``"runs_total"``).
    kind:        ``"counter"``, ``"histogram"`` or ``"gauge"``.
    value:       The numeric observation. For a counter this is the
                 increment; for a histogram, the sample value; for a
                 gauge, the new absolute value.
    labels:      Frozen mapping of label name → string value.
    timestamp:   UTC, timezone-aware datetime taken from the recorder's
                 :class:`Clock` at record time.
    """

    name: str
    kind: MetricKind
    value: float
    labels: Mapping[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.fromtimestamp(0))


# ---------------------------------------------------------------------------
# Helpers used by the translation table.
# ---------------------------------------------------------------------------


def _str(value: Any, default: str = "unknown") -> str:
    """Coerce a payload value to a label string with a sane default."""
    if value is None:
        return default
    return str(value)


def _seconds(payload: Mapping[str, Any], key: str) -> float:
    """Read a duration in seconds from a payload, defaulting to ``0.0``."""
    raw = payload.get(key)
    if raw is None:
        return 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return 0.0


# Type of a translation rule: given an event payload, produce zero or
# more (name, kind, value, labels) tuples that ``MetricsRecorder.record``
# will turn into ``MetricRecord``s.
_Rule = Callable[
    ["DomainEvent"],
    "list[tuple[str, MetricKind, float, dict[str, str]]]",
]


# ---------------------------------------------------------------------------
# Translation rules — one per metric in the catalogue.
# ---------------------------------------------------------------------------


def _runs_total(outcome: str) -> _Rule:
    def rule(event: DomainEvent) -> list[tuple[str, MetricKind, float, dict[str, str]]]:
        return [
            ("runs_total", "counter", 1.0, {"outcome": outcome}),
            (
                "run_duration_seconds",
                "histogram",
                _seconds(event.payload, "duration_seconds"),
                {"outcome": outcome},
            ),
        ]

    return rule


def _stage(outcome: str) -> _Rule:
    def rule(event: DomainEvent) -> list[tuple[str, MetricKind, float, dict[str, str]]]:
        labels = {
            "stage": _str(event.payload.get("stage")),
            "outcome": outcome,
        }
        return [
            (
                "stage_duration_seconds",
                "histogram",
                _seconds(event.payload, "duration_seconds"),
                labels,
            ),
        ]

    return rule


def _llm_succeeded(event: DomainEvent) -> list[tuple[str, MetricKind, float, dict[str, str]]]:
    base_labels = {
        "provider": _str(event.payload.get("provider")),
        "model": _str(event.payload.get("model")),
        "mode": _str(event.payload.get("mode")),
        "outcome": "success",
    }
    out: list[tuple[str, MetricKind, float, dict[str, str]]] = [
        ("llm_invocations_total", "counter", 1.0, base_labels),
    ]
    prompt_tokens = event.payload.get("prompt_tokens")
    completion_tokens = event.payload.get("completion_tokens")
    if prompt_tokens is not None:
        out.append(
            (
                "llm_tokens_total",
                "counter",
                float(prompt_tokens),
                {
                    "provider": base_labels["provider"],
                    "model": base_labels["model"],
                    "direction": "prompt",
                },
            ),
        )
    if completion_tokens is not None:
        out.append(
            (
                "llm_tokens_total",
                "counter",
                float(completion_tokens),
                {
                    "provider": base_labels["provider"],
                    "model": base_labels["model"],
                    "direction": "completion",
                },
            ),
        )
    return out


def _llm_failed(event: DomainEvent) -> list[tuple[str, MetricKind, float, dict[str, str]]]:
    return [
        (
            "llm_invocations_total",
            "counter",
            1.0,
            {
                "provider": _str(event.payload.get("provider")),
                "model": _str(event.payload.get("model")),
                "mode": _str(event.payload.get("mode")),
                "outcome": "failure",
            },
        ),
    ]


def _demo_mode(event: DomainEvent) -> list[tuple[str, MetricKind, float, dict[str, str]]]:
    return [
        (
            "demo_mode_engaged_total",
            "counter",
            1.0,
            {"reason_code": _str(event.payload.get("reason_code"))},
        ),
    ]


def _artifact_generated(
    event: DomainEvent,
) -> list[tuple[str, MetricKind, float, dict[str, str]]]:
    return [
        (
            "artifact_generated_total",
            "counter",
            1.0,
            {"artefact_type": _str(event.payload.get("artefact_type"))},
        ),
    ]


def _cluster(outcome: str) -> _Rule:
    def rule(event: DomainEvent) -> list[tuple[str, MetricKind, float, dict[str, str]]]:
        labels = {
            "runtime": _str(event.payload.get("runtime")),
            "outcome": outcome,
        }
        return [
            ("cluster_creation_total", "counter", 1.0, labels),
            (
                "cluster_creation_duration_seconds",
                "histogram",
                _seconds(event.payload, "duration_seconds"),
                labels,
            ),
        ]

    return rule


def _verification(outcome: str) -> _Rule:
    def rule(event: DomainEvent) -> list[tuple[str, MetricKind, float, dict[str, str]]]:
        return [
            ("deployment_verifications_total", "counter", 1.0, {"outcome": outcome}),
        ]

    return rule


# Stable mapping from event ``name`` to its translation rule. We use
# the wire-stable string here (not the Python class) so subscribers
# need not import the full catalogue to be testable.
_EVENT_RULES: Mapping[str, _Rule] = {
    "RunSucceeded": _runs_total("success"),
    "RunFailed": _runs_total("failure"),
    "StageSucceeded": _stage("success"),
    "StageFailed": _stage("failure"),
    "LlmInvocationSucceeded": _llm_succeeded,
    "LlmInvocationFailed": _llm_failed,
    "DemoModeEngaged": _demo_mode,
    "ArtifactGenerated": _artifact_generated,
    "ClusterCreationSucceeded": _cluster("success"),
    "ClusterCreationFailed": _cluster("failure"),
    "DeploymentVerified": _verification("success"),
    "DeploymentVerificationFailed": _verification("failure"),
}


class MetricsRecorder:
    """Translate domain events into :class:`MetricRecord` value objects.

    The recorder owns no global state — there is no in-memory metric
    store on this class. Adapters that need to persist or export
    records should observe the return values of :meth:`record` /
    :meth:`from_event`.
    """

    # Re-exposed as a class-level constant so tests can introspect
    # which event names are mapped without poking at module privates.
    EVENT_RULES: Mapping[str, _Rule] = _EVENT_RULES

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    # ----- API --------------------------------------------------------

    def record(
        self,
        name: str,
        kind: MetricKind,
        value: float,
        labels: Mapping[str, str] | None = None,
    ) -> MetricRecord:
        """Construct (and return) a single :class:`MetricRecord`.

        Subscribers that want to persist or fan out the record can do
        so by treating ``record`` as the canonical factory and pulling
        the timestamp from the recorder's :class:`Clock`.
        """
        return MetricRecord(
            name=name,
            kind=kind,
            value=float(value),
            labels=dict(labels or {}),
            timestamp=self._clock.now(),
        )

    def from_event(self, event: DomainEvent) -> tuple[MetricRecord, ...]:
        """Map an event to zero or more :class:`MetricRecord`s."""
        rule = _EVENT_RULES.get(event.name)
        if rule is None:
            return ()
        return tuple(
            self.record(name, kind, value, labels)
            for name, kind, value, labels in rule(event)
        )
