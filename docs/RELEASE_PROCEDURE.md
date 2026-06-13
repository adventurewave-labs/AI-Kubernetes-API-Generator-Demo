# Release Procedure — Reusable Runbook

> **Audience:** the engineer cutting any future release of
> `ai-platform-generator` — v1.1, v2.0, patch releases, anything.
> Read top to bottom; check each box before moving on.

The procedure assumes [Semantic Versioning](https://semver.org/) and
[Keep a Changelog](https://keepachangelog.com/) and the architecture
documented under `docs/adr/` and `docs/ddd/`. None of the steps are CI-only —
every gate can be run locally first.

---

## 0. Roles and prerequisites

- **Release captain** — one person owns the release end-to-end.
- **Reviewer** — at least one other maintainer signs off on the PR.
- **Tools on PATH:** `git`, `gh` (or `git push` + GitHub web UI), `python ≥ 3.11`,
  `pip`, `make`, `ruff`, `mypy`, `pytest`, `python -m build`.
  *(Optional)* `kind`, `docker`, `cosign`, `syft` for the e2e + signing tier.
- **Authority:** push permission to `main`; permission to tag and publish a GitHub
  Release; PyPI trusted-publishing wiring on the repo.

Pick a **`VERSION`** for this release (e.g. `1.1.0` for a minor, `1.0.1` for a
patch). The rest of this runbook references it as `<VERSION>` — substitute
your value when you copy commands.

---

## 1. Pre-release checklist

Run through these **before** you cut a release branch:

- [ ] **Issue triage.** No P0/P1 issues open against the milestone for this
      release. Anything not done is moved to the next milestone.
- [ ] **CHANGELOG `[Unreleased]` is up to date.** Every user-facing change since
      the last tag is recorded under the appropriate section
      (Added / Changed / Deprecated / Removed / Fixed / Security / Performance).
      Wording follows the existing style; ADR / DDD cross-references are present.
- [ ] **Docs reflect reality.** README quickstart works on a clean checkout.
      `docs/use-case-guide.md` still describes the current CLI surface.
      Any new commands or flags are documented.
- [ ] **ADR coverage.** Any architectural change in this release has an
      Accepted ADR (or a superseding one). Status board in `docs/adr/README.md`
      is current.
- [ ] **`pyproject.toml` metadata** is correct: keywords, classifiers, URLs,
      dependency ranges. Run `pip check` against a fresh install.
- [ ] **License + NOTICE.** `LICENSE` present and unchanged or intentionally
      changed. `NOTICE` (if any) updated.
- [ ] **Security review.** Generated-artefact security review
      (`docs/security/go-scaffold-review.md`) is current for any new
      generator or hardening change.
- [ ] **Version bump location confirmed.** The version source is
      `src/ai_platform_generator/__init__.py` (`__version__ = "..."`).
      `pyproject.toml` uses `[tool.hatch.version] path = "..."` and reads
      from it — **do not** hand-edit `pyproject.toml`'s version.

---

## 2. Cut the release branch

```bash
git checkout main
git pull --ff-only origin main
git checkout -b release/v<VERSION>
```

Do **not** push yet — there is more to do on this branch.

---

## 3. Bump the version

```bash
# 1. Bump src/ai_platform_generator/__init__.py
$EDITOR src/ai_platform_generator/__init__.py
# change: __version__ = "<VERSION>"

# 2. Verify the CLI reports the new version
python -m ai_platform_generator.adapters.cli.main --version
# -> ai-platform-generator, version <VERSION>
```

- [ ] CLI prints `<VERSION>`.

---

## 4. Promote CHANGELOG `[Unreleased]` → `[<VERSION>]`

In `CHANGELOG.md`:

- Replace the `## [Unreleased]` heading with `## [<VERSION>] - YYYY-MM-DD`.
- Add a fresh empty `## [Unreleased]` block above it.
- Update the link references at the bottom of the file:

  ```
  [Unreleased]: https://github.com/marcuspat/AI-Kubernetes-API-Generator-Demo/compare/v<VERSION>...HEAD
  [<VERSION>]:  https://github.com/marcuspat/AI-Kubernetes-API-Generator-Demo/compare/v<PREVIOUS>...v<VERSION>
  ```

- [ ] `git diff CHANGELOG.md` shows only the promotion + a new empty
      `[Unreleased]` + updated link refs.

---

## 5. Write release notes

Update / create `RELEASE_NOTES.md` for `<VERSION>`. Required sections:

1. **Headline** (one paragraph, punchy, 4–6 sentences).
2. **What's included** — feature/capability table.
3. **Installation / quickstart** — pip, source, container.
4. **Breaking changes** — explicit, even if empty (`"None."`).
5. **Acknowledgements**.
6. **Upgrade path** — migration steps if any.
7. **Verifying this release** — wheel checksum, cosign, manifest verification.

For a patch release, keep it short; for a major release, fold in any
deprecation timeline.

- [ ] `RELEASE_NOTES.md` updated.

---

## 6. Validation gates (run locally — every one must pass)

Run in this order; **do not** skip on a green CI. The local run protects
against environment drift.

```bash
# Clean state
rm -rf dist/ build/ .pytest_cache .ruff_cache .mypy_cache

# Fresh install in a clean env (use a venv in real life)
pip install -e ".[dev]"
```

### 6.1 Lint
```bash
ruff check src/ tests/
# Expect: All checks passed!
```

### 6.2 Strict typing
```bash
mypy src/ai_platform_generator/ --strict
# Expect: Success: no issues found in N source files
```

### 6.3 Unit + golden tests
```bash
python -m pytest tests/unit/ tests/golden/ -q
# Expect: all passed; only environment-gated skips (otel, go vet)
```

### 6.4 Offline e2e
```bash
python -m pytest tests/e2e/ -q -m e2e_no_cluster
# Expect: all passed
```

### 6.5 Performance budgets
```bash
python -m pytest tests/performance/ --benchmark-sort=mean
# Expect: all benchmarks within their documented budget
```

### 6.6 (If kind+docker available) Cluster e2e
```bash
python -m pytest tests/e2e/ -q
# Expect: all passed; no skips beyond e2e_no_cluster
```

### 6.7 Smoke-test the CLI surface
```bash
python -m ai_platform_generator.adapters.cli.main --version
python -m ai_platform_generator.adapters.cli.main examples
python -m ai_platform_generator.adapters.cli.main --llm-provider=demo --no-deploy \
  --output-dir /tmp/release-smoke generate "postgres"
find /tmp/release-smoke -type f | sort
# Expect: exit 0; 14 files; manifest.json present
```

### 6.8 Build the distributions
```bash
python -m build --no-isolation
ls dist/
# Expect:
#   ai_platform_generator-<VERSION>-py3-none-any.whl
#   ai_platform_generator-<VERSION>.tar.gz
```

### 6.9 Refresh the validation report
```bash
$EDITOR docs/VALIDATION_REPORT.md   # update Date / Version / commit SHA + captured outputs
```

- [ ] `docs/VALIDATION_REPORT.md` reflects this release's gate output.
- [ ] All gates in §6 passed.

---

## 7. Open the release PR

```bash
git add -A
git commit -m "release: v<VERSION>

- bump __version__ to <VERSION>
- promote CHANGELOG [Unreleased] → [<VERSION>]
- refresh RELEASE_NOTES.md and docs/VALIDATION_REPORT.md
- (any other release-only changes)"

git push -u origin release/v<VERSION>

gh pr create \
  --base main \
  --title "Release v<VERSION>" \
  --body-file RELEASE_NOTES.md
```

Request review from at least one other maintainer. Block merge until:

- [ ] All CI checks green.
- [ ] At least one reviewer approves.
- [ ] PR description references the validation report and the CHANGELOG diff.

---

## 8. Tag and merge

After approval:

```bash
# Squash or merge per project convention
gh pr merge release/v<VERSION> --merge --delete-branch

git checkout main
git pull --ff-only origin main

# Tag the merge commit
git tag -a v<VERSION> -m "Release v<VERSION>"
git push origin v<VERSION>
```

The tag push triggers `.github/workflows/release.yml`, which:

1. Builds the wheel + sdist on Python 3.11 and 3.12.
2. Publishes to PyPI via trusted publishing.
3. Builds the multi-arch container image (`linux/amd64`, `linux/arm64`).
4. Signs the image with cosign.
5. Generates the CycloneDX SBOM and attaches it to the release.
6. Creates the GitHub Release using `RELEASE_NOTES.md`.

- [ ] Tag pushed.
- [ ] Release workflow green.
- [ ] PyPI shows the new version.
- [ ] GHCR shows the new image.
- [ ] GitHub Release page lists the wheel, sdist, and SBOM.

---

## 9. Post-release verification

From a **clean, fresh checkout** (or any machine, not the build host):

```bash
# 1. Install from PyPI
pip install ai-platform-generator==<VERSION>
ai-platform-generator --version
# -> ai-platform-generator, version <VERSION>

# 2. Run the offline smoke test
ai-platform-generator --llm-provider=demo --no-deploy \
  --output-dir /tmp/post-release generate "postgres"
test -f /tmp/post-release/postgrescluster.crd.yaml || echo "MISSING CRD"
test -f /tmp/post-release/manifest.json           || echo "MISSING MANIFEST"

# 3. Verify the wheel checksum matches the GitHub Release attachment
sha256sum "$(pip show -f ai-platform-generator | awk '/Location/{loc=$2}/RECORD/{print loc"/"$1}')"

# 4. (If container) verify cosign signature
cosign verify ghcr.io/marcuspat/ai-kubernetes-api-generator-demo:v<VERSION> \
  --certificate-identity-regexp '.*' --certificate-oidc-issuer-regexp '.*'

# 5. (If container) pull and exercise the image
docker run --rm ghcr.io/marcuspat/ai-kubernetes-api-generator-demo:v<VERSION> --version
```

- [ ] PyPI install + smoke test exit 0.
- [ ] Wheel checksum matches the release attachment.
- [ ] (If container) cosign verification passes.
- [ ] (If container) `docker run … --version` prints `<VERSION>`.

---

## 10. Communicate

- [ ] Post the release link in the team chat with a one-liner summary
      (lifted from the headline in `RELEASE_NOTES.md`).
- [ ] Close the milestone for `<VERSION>` on GitHub.
- [ ] Open the next milestone (`v<NEXT>`).
- [ ] (Major / minor only) Update any external docs site / landing page.

---

## 11. If something goes wrong

| Symptom | Action |
|---|---|
| Tag pushed but release workflow failed mid-flight | Re-run the failed job; do not delete the tag unless artifacts are corrupted. |
| Wheel uploaded with a bug | **Yank** the broken version on PyPI; cut a `<VERSION>+1` patch with the fix. Never re-publish under the same version. |
| Container image signature missing | Re-trigger the signing job; do not delete the image. |
| CHANGELOG entry forgot a change | Add it in the next patch release's `[Unreleased]` with a "(missed in v<VERSION>)" note. |
| `pip install` resolves to an older version | Verify PyPI metadata; check that `requires-python` and classifiers allow the user's interpreter. |
| `git revert` needed | Revert through a new PR (`release/revert-v<VERSION>`); never force-push `main`. Publish a `<VERSION>.post1` or `<VERSION>+1` with the revert. |

---

## 12. Patch release shortcut

For a patch release (`x.y.Z+1`):

1. Branch from the existing tag, not `main`:
   `git checkout -b release/v<VERSION> v<PREVIOUS>`
2. Cherry-pick the fix commits.
3. Run §3 (version bump), §4 (CHANGELOG), §5 (release notes), §6 (gates),
   §7 (PR), §8 (tag + merge), §9 (verify), §10 (communicate).
4. After the patch release, forward-port the CHANGELOG entry to `main`'s
   `[Unreleased]` so it isn't lost.

---

## Appendix — Definition of "Done" for a release

A release is **done** when:

1. The tag exists on `main` and on GitHub.
2. PyPI, GHCR, and the GitHub Releases page all show the new version.
3. Cosign + SBOM artifacts are attached.
4. A fresh `pip install ai-platform-generator==<VERSION>` followed by the
   offline smoke test exits 0 from a machine other than the build host.
5. The CHANGELOG, README, RELEASE_NOTES, and VALIDATION_REPORT all reflect
   the released version.
6. The team channel announcement is posted and the milestone is closed.

Anything less means the release is in progress — keep working through this
runbook until every box is ticked.
