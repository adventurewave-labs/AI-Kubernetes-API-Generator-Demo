"""The :class:`DomainEvent` envelope.

All domain events share this envelope (see ``docs/ddd/05-domain-events.md``).
Events are immutable, past-tense, self-contained, and versioned.

``run_id`` is typed as ``RunId | None`` — the type is sourced from
``ai_platform_generator.domain.values``. Because this module is built in
parallel with the value-objects module, we import ``RunId`` only under
``TYPE_CHECKING`` and fall back to ``Any`` at runtime; this keeps the
envelope importable in isolation while preserving static-type fidelity once
``RunId`` lands.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.values import RunId
else:
    RunId = Any  # type: ignore[assignment,misc]


VALID_CONTEXTS: frozenset[str] = frozenset(
    {
        "intent",
        "modelling",
        "generation",
        "cluster",
        "user_interaction",
        "orchestrator",
    }
)


@dataclass(frozen=True)
class DomainEvent:
    """Immutable envelope for a single domain event.

    Attributes:
        event_id:        UUID identifying this specific event occurrence.
        run_id:          Generation Run that produced the event (``None``
                         for events that occur outside a run, e.g. a CLI
                         ``CommandStarted`` before any run is opened).
        name:            Stable event name (e.g. ``"CodegenRequestParsed"``).
        schema_version:  Numeric version of the payload shape.
        occurred_at:     UTC timestamp at which the event was raised.
        context:         Producing bounded context. Must be one of
                         :data:`VALID_CONTEXTS`.
        payload:         Arbitrary, JSON-serialisable, snake_case mapping.
        causation_id:    Event that *caused* this one, if known.
    """

    event_id: UUID
    run_id: RunId | None
    name: str
    schema_version: int
    occurred_at: datetime
    context: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    causation_id: UUID | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly ``dict`` representation of the event.

        UUIDs and datetimes are converted to strings; the payload is
        shallow-copied so callers cannot mutate the envelope's view.
        """
        return {
            "event_id": str(self.event_id),
            "run_id": None if self.run_id is None else str(self.run_id),
            "name": self.name,
            "schema_version": self.schema_version,
            "occurred_at": self.occurred_at.isoformat(),
            "context": self.context,
            "payload": dict(self.payload),
            "causation_id": (
                None if self.causation_id is None else str(self.causation_id)
            ),
        }
