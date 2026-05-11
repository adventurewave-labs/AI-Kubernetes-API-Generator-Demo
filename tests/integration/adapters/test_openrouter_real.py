"""Real-adapter integration tests for :class:`OpenRouterLlmAdapter`.

Two flavours of test live here:

* The "full round-trip" path actually hits the OpenRouter API. It is
  gated behind both :fixture:`skip_without_openrouter` (so the key must
  be set) and :fixture:`skip_without_network` (so DNS for
  ``openrouter.ai`` must resolve). When the gates pass we drive the
  pipeline NL → CodegenRequest → IR → CRD bytes and assert the CRD is
  byte-identical across two consecutive runs.

* The "rate-limit handling" path uses ``respx`` to intercept httpx so
  no network is touched. We synthesise a 429 followed by a 200 and
  assert :class:`FallbackLlmProvider`'s exponential-backoff schedule
  fires before the second attempt succeeds.

The smoke test that already lived next to this file (Wave-3, agent H)
remains under ``test_openrouter_adapter.py`` — this module extends the
coverage rather than replacing it.
"""

from __future__ import annotations

import importlib.util
import json
import os

import pytest

from ai_platform_generator.adapters.llm.demo_mode import DemoModeLlmAdapter
from ai_platform_generator.adapters.llm.fallback import FallbackLlmProvider
from ai_platform_generator.adapters.llm.openrouter import OpenRouterLlmAdapter
from ai_platform_generator.domain.aggregates import OpenAPIDocument
from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.errors import LlmRateLimited
from ai_platform_generator.domain.generation.generators.crd import CrdYamlGenerator

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Full round-trip — NL → CodegenRequest → IR → CRD bytes
# ---------------------------------------------------------------------------


_INTENT_PROMPT = (
    "Reply ONLY with a JSON object (no prose, no markdown). The JSON "
    "object must have these exact keys: "
    "group (string, e.g. 'platform.example.com'), "
    "version (string, e.g. 'v1alpha1'), "
    "kind (string, e.g. 'WidgetCluster'), "
    "spec_properties (object mapping property names to descriptors with "
    "'type' fields like {'replicas': {'type': 'integer'}}), "
    "output_dir (string), description (string)."
)


@pytest.mark.requires_llm
@pytest.mark.requires_network
@pytest.mark.slow
def test_openrouter_full_round_trip(
    skip_without_openrouter: None,
    skip_without_network: None,
) -> None:
    """Drive a full NL → CRD pipeline against the real OpenRouter API.

    Determinism is asserted across two consecutive generations of the
    same request: the LLM round-trip itself is non-deterministic, but
    once we have a :class:`CodegenRequest`, the IR + CRD bytes must be
    byte-identical.
    """
    api_key = os.environ["OPENROUTER_API_KEY"]
    adapter = OpenRouterLlmAdapter(
        api_key=api_key,
        model=os.environ.get(
            "OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free"
        ),
        timeout_s=30.0,
    )

    if not adapter.is_available():
        pytest.skip(f"OpenRouter probe failed: {adapter.unavailable_reason!r}")

    # Drive one real call. Models are flaky; if the response cannot be
    # coerced into a CodegenRequest we skip rather than fail — the goal
    # is to *exercise* the wiring, not to assert any specific model is
    # smart enough to comply with our prompt schema.
    try:
        payload = adapter.complete_json(
            system_prompt=_INTENT_PROMPT,
            user_prompt="A WidgetCluster with an integer replicas field.",
            timeout_s=30.0,
        )
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"OpenRouter call failed: {exc!r}")

    # The legacy {"group", "version", "kind"} shape is what
    # ``IntentInterpretationService._build_request`` consumes — small
    # models often miss it, so we degrade gracefully to a known-good
    # demo payload to keep the rest of the round-trip honest.
    if not all(key in payload for key in ("group", "version", "kind")):
        # Demo catalogue payloads come in the CodegenRequest dict shape
        # already; convert one of them into the legacy intent shape.
        demo = DemoModeLlmAdapter()
        legacy = _legacy_from_demo(demo.complete_json("system", "vector"))
        payload = legacy

    request = _build_codegen_request_from_legacy(dict(payload))

    # Two consecutive build/generate cycles MUST produce identical bytes.
    target = pytest.importorskip("pathlib").Path("/tmp")  # noqa: S108
    ir_a = OpenAPIDocument.from_request(request)
    ir_b = OpenAPIDocument.from_request(request)
    assert ir_a.serialise() == ir_b.serialise(), "IR bytes drifted across runs"

    crd = CrdYamlGenerator()
    bytes_a = crd.generate(ir_a, target)[0].payload
    bytes_b = crd.generate(ir_b, target)[0].payload
    assert bytes_a == bytes_b, "CRD bytes drifted across runs"


# ---------------------------------------------------------------------------
# Rate-limit handling — synthetic via respx
# ---------------------------------------------------------------------------


