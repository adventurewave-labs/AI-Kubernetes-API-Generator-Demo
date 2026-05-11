"""Security lock-in tests for the Go controller scaffold.

These assertions encode the hardening posture documented in
``docs/security/go-scaffold-review.md`` and ADR-0020 §"Generated-artefact
hardening". A regression in any of the templates that loosens one of
these guarantees will fail this module.

The tests deliberately re-derive the artefact set from the canonical
``PostgresCluster`` demo scenario rather than reading the golden files
on disk, so that the security contract is verified on freshly rendered
output (not stale fixtures).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ai_platform_generator.adapters.llm.demo_catalog import DemoCatalog
from ai_platform_generator.domain.aggregates import (
    CodegenRequest,
    OpenAPIDocument,
)
from ai_platform_generator.domain.generation.generators.go_controller import (
    GoControllerGenerator,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rendered_files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Render the six-file scaffold for the canonical PostgresCluster scenario.

    Returns
    -------
    dict[str, str]
        Map from the file's basename (e.g. ``"Dockerfile"``,
        ``"main.go"``, ``"postgrescluster_controller.go"``,
        ``"go.mod"``) to its UTF-8 decoded payload.
    """
    scenario = next(
        s for s in DemoCatalog().scenarios if s.name == "postgres-cluster"
    )
    req = CodegenRequest.from_dict(scenario.request)
    ir = OpenAPIDocument.from_request(req)
    tmp = tmp_path_factory.mktemp("go-scaffold-security")
    artefacts = GoControllerGenerator().generate(ir, tmp)
    return {Path(a.path).name: a.payload.decode("utf-8") for a in artefacts}


# ---------------------------------------------------------------------------
# Dockerfile assertions
# ---------------------------------------------------------------------------


def test_dockerfile_uses_distroless_static_nonroot(
    rendered_files: dict[str, str],
) -> None:
    """ADR-0020 §"Generated-artefact hardening": distroless static, non-root."""
    dockerfile = rendered_files["Dockerfile"]
    assert "FROM gcr.io/distroless/static:nonroot" in dockerfile, (
        "Dockerfile runtime stage must be distroless/static:nonroot"
    )
    assert "USER 65532:65532" in dockerfile, (
        "Dockerfile must explicitly set USER 65532:65532 (the upstream "
        "'nonroot' UID), even though distroless:nonroot defaults to it — "
        "explicit is better than implicit for security review."
    )


def test_dockerfile_is_multistage_with_copy_from_builder(
    rendered_files: dict[str, str],
) -> None:
    """The builder toolchain must not ship in the runtime image."""
    dockerfile = rendered_files["Dockerfile"]
    assert "AS builder" in dockerfile
    assert "COPY --from=builder" in dockerfile


def test_dockerfile_has_no_shell_or_package_manager(
    rendered_files: dict[str, str],
) -> None:
    """No apt/apk/yum, no ``RUN sh``, no ``USER root``."""
    dockerfile = rendered_files["Dockerfile"]
    forbidden = (
        "apt-get",
        "apk add",
        "yum install",
        "dnf install",
        "RUN sh ",
        "RUN /bin/sh",
        "USER root",
        "USER 0",
        "USER 0:0",
    )
    for needle in forbidden:
        assert needle not in dockerfile, (
            f"Dockerfile contains forbidden token {needle!r}; the runtime "
            f"image must remain distroless and the user must remain non-root"
        )


def test_dockerfile_build_uses_readonly_modules_and_trimpath(
    rendered_files: dict[str, str],
) -> None:
    """Supply-chain + information-disclosure hardening."""
    dockerfile = rendered_files["Dockerfile"]
    assert "-mod=readonly" in dockerfile, (
        "go build must use -mod=readonly so the build cannot silently "
        "mutate go.mod/go.sum"
    )
    assert "-trimpath" in dockerfile, (
        "go build must use -trimpath to strip absolute filesystem paths "
        "from the binary"
    )


def test_dockerfile_has_no_inline_secret_args(
    rendered_files: dict[str, str],
) -> None:
    """No build-arg-passed secrets baked into the image."""
    dockerfile = rendered_files["Dockerfile"]
    # Reject ARG/ENV declarations whose name looks secret-shaped.
    suspicious = re.compile(
        r"^(?:ARG|ENV)\s+\S*"
        r"(?:PASSWORD|SECRET|TOKEN|API[_-]?KEY|PRIVATE[_-]?KEY)",
        re.IGNORECASE | re.MULTILINE,
    )
    assert suspicious.search(dockerfile) is None, (
        "Dockerfile must not declare secret-shaped ARG/ENV entries; "
        "controllers read secrets from Kubernetes Secret objects at runtime"
    )


