# syntax=docker/dockerfile:1
# Multi-stage build for the RedisCluster controller.
# Stage 1 — builder image based on the upstream Go toolchain.
FROM golang:1.22 AS builder

WORKDIR /workspace

# Cache module downloads — copy go.mod/go.sum first.
COPY go.mod go.mod
RUN go mod download

# Copy the rest of the source tree.
COPY main.go main.go
COPY api/ api/
COPY internal/ internal/

# Build a fully static binary; CGO is disabled for distroless compatibility.
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -a -o manager main.go

# Stage 2 — minimal runtime image (distroless, non-root).
FROM gcr.io/distroless/static:nonroot
WORKDIR /
COPY --from=builder /workspace/manager .
USER 65532:65532

ENTRYPOINT ["/manager"]