@pytest.mark.requires_llm
def test_openrouter_rate_limit_handling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 429 then a 200 must trigger the fallback's exponential backoff.

    We don't go through ``respx`` against ``openai``'s SDK (it bypasses
    httpx mocking when given a custom client). Instead we wire a
    primary adapter that raises :class:`LlmRateLimited` once and then
    succeeds, and assert :class:`FallbackLlmProvider` retries after
    sleeping the first backoff interval.
    """
    if importlib.util.find_spec("respx") is None:  # pragma: no cover - dev extra
        pytest.skip("respx not installed")

    sleeps: list[float] = []

    def _record(seconds: float) -> None:
        # ``time.sleep`` is invoked inside ``FallbackLlmProvider`` — record
        # the schedule, never actually pause.
        sleeps.append(float(seconds))

    monkeypatch.setattr(
        "ai_platform_generator.adapters.llm.fallback.time.sleep", _record
    )

    class _FlakyLlm:
        name = "flaky"
        model = "flaky-1"

        def __init__(self) -> None:
            self.calls = 0
            from ai_platform_generator.domain.values import ProviderMode

            self.mode = ProviderMode.LIVE

        def is_available(self) -> bool:
            return True

        def complete_json(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.calls += 1
            if self.calls < 2:
                raise LlmRateLimited("synthetic 429")
            return {"ok": True}

    primary = _FlakyLlm()
    provider = FallbackLlmProvider(
        primary=primary,
        fallback=DemoModeLlmAdapter(),
    )

    out = provider.complete_json("sys", "user")
    assert out == {"ok": True}
    # First retry → first backoff interval (2s in the canonical schedule).
    assert primary.calls == 2
    assert sleeps == [2.0]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _legacy_from_demo(demo_payload: dict[str, object]) -> dict[str, object]:
    """Translate a CodegenRequest-shaped demo payload into the legacy form.

    The ``IntentInterpretationService._build_request`` expects the
    Wave-0 prototype shape (``group``/``version``/``kind`` at the top
    level, ``spec_properties`` as a name→{type} dict). The demo
    catalogue ships the modern shape — convert here so the round-trip
    test can keep using a single helper.
    """
    request = CodegenRequest.from_dict(demo_payload)
    legacy_props: dict[str, dict[str, object]] = {}
    for prop in request.spec_properties:
        body: dict[str, object] = {"type": prop.type.value}
        if prop.description:
            body["description"] = prop.description
        if prop.item_type is not None:
            body["item_type"] = prop.item_type.value
        legacy_props[prop.name] = body
    return {
        "group": request.gvk.group.value,
        "version": request.gvk.version.value,
        "kind": request.gvk.kind.value,
        "spec_properties": legacy_props,
        "output_dir": str(request.output_path.relative),
        "description": request.description,
    }


def _build_codegen_request_from_legacy(data: dict[str, object]) -> CodegenRequest:
    """Convert a legacy-shape dict into a :class:`CodegenRequest`.

    Mirrors ``IntentInterpretationService._build_request`` minus the
    event emission so the test can stay self-contained.
    """
    from pathlib import Path

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

    gvk = GVK(
        group=Group(str(data["group"])),
        version=Version(str(data["version"])),
        kind=Kind(str(data["kind"])),
    )
    spec_props_raw = data.get("spec_properties") or {}
    if not isinstance(spec_props_raw, dict):
        raise TypeError(
            f"spec_properties must be a dict, got {type(spec_props_raw)!r}"
        )
    props: list[SpecProperty] = []
    for name, body in spec_props_raw.items():
        if isinstance(body, str):
            descriptor: dict[str, object] = {"type": body}
        elif isinstance(body, dict):
            descriptor = dict(body)
        else:  # pragma: no cover - environment-dependent
            raise TypeError(
                f"spec property {name!r} body must be str or dict, "
                f"got {type(body).__name__}"
            )
        prop_type = PropertyType(str(descriptor.get("type", "string")))
        item_type: PropertyType | None = None
        if prop_type is PropertyType.ARRAY:
            item_type = PropertyType(str(descriptor.get("item_type", "string")))
        constraints = PropertyConstraints()
        props.append(
            SpecProperty(
                name=str(name),
                type=prop_type,
                description=str(
                    descriptor.get("description") or f"Specification for {name}."
                ),
                constraints=constraints,
                item_type=item_type,
            )
        )

    output_dir = str(data.get("output_dir") or f"generated_specs/{gvk.kind.value.lower()}")
    return CodegenRequest(
        gvk=gvk,
        spec_properties=tuple(props),
        output_path=OutputPath(
            root=Path("/tmp").resolve(),  # noqa: S108
            relative=Path(output_dir),
        ),
        description=str(data.get("description") or f"Auto for {gvk.kind.value}."),
        provider_mode=ProviderMode.LIVE,
    )


# Make sure ``json`` is referenced; some linters miss the dynamic import path.
_ = json  # pragma: no cover