# ---------------------------------------------------------------------------
# Controller (.go) assertions
# ---------------------------------------------------------------------------


def _controller_source(rendered_files: dict[str, str]) -> str:
    return rendered_files["postgrescluster_controller.go"]


def test_controller_does_not_import_dangerous_packages(
    rendered_files: dict[str, str],
) -> None:
    """A reconciler stub has no business with ``os/exec``/``syscall``/``unsafe``."""
    src = _controller_source(rendered_files)
    for forbidden in ('"os/exec"', '"syscall"', '"unsafe"'):
        assert forbidden not in src, (
            f"controller.go imports {forbidden}; that surface should not "
            f"appear in a CRD reconciler"
        )


def test_controller_rbac_markers_have_explicit_verbs(
    rendered_files: dict[str, str],
) -> None:
    """No ``*`` verbs, no ``*`` group, no ``*`` resource."""
    src = _controller_source(rendered_files)
    rbac_lines = [
        line for line in src.splitlines() if "+kubebuilder:rbac:" in line
    ]
    assert rbac_lines, "controller.go should declare at least one RBAC marker"
    rbac_re = re.compile(
        r"\+kubebuilder:rbac:groups=(?P<groups>[^,]+),"
        r"resources=(?P<resources>[^,]+),"
        r"verbs=(?P<verbs>\S+)"
    )
    for line in rbac_lines:
        match = rbac_re.search(line)
        assert match is not None, f"unparseable RBAC marker: {line!r}"
        for field in ("groups", "resources", "verbs"):
            value = match.group(field)
            assert "*" not in value, (
                f"RBAC marker contains a wildcard in {field}: {line!r}"
            )
            for verb in value.split(";"):
                assert verb.strip(), (
                    f"empty verb in RBAC marker: {line!r}"
                )


# ---------------------------------------------------------------------------
# main.go assertions
# ---------------------------------------------------------------------------


def test_main_go_defaults_zap_to_production_mode(
    rendered_files: dict[str, str],
) -> None:
    """Verbose dev-mode logs must be opt-in, not the default."""
    main_go = rendered_files["main.go"]
    assert "Development: false" in main_go, (
        "main.go must default zap.Options{Development: false} so reconciled "
        "object contents are not stamped into stdout without operator intent"
    )
    assert "Development: true" not in main_go, (
        "main.go must not hard-code Development: true; operators opt in via "
        "the --zap-devel flag instead"
    )


# ---------------------------------------------------------------------------
# go.mod assertions
# ---------------------------------------------------------------------------


_REQUIRE_RE = re.compile(
    r"^\s*(?P<path>[^\s]+)\s+(?P<version>v\S+)\s*$",
    re.MULTILINE,
)
_PSEUDO_VERSION_RE = re.compile(r"^v0\.0\.0-")


def test_go_mod_pins_every_dependency(
    rendered_files: dict[str, str],
) -> None:
    """No floating refs (``master``, ``latest``); no pseudo-versions."""
    go_mod = rendered_files["go.mod"]
    # Extract the body of the require ( ... ) block.
    match = re.search(r"require\s*\(\s*(?P<body>.+?)\)", go_mod, re.DOTALL)
    assert match is not None, "go.mod is missing a require ( ... ) block"

    body = match.group("body")
    requires = list(_REQUIRE_RE.finditer(body))
    assert requires, "require block has no entries"

    forbidden_versions = {"master", "main", "latest", "HEAD"}
    for entry in requires:
        version = entry.group("version")
        path = entry.group("path")
        assert version not in forbidden_versions, (
            f"go.mod entry {path!r} pinned to floating ref {version!r}"
        )
        assert not _PSEUDO_VERSION_RE.match(version), (
            f"go.mod entry {path!r} uses a pseudo-version {version!r}; "
            f"pin to a tagged release instead"
        )
        # Basic shape: vMAJOR.MINOR.PATCH (allow optional -suffix).
        assert re.match(r"^v\d+\.\d+\.\d+(?:[-+]\S+)?$", version), (
            f"go.mod entry {path!r} has malformed version {version!r}"
        )
