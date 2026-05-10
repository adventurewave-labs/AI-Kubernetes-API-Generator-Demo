"""Per-``run_id`` span stack used by OTEL-shaped telemetry sinks.

This is a deliberately tiny domain helper: it knows nothing about
OpenTelemetry — it just maintains a LIFO of opaque span identifiers
keyed by ``run_id``. Adapters (currently :class:`OtelSink`) use it to
map ``StageStarted`` / ``StageSucceeded`` events to span ``open`` /
``close`` calls without leaking the OTEL SDK into the domain.

See ``docs/ddd/bounded-contexts/06-observability.md`` §8 ("Span
structure") for the parent / child semantics this stack implements.
"""

from __future__ import annotations

from uuid import uuid4


class SpanCorrelator:
    """Track the active span identifiers for each ``run_id``.

    Every ``run_id`` gets its own LIFO stack: opening a span pushes a
    fresh UUID-string identifier; closing pops the top of the stack and
    asserts the popped id matches the one the caller is closing.

    The class is intentionally process-local and not thread-safe. The
    orchestrator drives one run at a time per :class:`SpanCorrelator`
    instance, and each run's events are published in order by the
    in-process :class:`EventBus`.
    """

    def __init__(self) -> None:
        self._stacks: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def open(self, run_id: str, span_name: str) -> str:
        """Push a new span on the ``run_id`` stack and return its id.

        ``span_name`` is accepted for parity with OTEL APIs but is not
        currently retained on the stack — adapters that need to remember
        names should keep their own side-table keyed by the returned id.
        """
        del span_name  # accepted for API parity; see docstring.
        span_id = uuid4().hex
        self._stacks.setdefault(self._key(run_id), []).append(span_id)
        return span_id

    def close(self, run_id: str, span_id: str) -> None:
        """Pop the top of ``run_id``'s stack; assert it equals ``span_id``.

        Raises :class:`AssertionError` if the stack is empty or the top
        does not match — both indicate an out-of-order span lifecycle on
        the part of the caller, which is a programming error and should
        fail loudly during development.
        """
        key = self._key(run_id)
        stack = self._stacks.get(key)
        if not stack:
            raise AssertionError(
                f"SpanCorrelator: cannot close span {span_id!r}; "
                f"stack for run_id={run_id!r} is empty",
            )
        top = stack.pop()
        if top != span_id:
            # Restore the popped id so the caller can inspect state.
            stack.append(top)
            raise AssertionError(
                f"SpanCorrelator: closing span {span_id!r} but top was {top!r}",
            )
        if not stack:
            # Don't keep empty stacks around — keeps :meth:`current`
            # simple and prevents :pyattr:`_stacks` from growing
            # without bound across long-lived processes.
            del self._stacks[key]

    def current(self, run_id: str) -> str | None:
        """Return the id at the top of ``run_id``'s stack, or ``None``."""
        stack = self._stacks.get(self._key(run_id))
        if not stack:
            return None
        return stack[-1]

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _key(run_id: str) -> str:
        # Coerce to string so callers can pass either a ``RunId`` value
        # object or a bare string without surprising lookup misses.
        return str(run_id)
