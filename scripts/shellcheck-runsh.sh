#!/usr/bin/env bash
# =============================================================================
# scripts/shellcheck-runsh.sh — canonical shellcheck wrapper for run.sh
# =============================================================================
# Mirrors the Makefile ``shellcheck`` target so contributors can invoke the
# same check locally without remembering the flag set. The exclusions are
# documented inline so a future reader knows why each is suppressed.
#
#   SC2086  — word-splitting on unquoted expansions. We deliberately rely
#             on bash's IFS=$'\n\t' to keep variable expansions intact, so
#             the warning is noise.
#   SC2164  — ``cd`` failing without an explicit ``|| exit``. The script
#             runs under ``set -e`` so any failed ``cd`` aborts.
#
# Exits non-zero if shellcheck finds issues, exits 0 with a friendly note
# if shellcheck is not installed (so CI without the binary still passes).
# =============================================================================

set -Eeuo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_ROOT
readonly TARGET="${REPO_ROOT}/run.sh"

if ! command -v shellcheck >/dev/null 2>&1; then
    printf '[shellcheck-runsh] shellcheck not installed; skipping.\n' >&2
    printf '[shellcheck-runsh]   install: https://www.shellcheck.net/\n' >&2
    exit 0
fi

if [[ ! -f "${TARGET}" ]]; then
    printf '[shellcheck-runsh] %s does not exist\n' "${TARGET}" >&2
    exit 1
fi

exec shellcheck -x -e SC2086,SC2164 "${TARGET}"
