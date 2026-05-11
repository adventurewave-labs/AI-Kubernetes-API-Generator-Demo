"""``IntentInterpretationService`` — application service for Phase 3.

Realises the contract from
``docs/ddd/bounded-contexts/01-intent-interpretation.md`` §5 and §10.
The service composes:

* a :class:`~ai_platform_generator.ports.LlmProvider` port (any concrete
  adapter — live, fake, demo);
* a ``RequestValidator`` and a ``RequestEnhancer`` (Agent E's domain
  services — imported lazily so this module remains importable while
  Wave 2 is in progress);
* an event bus / sink (the Wave 1 :class:`RecordingSink` is the
  canonical test double);
* a :class:`~ai_platform_generator.ports.Clock` for deterministic
  timestamps in tests.

Demo-mode fallback is *not* implemented in this service: per ADR-0009
the orchestrator engages demo mode by *swapping the LLM adapter*, not
by branching here. We therefore only retry on ``LlmRateLimited`` and
otherwise re-raise — letting the orchestrator decide.
"""

from __future__ import annotations

import json
import time
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_platform_generator.domain.errors import (
    DomainValidationError,
    FieldViolation,
    LlmRateLimited,
)
from ai_platform_generator.domain.events import (
    CodegenRequestParsed,
    CodegenRequestRejected,
    IntentSubmitted,
    LlmInvocationFailed,
    LlmInvocationStarted,
    LlmInvocationSucceeded,
)
from ai_platform_generator.domain.values import (
    GVK,
    Group,
    Kind,
    OutputPath,
    PropertyConstraints,
    PropertyType,
    ProviderMode,
    SpecProperty,
    Version,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_platform_generator.domain.aggregates import CodegenRequest
    from ai_platform_generator.domain.values import Intent, RunId
    from ai_platform_generator.ports import Clock, LlmProvider, TelemetrySink


#: Maximum number of retries on :class:`LlmRateLimited` before giving up.
_MAX_RATE_LIMIT_RETRIES = 3
#: Exponential-backoff delays in seconds, indexed by retry attempt.
_RATE_LIMIT_BACKOFFS_S: tuple[float, ...] = (2.0, 4.0, 8.0)


def _load_system_prompt() -> str:
    """Load the v1 intent-interpretation system prompt as a string.

    Falls back to a minimal embedded copy if the resource can't be found
    (e.g. when running outside an installed wheel) — keeps the service
    operational while still emitting an inferable prompt for tests.
    """
    try:
        return (
            resources.files("ai_platform_generator.prompts.v1")
            .joinpath("intent_interpretation.txt")
            .read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ModuleNotFoundError, AttributeError):  # pragma: no cover
        return (
            "You are a Kubernetes API designer. Reply with a single JSON "
            "object containing keys: group, version, kind, spec_properties, "
            "output_dir, description."
        )


class IntentInterpretationService:
    """Translate a raw :class:`Intent` into a validated ``CodegenRequest``."""

    def __init__(
        self,
        llm: LlmProvider,
        validator: Any,  # domain.services.RequestValidator (Agent E)
        enhancer: Any,  # domain.services.RequestEnhancer  (Agent E)
        events: TelemetrySink,
        clock: Clock,
        *,
        allow_demo_mode: bool = True,
        sleep: Any = time.sleep,
    ) -> None:
        self._llm = llm
        self._validator = validator
        self._enhancer = enhancer
        self._events = events
        self._clock = clock
        self._allow_demo_mode = allow_demo_mode
        # Indirected for testability: tests pass a no-op ``sleep``.
        self._sleep = sleep
        self._system_prompt = _load_system_prompt()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def parse(
        self, intent: Intent, *, run_id: RunId | None = None
    ) -> CodegenRequest:
        """Parse ``intent`` into a validated ``CodegenRequest``.

        See ``docs/ddd/bounded-contexts/01-intent-interpretation.md`` §5.
        """
        self._events.emit(
            IntentSubmitted.make(
                run_id=run_id,
                payload={
                    "intent_text_hash": intent.text_hash(),
                    "intent_length": len(intent.text),
                },
            )
        )

        response = self._invoke_llm_with_retry(intent, run_id=run_id)
        request = self._build_request(response)

        self._events.emit(
            CodegenRequestParsed.make(
                run_id=run_id,
                payload={
                    "gvk": {
                        "group": request.gvk.group.value,
                        "version": request.gvk.version.value,
                        "kind": request.gvk.kind.value,
                    },
                    "property_count": len(request.spec_properties),
                    "provider_mode": request.provider_mode.value,
                },
            )
        )

        violations = self.validate(request)
        if violations:
            self._events.emit(
                CodegenRequestRejected.make(
                    run_id=run_id,
                    payload={
                        "violations": [
                            {
                                "path": v.path,
                                "expected": v.expected,
                                "actual": v.actual,
                                "message": v.message,
                            }
                            for v in violations
                        ]
                    },
                )
            )
            raise DomainValidationError(
                "CodegenRequest rejected by validator",
                field_violations=list(violations),
            )

        return self.enhance(request)

    def validate(self, request: CodegenRequest) -> list[FieldViolation]:
        """Run the configured ``RequestValidator``.

        Tolerates an absent validator (``None``) — Agent E's service has
        not yet landed; in that case there are zero violations and the
        caller proceeds.
        """
        if self._validator is None:
            return []
        result = self._validator.validate(request)
        return list(result or [])

    def enhance(self, request: CodegenRequest) -> CodegenRequest:
        """Run the configured ``RequestEnhancer`` (passthrough if absent)."""
        if self._enhancer is None:
            return request
        enhanced: CodegenRequest = self._enhancer.enhance(request)
        return enhanced

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _invoke_llm_with_retry(
        self, intent: Intent, *, run_id: RunId | None
    ) -> dict[str, Any]:
        """Call the LLM with exponential backoff on ``LlmRateLimited``."""
        provider_payload = {
            "provider": getattr(self._llm, "name", "unknown"),
            "model": getattr(self._llm, "model", "unknown"),
            "mode": _provider_mode_value(self._llm),
        }
        attempts = 0
        last_exc: Exception | None = None
        while attempts <= _MAX_RATE_LIMIT_RETRIES:
            self._events.emit(
                LlmInvocationStarted.make(run_id=run_id, payload=provider_payload)
            )
            started = self._clock.monotonic()
            try:
                raw = self._llm.complete_json(
                    self._system_prompt,
                    intent.text,
                )
            except LlmRateLimited as exc:
                last_exc = exc
                self._events.emit(
                    LlmInvocationFailed.make(
                        run_id=run_id,
                        payload={
                            **provider_payload,
                            "error_code": exc.code,
                            "recoverable": True,
                        },
                    )
                )
                if attempts >= _MAX_RATE_LIMIT_RETRIES:
                    raise
                self._sleep(_RATE_LIMIT_BACKOFFS_S[attempts])
                attempts += 1
                continue
            except Exception as exc:
                self._events.emit(
                    LlmInvocationFailed.make(
                        run_id=run_id,
                        payload={
                            **provider_payload,
                            "error_code": getattr(exc, "code", type(exc).__name__),
                            "recoverable": getattr(exc, "recoverable", False),
                        },
                    )
                )
                raise
            else:
                latency_ms = int((self._clock.monotonic() - started) * 1000)
                self._events.emit(
                    LlmInvocationSucceeded.make(
                        run_id=run_id,
                        payload={
                            **provider_payload,
                            "latency_ms": latency_ms,
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                        },
                    )
                )
                return _coerce_to_dict(raw)
        # Defensive: should be unreachable because the loop either returns
        # or raises. Keep it so type-checkers know the function terminates.
        assert last_exc is not None  # pragma: no cover
        raise last_exc  # pragma: no cover

    def _build_request(self, data: dict[str, Any]) -> CodegenRequest:
        """Hand-rolled factory: raw LLM JSON → ``CodegenRequest``.

        Handles the legacy Wave-0 prototype shape where ``spec_properties``
        was a ``dict[str, str | dict]`` (string values were just the
        type). The factory normalises that into the
        ``{"type": value}`` form expected by ``SpecProperty``.
        """
        # Imported here to keep the module importable while Agent E lands
        # the aggregate alias chain in ``domain.aggregates``.
        from ai_platform_generator.domain.aggregates.codegen_request import (
            CodegenRequest as _CodegenRequest,
        )

        try:
            gvk = GVK(
                group=Group(str(data["group"])),
                version=Version(str(data["version"])),
                kind=Kind(str(data["kind"])),
            )
        except KeyError as exc:
            raise DomainValidationError(
                f"LLM response missing required GVK key: {exc}",
            ) from exc

        spec_props_raw = data.get("spec_properties") or {}
        if not isinstance(spec_props_raw, dict):
            raise DomainValidationError(
                "LLM response 'spec_properties' must be an object"
            )
        spec_properties = tuple(
            _spec_property_from_legacy(name, value)
            for name, value in spec_props_raw.items()
        )

        output_dir = data.get("output_dir") or f"generated_specs/{gvk.kind.value.lower()}"
        output_path = OutputPath(
            root=Path.cwd().resolve(),
            relative=Path(str(output_dir)),
        )

        description = str(
            data.get("description") or f"Auto-generated description for {gvk.kind.value}."
        )

        return _CodegenRequest(
            gvk=gvk,
            spec_properties=spec_properties,
            output_path=output_path,
            description=description,
            provider_mode=_provider_mode_for(self._llm),
        )


# ---------------------------------------------------------------------------
# Helpers (module-private)
# ---------------------------------------------------------------------------


def _coerce_to_dict(raw: Any) -> dict[str, Any]:
    """Coerce an :class:`LlmProvider` response into a plain ``dict``."""
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        return dict(json.loads(raw))
    if hasattr(raw, "items"):
        return {str(k): v for k, v in raw.items()}
    raise DomainValidationError(
        f"LLM response was not a JSON object (got {type(raw).__name__})"
    )


def _spec_property_from_legacy(name: str, value: Any) -> SpecProperty:
    """Translate a legacy ``str`` value into the modern object form."""
    if isinstance(value, str):
        body: dict[str, Any] = {"type": value}
    elif isinstance(value, dict):
        body = dict(value)
    else:
        raise DomainValidationError(
            f"spec_properties[{name!r}] must be a string or object, got {type(value).__name__}"
        )

    raw_type = str(body.get("type", "string"))
    try:
        prop_type = PropertyType(raw_type)
    except ValueError as exc:
        raise DomainValidationError(
            f"spec_properties[{name!r}] has unsupported type {raw_type!r}"
        ) from exc

    description = str(
        body.get("description") or f"Specification for {name}."
    )

    item_type: PropertyType | None = None
    if prop_type is PropertyType.ARRAY:
        raw_item = str(body.get("item_type", "string"))
        try:
            item_type = PropertyType(raw_item)
        except ValueError as exc:
            raise DomainValidationError(
                f"spec_properties[{name!r}].item_type {raw_item!r} is not a supported type"
            ) from exc

    constraints = PropertyConstraints(
        minimum=body.get("minimum"),
        maximum=body.get("maximum"),
        min_length=body.get("min_length") or body.get("minLength"),
        max_length=body.get("max_length") or body.get("maxLength"),
        pattern=body.get("pattern"),
        enum=tuple(body["enum"]) if isinstance(body.get("enum"), (list, tuple)) else None,
        format=body.get("format"),
    )

    return SpecProperty(
        name=name,
        type=prop_type,
        description=description,
        constraints=constraints,
        item_type=item_type,
    )


def _provider_mode_for(llm: LlmProvider) -> ProviderMode:
    """Return a :class:`ProviderMode` for the wired provider, defaulting to LIVE."""
    mode = getattr(llm, "mode", None)
    if isinstance(mode, ProviderMode):
        return mode
    if isinstance(mode, str):
        try:
            return ProviderMode(mode)
        except ValueError:
            return ProviderMode.LIVE
    return ProviderMode.LIVE


def _provider_mode_value(llm: LlmProvider) -> str:
    """Return the wire-form (``"live"`` / ``"demo"``) of the provider mode."""
    return _provider_mode_for(llm).value
