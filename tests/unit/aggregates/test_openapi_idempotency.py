"""Idempotency tests for the IR builder.

The load-bearing invariant of API Modelling: the same
``CodegenRequest`` produces byte-identical IR every time. See
``docs/ddd/04-tactical-design.md`` section 8.3 and
``docs/ddd/bounded-contexts/02-api-modelling.md`` section 7.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import mkdtemp

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ai_platform_generator.domain.aggregates.codegen_request import CodegenRequest
from ai_platform_generator.domain.aggregates.openapi_document import OpenAPIDocument
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

# ---------------------------------------------------------------------------
# Hand-rolled fixture
# ---------------------------------------------------------------------------


def _request_with_two_props() -> CodegenRequest:
    return CodegenRequest(
        gvk=GVK(Group("platform.example.com"), Version("v1"), Kind("Database")),
        spec_properties=(
            SpecProperty(
                name="replicas",
                type=PropertyType.INTEGER,
                description="how many",
                constraints=PropertyConstraints(minimum=1, maximum=10),
            ),
            SpecProperty(
                name="engine",
                type=PropertyType.STRING,
                description="engine flavour",
                constraints=PropertyConstraints(enum=("postgres", "mysql")),
            ),
        ),
        output_path=OutputPath(root=Path(mkdtemp()), relative=Path("out")),
        description="Database CRD",
        provider_mode=ProviderMode.LIVE,
    )


def test_serialise_is_byte_identical_across_builds() -> None:
    req = _request_with_two_props()
    a = OpenAPIDocument.from_request(req).serialise()
    b = OpenAPIDocument.from_request(req).serialise()
    c = OpenAPIDocument.from_request(req).serialise()
    assert a == b == c


def test_serialise_invariant_to_property_input_order() -> None:
    """Reordering the input tuple should NOT change the output bytes.

    (Required because the IR sorts properties lexicographically.)
    """
    p1 = SpecProperty(
        name="alpha", type=PropertyType.STRING, description="d", constraints=PropertyConstraints()
    )
    p2 = SpecProperty(
        name="beta", type=PropertyType.STRING, description="d", constraints=PropertyConstraints()
    )
    p3 = SpecProperty(
        name="gamma", type=PropertyType.STRING, description="d", constraints=PropertyConstraints()
    )

    op = OutputPath(root=Path(mkdtemp()), relative=Path("out"))
    base = {
        "gvk": GVK(Group("platform.example.com"), Version("v1"), Kind("X")),
        "output_path": op,
        "description": "X",
        "provider_mode": ProviderMode.LIVE,
    }
    a = OpenAPIDocument.from_request(
        CodegenRequest(spec_properties=(p1, p2, p3), **base)  # type: ignore[arg-type]
    ).serialise()
    b = OpenAPIDocument.from_request(
        CodegenRequest(spec_properties=(p3, p2, p1), **base)  # type: ignore[arg-type]
    ).serialise()
    assert a == b


def test_serialise_ends_with_newline() -> None:
    req = _request_with_two_props()
    out = OpenAPIDocument.from_request(req).serialise()
    assert out.endswith(b"\n")


# ---------------------------------------------------------------------------
# Property-based test
# ---------------------------------------------------------------------------


_NAME_RE = r"[a-z][A-Za-z0-9]{0,8}"


@st.composite
def _spec_property(draw: st.DrawFn) -> SpecProperty:
    name = draw(st.from_regex(rf"^{_NAME_RE}$", fullmatch=True))
    ptype = draw(
        st.sampled_from(
            [
                PropertyType.STRING,
                PropertyType.INTEGER,
                PropertyType.NUMBER,
                PropertyType.BOOLEAN,
                PropertyType.OBJECT,
            ]
        )
    )
    description = draw(st.text(min_size=1, max_size=20).filter(lambda s: s.strip()))
    return SpecProperty(
        name=name,
        type=ptype,
        description=description.strip(),
        constraints=PropertyConstraints(),
    )


@st.composite
def _request(draw: st.DrawFn) -> CodegenRequest:
    # Unique-by-name properties.
    props_list: list[SpecProperty] = draw(
        st.lists(_spec_property(), min_size=1, max_size=4, unique_by=lambda p: p.name)
    )
    return CodegenRequest(
        gvk=GVK(Group("platform.example.com"), Version("v1"), Kind("Thing")),
        spec_properties=tuple(props_list),
        output_path=OutputPath(root=Path(mkdtemp()), relative=Path("out")),
        description="t",
        provider_mode=ProviderMode.LIVE,
    )


@given(req=_request())
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_property_byte_stable_across_builds(req: CodegenRequest) -> None:
    a = OpenAPIDocument.from_request(req).serialise()
    b = OpenAPIDocument.from_request(req).serialise()
    assert a == b
