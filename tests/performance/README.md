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
