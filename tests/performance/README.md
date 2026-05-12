# Performance benchmarks

Wave-6 micro-benchmark suite for the system's hot paths. The suite is
built on `pytest-benchmark` and is intentionally narrow: every test
exercises **one** unit (IR builder, CRD generator, artefact bundle
service, full saga) parametrised over the eight canonical scenarios
from `docs/ddd/08-implementation-roadmap.md` §10.

## Running

The suite is **not** part of the default `pytest` run (it is excluded
from `tool.pytest.ini_options.testpaths` so unit / integration / golden
runs stay fast). Invoke it directly:

```bash
# Collect-only sanity check (works without pytest-benchmark installed).
python -m pytest tests/performance --collect-only -q

# Full benchmark run.
pip install 'pytest-benchmark>=4.0'
python -m pytest tests/performance --benchmark-only
```

## Comparing runs

Save a baseline once the system is in a known-good state:

```bash
python -m pytest tests/performance --benchmark-only --benchmark-save=baseline
```

Then on a feature branch, compare against it:

```bash
python -m pytest tests/performance --benchmark-only \
    --benchmark-compare=baseline \
    --benchmark-compare-fail=mean:10%
```

The `--benchmark-compare-fail=mean:10%` flag turns a 10% mean-time
regression into a non-zero exit code — wire that into CI when the
nightly job graduates to a gate.

## Per-test budgets

| File                                      | Budget (mean) |
| ----------------------------------------- | ------------- |
| `test_ir_builder_bench.py`                | 50 ms         |
| `test_crd_generator_bench.py`             | 100 ms        |
| `test_artifact_bundle_bench.py`           | 500 ms        |
| `test_full_saga_bench.py`                 | 1.0 s         |

A test fails *immediately* if its mean exceeds the budget — the
benchmark suite is therefore both a regression detector (via
`--benchmark-compare`) and a hard ceiling.

## Cadence

These benchmarks are intended to run **nightly only**, not on every
PR. They sit outside the default `testpaths` so contributors do not
have to install `pytest-benchmark` for normal development. The
`tests/golden/` matrix already catches functional regressions; this
suite catches *performance* regressions with longer iteration counts
than a per-PR budget would tolerate.

## Baselines (Wave 8)

Measured on `2026-05-12`, baseline commit `f911d1a`, Python 3.11, dev
container. All numbers are for the `postgres-cluster` parametrisation
(the slowest scenario in every bench — the upper bound governs the
budget). `--benchmark-warmup=on --benchmark-min-rounds=20`.

### Before optimisation (commit f911d1a)

| Bench                       | mean        | stddev   | rounds |
| --------------------------- | ----------- | -------- | ------ |
| test_ir_builder_bench       | 28.82 µs    | 6.87 µs  | 39326  |
| test_crd_generator_bench    | 2175.47 µs  | 99.19 µs | 477    |
| test_artifact_bundle_bench  | 14709.30 µs | 1794.80  | 79     |
| test_full_saga_bench        | 13660.63 µs | 361.32   | 5      |

### Top 3 hotspots (cumulative time, 100 warm saga runs)

1. `go_controller.py:444 _post_process` — 0.723 s / 100 calls. The
   ``gofmt`` ``subprocess.run`` invocations dominate; one fork+exec per
   ``.go`` file × three Go files per saga. Behaviourally required.
2. `crd.py:146 _render` — 0.609 s / 100 calls. ``yaml.dump`` of the
   CRD manifest is pure-CPU YAML emission. Inherent.
3. `artifact_generation.py:163 _safe_git_sha` — 0.217 s / 100 calls.
   One ``git rev-parse HEAD`` fork+exec per saga; the SHA is stable
   for the process lifetime.

Sub-hotspot worth fixing despite a smaller absolute cost:
`openapi_document.py:184 gvk` — 0.041 s / 2 000 calls. Every generator
re-derives the GVK via ``info.model_dump(mode="json")`` + three regex
value-object constructors.

### Optimisations applied

1. **Cache `_safe_git_sha`** — `application/services/artifact_generation.py:163`.
   Wrap with `functools.cache`; the git SHA is stable for the lifetime
   of the process. Win: removes one fork+exec per saga (≈ 2 ms). Drives
   the full-saga and artifact-bundle improvements.
2. **Memoise `OpenAPIDocument.gvk`** — `domain/aggregates/openapi_document.py:183`.
   Added a private `_gvk_cache` dataclass slot (`init=False, compare=False`)
   and read the extension off `info.model_extra` instead of a full
   `model_dump(mode="json")` deep copy. The IR is frozen, so the GVK
   is invariant. Win: eliminates ~20 redundant value-object rebuilds
   per saga.
3. **(Reverted)** A `functools.cache` over `shutil.which("gofmt")` was
   prototyped, then reverted: existing post-processing tests
   monkeypatch `shutil.which` at module scope and the module-level
   cache makes those tests order-dependent. The savings were below the
   noise floor of the bench anyway, so no second-attempt was warranted.

### After optimisation (this chunk)

| Bench                       | mean        | stddev   | rounds | Δ vs before |
| --------------------------- | ----------- | -------- | ------ | ----------- |
| test_ir_builder_bench       | 29.41 µs    | 8.22 µs  | 39318  | +2.0% (noise) |
| test_crd_generator_bench    | 2109.60 µs  | 190.24   | 499    | -3.0%       |
| test_artifact_bundle_bench  | 12473.00 µs | 526.48   | 90     | -15.2%      |
| test_full_saga_bench        | 11696.48 µs | 335.99   | 5      | -14.4%      |

The IR-builder bench is within noise — its hot path never reaches the
cached helpers — while the artifact-bundle and full-saga benches both
clear the 5% bar comfortably. `mypy --strict src/ai_platform_generator/`
remains at 0 errors; the full unit suite (1367 tests) still passes.
