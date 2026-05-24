# Use-Case Guide — AI Kubernetes API Generator

> **Who should read this?**  Anyone evaluating whether this tool solves a
> problem they have. Read the scenario that matches your role, then follow the
> quick-start steps at the bottom of that section.

---

## What problem does this tool solve?

Creating a Kubernetes Custom Resource Definition (CRD) is tedious. You have to:

1. Write an OpenAPI 3.0 schema by hand.
2. Wrap it in the `apiextensions.k8s.io/v1` CRD envelope.
3. Write a sample instance YAML.
4. Scaffold a Go controller with the right imports, reconcile loop, and RBAC annotations.
5. Wire a kustomization overlay.
6. Keep all five files consistent with each other.

This tool collapses all five steps into one natural-language command and produces
a byte-identical, SHA-256-checksummed artifact bundle in under one second.

---

## Scenario 1 — Platform engineer defining internal APIs

**You are:** a platform engineer building an Internal Developer Platform (IDP).
Your teams need to define their own Kubernetes resources (databases, queues,
pipelines) without becoming Kubernetes API experts.

**The pain:** every new resource type requires hand-authoring a CRD and
controller scaffold. It takes days per resource; schema mistakes surface only
at apply-time.

**How this tool helps:**

```bash
# Describe what you want — no YAML required
python -m ai_platform_generator.adapters.cli.main \
  --llm-provider=demo \
  --no-deploy \
  --output-dir ./apis/redis-cluster \
  generate "Redis cluster with memoryGiB (integer 1-256), port (integer 1-65535),
            and persistence (boolean)"
```

You get:

- `rediscluster.crd.yaml` — ready for `kubectl apply` or inclusion in your GitOps repo
- `rediscluster.instance.yaml` — sample CR for documentation and testing
- `controller/` — a complete controller-runtime scaffold your Go team can extend
- `manifest.json` — SHA-256 checksums you can store in your supply-chain attestation

**Time saved:** hours → seconds per new API type.

**Next step:** `kubectl apply -k ./apis/redis-cluster/` to register the CRD in
your cluster, then give the controller scaffold to your team.

---

## Scenario 2 — Application developer consuming platform APIs

**You are:** a developer who needs to deploy a PostgreSQL cluster on your
company's platform. You know what you want (replicas, storage, backups) but
you're not sure what the CRD looks like.

**The pain:** reading hand-authored API documentation that is often outdated,
or asking the platform team to extend the CRD on your behalf.

**How this tool helps:**

```bash
# List built-in examples
python -m ai_platform_generator.adapters.cli.main examples

# Generate a postgres-cluster API offline (demo mode, no key needed)
python -m ai_platform_generator.adapters.cli.main \
  --llm-provider=demo \
  --no-deploy \
  --output-dir ./my-db \
  generate "PostgresCluster with replicas (integer 1-7), storageGiB (integer),
            backupSchedule (string), and tlsEnabled (boolean)"
```

The generated `postgrescluster.instance.yaml` is a correctly-typed sample you can
fill in and apply immediately:

```yaml
apiVersion: database.cnoe.io/v1alpha1
kind: PostgresCluster
metadata:
  name: my-postgrescluster-instance
  namespace: default
spec:
  backupSchedule: "0 2 * * *"
  replicas: 3
  storageGiB: 100
  tlsEnabled: true
```

**Next step:** modify the instance YAML and `kubectl apply -f` it against a
cluster where the CRD is already installed.

---

## Scenario 3 — DevEx / platform-tooling lead evaluating the architecture

**You are:** a technical lead assessing whether this codebase is production-ready
and extensible enough to fork or adopt.

**What to look at:**

| Concern | Where to find it |
|---|---|
| Architectural decisions | [`docs/adr/README.md`](adr/README.md) — 20 ADRs, all Accepted |
| Domain model | [`docs/ddd/README.md`](ddd/README.md) — 6 bounded contexts, full ubiquitous language |
| Type safety | `mypy --strict` clean across 128 source files (0 errors) |
| Test coverage | 1 367 unit tests, 62 golden tests, 25 benchmarks — all passing |
| Security posture | [`docs/security/go-scaffold-review.md`](security/go-scaffold-review.md) — threat model per ADR-0020 |
| Performance | IR build: ~23 µs; CRD generation: ~1.8 ms; full bundle: ~11 ms |
| Extensibility | Add a generator in 6 steps ([`docs/ddd/bounded-contexts/03-artifact-generation.md §13`](ddd/bounded-contexts/03-artifact-generation.md)) |

**How to run the full validation suite yourself:**

```bash
pip install -e ".[dev]"
python -m ruff check src/ tests/          # lint: 0 issues
python -m mypy src/ai_platform_generator/ --strict  # types: 0 errors
python -m pytest tests/unit/ tests/golden/ -q       # 1 429 passed, 1 skipped
python -m pytest tests/performance/ --benchmark-sort=mean  # 25 benchmarks
```

