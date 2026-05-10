# syntax=docker/dockerfile:1.7
# Multi-stage, multi-arch (linux/amd64 + linux/arm64) image for
# ai-platform-generator. Builds a wheel in a builder stage, then installs the
# wheel into a minimal runtime stage running as a non-root user.
#
# See ADR-0019 (versioning, release, packaging) and ADR-0020 (security
# threat model and hardening) for the rationale behind every layer here.

ARG PYTHON_VERSION=3.12

###############################################################################
# Stage 1: builder
###############################################################################
FROM python:${PYTHON_VERSION}-slim AS builder
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential git \
    && rm -rf /var/lib/apt/lists/*

# Copy the minimum needed to build a wheel. Templates and prompts live inside
# the src/ tree so they are picked up automatically with src/.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY tests/golden/expected ./tests/golden/expected

# Best-effort: include CHANGELOG.md if present (sdist references it).
COPY CHANGELOG.md ./CHANGELOG.md

RUN python -m pip install --no-cache-dir --upgrade pip build \
    && python -m build --wheel --outdir /dist

###############################################################################
# Stage 2: runtime
###############################################################################
FROM python:${PYTHON_VERSION}-slim AS runtime
ARG TARGETARCH

LABEL org.opencontainers.image.title="ai-platform-generator"
LABEL org.opencontainers.image.description="AI Kubernetes API Generator (DDD/hexagonal)"
LABEL org.opencontainers.image.source="https://github.com/marcuspat/AI-Kubernetes-API-Generator-Demo"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.vendor="AI Platform Generator contributors"

# ca-certificates for HTTPS to LLM providers; curl as an operability tool when
# kubectl/kind is mounted in (e.g. demo flows). No shell-exposing extras.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 65532 --gid 0 --no-create-home --shell /sbin/nologin app

COPY --from=builder /dist/*.whl /tmp/
RUN python -m pip install --no-cache-dir /tmp/*.whl \
    && rm -rf /tmp/*.whl /root/.cache

# Per ADR-0020: run as non-root, drop default shell, use explicit ENTRYPOINT.
USER 65532:0
WORKDIR /work

ENTRYPOINT ["ai-platform-generator"]
CMD ["--help"]