See the full gate log in [`docs/validation-report.md`](validation-report.md).

---

## Scenario 4 — Conference or workshop demo

**You are:** presenting Kubernetes API design, platform engineering, or AI-assisted
development at a meetup or internal workshop.

**Demo script (offline, ~2 minutes):**

```bash
# 1. Show the tool version and built-in scenarios
python -m ai_platform_generator.adapters.cli.main --version
python -m ai_platform_generator.adapters.cli.main examples

# 2. Generate a complete API from natural language (no internet required)
python -m ai_platform_generator.adapters.cli.main \
  --llm-provider=demo \
  --no-deploy \
  --output-dir /tmp/demo-api \
  --log-format tty \
  generate "Create an MLPipeline API with stages (array of strings),
            parallelism (integer 1-32), and gpuEnabled (boolean)"

# 3. Show what was generated
find /tmp/demo-api -type f | sort
cat /tmp/demo-api/mlpipeline.crd.yaml
cat /tmp/demo-api/manifest.json   # SHA-256 provenance

# 4. (Optional) Deploy to a local Kind cluster
./run.sh cluster-up
kubectl apply -k /tmp/demo-api/
kubectl get crds | grep cnoe.io
kubectl apply -f /tmp/demo-api/mlpipeline.instance.yaml
kubectl get mlpipelines.ai.platform.cnoe.io
```

**Talking points:**

- The LLM parses the description into a typed schema — no YAML written by hand.
- The output is deterministic: run it again, get the exact same bytes.
- Every file is SHA-256 checksummed in `manifest.json` for supply-chain integrity.
- The Go controller scaffold is ready to extend — it follows kubebuilder conventions.
- Demo mode works completely offline; swap in `--llm-provider=openrouter` for
  arbitrary descriptions with a live API key.

---

## Scenario 5 — CI/CD pipeline integration

**You are:** automating API scaffolding as part of a GitOps workflow.

**Pattern — generate on PR, commit artifacts:**

```bash
# In a CI job (JSON output, machine-readable)
python -m ai_platform_generator.adapters.cli.main \
  --llm-provider=openrouter \
  --no-deploy \
  --output-dir ./generated/${KIND_LOWER} \
  --log-format json \
  generate "${DESCRIPTION}" 2>&1 | tee generation-log.json

# Verify the bundle (check every SHA-256)
python -m ai_platform_generator.adapters.cli.main \
  validate ./generated/${KIND_LOWER}/manifest.json

# Commit the generated artifacts
git add generated/
git commit -m "feat: add ${KIND} API (generated)"
```

The `manifest.json` in every bundle records the tool version, git SHA, provider
mode, model, and per-file checksums — enough for SLSA Level 2 provenance today
and Level 3 with the planned cosign integration.

---

## Common questions

**Can I use my own LLM?**
Yes. Use `--llm-provider=openrouter` with any model available on OpenRouter
(set `OPENROUTER_MODEL` env var). OpenAI direct is also supported with
`--llm-provider=openai`.

**Does it work without any API key?**
Yes. `--llm-provider=demo` uses a curated offline catalogue of 8 scenarios.
It matches by keyword so descriptions like "postgres", "redis", "ml pipeline"
all resolve without a network call.

**Can I add my own generator?**
Yes. Subclass `ArtifactGenerator`, implement `_check_preconditions`, `_plan`,
and `_render`, add Jinja2 templates, and register it. Full instructions in
[`docs/ddd/bounded-contexts/03-artifact-generation.md §13`](ddd/bounded-contexts/03-artifact-generation.md).

**Is the generated Go controller production-ready?**
It is a kubebuilder-style scaffold — it compiles and reconciles, but you must
add your business logic. The security review at
[`docs/security/go-scaffold-review.md`](security/go-scaffold-review.md) covers
what was checked and what to harden before production.

**What Kubernetes version is the CRD compatible with?**
`apiextensions.k8s.io/v1` — compatible with Kubernetes 1.22 and later.
Structural schema validation is always enabled (required by v1).

---

## Decision map

| If you want to… | Start here |
|---|---|
| Try it immediately (no setup) | [Quick start — offline](#scenario-4----conference-or-workshop-demo) |
| Understand the domain model | [`docs/ddd/01-domain-vision.md`](ddd/01-domain-vision.md) |
| Read architectural decisions | [`docs/adr/README.md`](adr/README.md) |
| See all validation evidence | [`docs/validation-report.md`](validation-report.md) + [`docs/cli-validation-report.md`](cli-validation-report.md) |
| Extend with a new generator | [`docs/ddd/bounded-contexts/03-artifact-generation.md §13`](ddd/bounded-contexts/03-artifact-generation.md) |
| Integrate into CI | [Scenario 5](#scenario-5----cicd-pipeline-integration) |
| Deploy to Kind | `./run.sh demo` |
