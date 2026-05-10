#!/usr/bin/env bash
# =============================================================================
# AI Kubernetes API Generator — canonical demo entrypoint
# =============================================================================
# Usage: ./run.sh [demo|install|check|teardown|help] [--quiet] [--debug]
#                 [--no-deploy] [--no-install-tools]
#
# Sub-commands
#   demo       Full happy path: prerequisite check → cluster ensure →
#              generate → verify → summary. (default)
#   install    Install kubectl + kind into ~/.local/bin if absent.
#   check      Prerequisite check only; non-zero exit if anything is missing.
#   teardown   Delete the kind cluster created by `demo`.
#   help       Print this usage block.
#
# Flags
#   --quiet            Forward LOG_FORMAT=json to the CLI (machine-readable).
#   --debug            Forward --debug to the CLI (verbose tracing).
#   --no-deploy        Skip cluster ensure/deploy; pass --no-deploy to the CLI.
#   --no-install-tools Do not download kubectl/kind on `demo`/`install`.
#
# Environment
#   OPENROUTER_API_KEY   Live LLM provider key. If unset the user is offered
#                        DEMO MODE (--llm-provider=demo).
#   OFFLINE=1            Force --llm-provider=demo and skip OpenRouter.
#   LOG_FORMAT           Already-set rendering format (tty|json|quiet).
#
# Exit codes
#   Mirrors the Python CLI's stable taxonomy
#   (`docs/ddd/bounded-contexts/05-user-interaction.md` §7):
#     0   ok            10  intent      11  domain-validation
#     12  artifact      13  persistence 14  cluster
#     15  configuration 130 interrupted
# =============================================================================

set -Eeuo pipefail

# ----------------------------------------------------------------------------
# Globals & constants
# ----------------------------------------------------------------------------

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT
readonly VENV_DIR="${REPO_ROOT}/.venv"
readonly DEFAULT_CLUSTER_NAME="ai-platform-demo"
readonly DEFAULT_OUTPUT_DIR="${REPO_ROOT}/generated_specs/postgrescluster"
readonly DEFAULT_INTENT="PostgreSQL cluster API with replicas (int 1-7), tlsEnabled (bool), and backupSchedule (cron string)"
readonly KIND_VERSION="${KIND_VERSION:-v0.23.0}"
readonly LOCAL_BIN="${HOME}/.local/bin"

# Stable colour codes — auto-disabled when stdout is not a TTY.
if [[ -t 1 ]]; then
    readonly C_RED=$'\033[0;31m'
    readonly C_GREEN=$'\033[0;32m'
    readonly C_YELLOW=$'\033[1;33m'
    readonly C_CYAN=$'\033[0;36m'
    readonly C_RESET=$'\033[0m'
else
    readonly C_RED=""
    readonly C_GREEN=""
    readonly C_YELLOW=""
    readonly C_CYAN=""
    readonly C_RESET=""
fi

# Mutable flags — populated by parse_args.
SUBCOMMAND="demo"
FLAG_QUIET=0
FLAG_DEBUG=0
FLAG_NO_DEPLOY=0
FLAG_NO_INSTALL_TOOLS=0

# Step state for the error trap.
CURRENT_STEP=""
CURRENT_STEP_STDERR=""
LAST_STEP_START_MS=0

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------

log_info() { printf "%s[run.sh]%s %s\n" "${C_CYAN}" "${C_RESET}" "$*" >&2; }
log_ok()   { printf "%s[run.sh]%s %s\n" "${C_GREEN}" "${C_RESET}" "$*" >&2; }
log_warn() { printf "%s[run.sh]%s %s\n" "${C_YELLOW}" "${C_RESET}" "$*" >&2; }
log_err()  { printf "%s[run.sh]%s %s\n" "${C_RED}" "${C_RESET}" "$*" >&2; }

now_ms() {
    # Portable millisecond clock. Bash on macOS lacks %N; fall back to seconds.
    local ns
    if ns="$(date +%s%N 2>/dev/null)" && [[ "${ns}" != *N ]]; then
        printf '%s' "$(( ns / 1000000 ))"
    else
        printf '%s000' "$(date +%s)"
    fi
}

step_start() {
    CURRENT_STEP="$1"
    LAST_STEP_START_MS="$(now_ms)"
    CURRENT_STEP_STDERR=""
    printf "[run.sh] step=%s status=started elapsed=0\n" "${CURRENT_STEP}" >&2
}

step_ok() {
    local elapsed=$(( $(now_ms) - LAST_STEP_START_MS ))
    printf "[run.sh] step=%s status=ok elapsed=%d\n" "${CURRENT_STEP}" "${elapsed}" >&2
    CURRENT_STEP=""
}

step_failed() {
    local elapsed=$(( $(now_ms) - LAST_STEP_START_MS ))
    printf "[run.sh] step=%s status=failed elapsed=%d\n" "${CURRENT_STEP}" "${elapsed}" >&2
}

# ----------------------------------------------------------------------------
# Error handling
# ----------------------------------------------------------------------------

on_error() {
    local exit_code=$?
    local line_no=${1:-0}
    if [[ -n "${CURRENT_STEP}" ]]; then
        step_failed
        log_err "step '${CURRENT_STEP}' failed at line ${line_no} (exit=${exit_code})"
        if [[ -n "${CURRENT_STEP_STDERR}" ]]; then
            log_err "captured stderr:"
            printf '%s\n' "${CURRENT_STEP_STDERR}" >&2
        fi
        print_remediation "${CURRENT_STEP}"
    else
        log_err "failed at line ${line_no} (exit=${exit_code})"
    fi
    exit "${exit_code}"
}

trap 'on_error ${LINENO}' ERR
trap 'log_warn "interrupted"; exit 130' INT TERM

print_remediation() {
    local step="$1"
    case "${step}" in
        require_python|ensure_venv)
            log_warn "remediation: install Python 3.10+ and python3-venv, then re-run."
            ;;
        require_kubectl_kind|require_or_install_tools)
            log_warn "remediation: re-run with default flags (install) or install kind/kubectl manually."
            log_warn "  see https://kind.sigs.k8s.io/docs/user/quick-start/#installation"
            ;;
        require_docker)
            log_warn "remediation: start Docker Desktop or 'sudo systemctl start docker'."
            ;;
        ensure_kind_cluster)
            log_warn "remediation: 'kind delete cluster --name ${DEFAULT_CLUSTER_NAME}' then re-run."
            ;;
        run_generation)
            log_warn "remediation: re-run with --debug to capture full traceback."
            log_warn "  exit codes: 10=intent, 11=domain-validation, 12=artifact, 13=persistence,"
            log_warn "              14=cluster, 15=configuration."
            ;;
        verify_resources)
            log_warn "remediation: 'kubectl get crd,postgrescluster --context kind-${DEFAULT_CLUSTER_NAME}'."
            ;;
        *)
            log_warn "remediation: re-run with './run.sh ${SUBCOMMAND} --debug' for more detail."
            ;;
    esac
}

# ----------------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------------

usage() {
    sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

parse_args() {
    local positional=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            demo|install|check|teardown|help)
                if [[ -z "${positional}" ]]; then
                    positional="$1"
                else
                    log_err "unexpected extra sub-command: $1"
                    exit 2
                fi
                ;;
            -h|--help)
                positional="help"
                ;;
            --quiet)
                FLAG_QUIET=1
                ;;
            --debug)
                FLAG_DEBUG=1
                ;;
            --no-deploy)
                FLAG_NO_DEPLOY=1
                ;;
            --no-install-tools)
                FLAG_NO_INSTALL_TOOLS=1
                ;;
            *)
                log_err "unknown argument: $1"
                usage
                exit 2
                ;;
        esac
        shift
    done
    SUBCOMMAND="${positional:-demo}"
}

# ----------------------------------------------------------------------------
# Platform detection
# ----------------------------------------------------------------------------

detect_os()   { uname -s | tr '[:upper:]' '[:lower:]'; }
detect_arch() {
    local arch
    arch="$(uname -m)"
    case "${arch}" in
        x86_64|amd64)        printf 'amd64' ;;
        aarch64|arm64)       printf 'arm64' ;;
        *)                   printf '%s' "${arch}" ;;
    esac
}

# ----------------------------------------------------------------------------
# Prerequisite checks
# ----------------------------------------------------------------------------

require_python() {
    step_start "require_python"
    if ! command -v python3 >/dev/null 2>&1; then
        log_err "python3 not on PATH"
        return 1
    fi
    if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
        local ver
        ver="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
        log_err "Python ${ver} detected; >= 3.10 required."
        return 1
    fi
    step_ok
}

ensure_venv() {
    step_start "ensure_venv"
    if [[ ! -d "${VENV_DIR}" ]]; then
        log_info "creating virtualenv at ${VENV_DIR}"
        python3 -m venv "${VENV_DIR}"
    fi
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    if ! python -c 'import ai_platform_generator' >/dev/null 2>&1; then
        log_info "installing ai-platform-generator (editable) into venv"
        python -m pip install --quiet --upgrade pip
        python -m pip install --quiet -e "${REPO_ROOT}[dev]"
    fi
    step_ok
}

require_or_install_tools() {
    step_start "require_or_install_tools"
    if [[ "${FLAG_NO_INSTALL_TOOLS}" -eq 1 ]]; then
        local missing=()
        command -v kubectl >/dev/null 2>&1 || missing+=("kubectl")
        command -v kind    >/dev/null 2>&1 || missing+=("kind")
        if [[ ${#missing[@]} -gt 0 ]]; then
            log_err "missing tools (and --no-install-tools set): ${missing[*]}"
            return 1
        fi
        step_ok
        return 0
    fi
    install_kubectl_if_missing
    install_kind_if_missing
    step_ok
}

install_kubectl_if_missing() {
    if command -v kubectl >/dev/null 2>&1; then
        return 0
    fi
    local os arch version url
    os="$(detect_os)"
    arch="$(detect_arch)"
    log_info "installing kubectl into ${LOCAL_BIN}"
    mkdir -p "${LOCAL_BIN}"
    version="$(curl -fsSL https://dl.k8s.io/release/stable.txt)"
    url="https://dl.k8s.io/release/${version}/bin/${os}/${arch}/kubectl"
    curl -fsSL -o "${LOCAL_BIN}/kubectl" "${url}"
    chmod +x "${LOCAL_BIN}/kubectl"
    # Best-effort checksum verification — upstream publishes a sibling .sha256.
    if curl -fsSL -o "${LOCAL_BIN}/kubectl.sha256" "${url}.sha256" 2>/dev/null; then
        local expected actual
        expected="$(cat "${LOCAL_BIN}/kubectl.sha256")"
        if command -v sha256sum >/dev/null 2>&1; then
            actual="$(sha256sum "${LOCAL_BIN}/kubectl" | awk '{print $1}')"
        elif command -v shasum >/dev/null 2>&1; then
            actual="$(shasum -a 256 "${LOCAL_BIN}/kubectl" | awk '{print $1}')"
        else
            actual=""
        fi
        if [[ -n "${actual}" && "${actual}" != "${expected}" ]]; then
            rm -f "${LOCAL_BIN}/kubectl"
            log_err "kubectl checksum mismatch: expected ${expected}, got ${actual}"
            return 1
        fi
        rm -f "${LOCAL_BIN}/kubectl.sha256"
    fi
    ensure_local_bin_on_path
    log_ok "kubectl ${version} installed"
}

install_kind_if_missing() {
    if command -v kind >/dev/null 2>&1; then
        return 0
    fi
    local os arch url
    os="$(detect_os)"
    arch="$(detect_arch)"
    log_info "installing kind ${KIND_VERSION} into ${LOCAL_BIN}"
    mkdir -p "${LOCAL_BIN}"
    url="https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-${os}-${arch}"
    curl -fsSL -o "${LOCAL_BIN}/kind" "${url}"
    chmod +x "${LOCAL_BIN}/kind"
    ensure_local_bin_on_path
    log_ok "kind ${KIND_VERSION} installed"
}

ensure_local_bin_on_path() {
    case ":${PATH}:" in
        *":${LOCAL_BIN}:"*) ;;
        *) export PATH="${LOCAL_BIN}:${PATH}" ;;
    esac
}

require_docker() {
    step_start "require_docker"
    if ! command -v docker >/dev/null 2>&1; then
        log_err "docker not on PATH"
        return 1
    fi
    if ! docker info >/dev/null 2>&1; then
        log_err "docker daemon not reachable. Start Docker Desktop or 'sudo systemctl start docker'."
        return 1
    fi
    step_ok
}

# ----------------------------------------------------------------------------
# Secrets / provider mode
# ----------------------------------------------------------------------------

LLM_PROVIDER_FLAG=""

verify_secret_or_offer_demo_mode() {
    step_start "verify_secret"
    if [[ "${OFFLINE:-0}" == "1" ]]; then
        log_info "OFFLINE=1 set; selecting --llm-provider=demo"
        LLM_PROVIDER_FLAG="--llm-provider=demo"
        step_ok
        return 0
    fi
    if [[ -n "${OPENROUTER_API_KEY:-}" ]]; then
        log_ok "OPENROUTER_API_KEY found; using live provider"
        LLM_PROVIDER_FLAG=""
        step_ok
        return 0
    fi
    log_warn "no OPENROUTER_API_KEY found"
    if [[ ! -t 0 ]]; then
        log_info "non-interactive shell — defaulting to DEMO MODE"
        LLM_PROVIDER_FLAG="--llm-provider=demo"
        step_ok
        return 0
    fi
    local reply=""
    printf "%s[run.sh]%s no API key found — run in DEMO MODE? [Y/n] " \
        "${C_YELLOW}" "${C_RESET}" >&2
    read -r reply || reply=""
    case "${reply}" in
        ""|y|Y|yes|YES)
            LLM_PROVIDER_FLAG="--llm-provider=demo"
            ;;
        *)
            log_err "user declined DEMO MODE; set OPENROUTER_API_KEY and re-run"
            return 15
            ;;
    esac
    step_ok
}

# ----------------------------------------------------------------------------
# Cluster lifecycle
# ----------------------------------------------------------------------------

ensure_kind_cluster() {
    step_start "ensure_kind_cluster"
    if kind get clusters 2>/dev/null | grep -qx "${DEFAULT_CLUSTER_NAME}"; then
        log_ok "kind cluster '${DEFAULT_CLUSTER_NAME}' already exists"
    else
        log_info "creating kind cluster '${DEFAULT_CLUSTER_NAME}'"
        kind create cluster --name "${DEFAULT_CLUSTER_NAME}" --wait 120s
    fi
    kubectl --context "kind-${DEFAULT_CLUSTER_NAME}" cluster-info >/dev/null
    step_ok
}

teardown_cluster() {
    step_start "teardown_cluster"
    if ! command -v kind >/dev/null 2>&1; then
        log_warn "kind not installed; nothing to tear down"
        step_ok
        return 0
    fi
    if kind get clusters 2>/dev/null | grep -qx "${DEFAULT_CLUSTER_NAME}"; then
        kind delete cluster --name "${DEFAULT_CLUSTER_NAME}"
        log_ok "deleted kind cluster '${DEFAULT_CLUSTER_NAME}'"
    else
        log_info "no kind cluster '${DEFAULT_CLUSTER_NAME}' to delete"
    fi
    step_ok
}

# ----------------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------------

run_generation() {
    step_start "run_generation"
    local -a cli_args=()
    cli_args+=("--output-dir" "${DEFAULT_OUTPUT_DIR}")
    if [[ -n "${LLM_PROVIDER_FLAG}" ]]; then
        cli_args+=("${LLM_PROVIDER_FLAG}")
    fi
    if [[ "${FLAG_DEBUG}" -eq 1 ]]; then
        cli_args+=("--debug")
    fi
    if [[ "${FLAG_QUIET}" -eq 1 ]]; then
        cli_args+=("--log-format" "json")
    fi
    if [[ "${FLAG_NO_DEPLOY}" -eq 1 ]]; then
        cli_args+=("--no-deploy")
    fi
    cli_args+=("--cluster-name" "${DEFAULT_CLUSTER_NAME}")
    cli_args+=("generate" "${DEFAULT_INTENT}")

    log_info "invoking ai_platform_generator CLI"
    set +e
    python -m ai_platform_generator.adapters.cli.main "${cli_args[@]}"
    local rc=$?
    set -e
    if [[ ${rc} -ne 0 ]]; then
        log_err "CLI returned non-zero exit code ${rc}"
        step_failed
        CURRENT_STEP=""
        exit "${rc}"
    fi
    step_ok
}

# ----------------------------------------------------------------------------
# Post-run verification
# ----------------------------------------------------------------------------

verify_resources() {
    step_start "verify_resources"
    if [[ "${FLAG_NO_DEPLOY}" -eq 1 ]]; then
        log_info "--no-deploy set; skipping cluster verification"
        step_ok
        return 0
    fi
    local ctx="kind-${DEFAULT_CLUSTER_NAME}"
    kubectl --context "${ctx}" get crd postgresclusters.database.cnoe.io
    kubectl --context "${ctx}" get postgrescluster.database.cnoe.io my-postgrescluster-instance \
        || log_warn "instance lookup did not return a row (this may be expected on first run)"
    step_ok
}

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------

render_summary() {
    step_start "render_summary"
    local manifest="${DEFAULT_OUTPUT_DIR}/manifest.json"
    log_ok "demo complete"
    printf "\n"
    printf "%s== AI Kubernetes API Generator ==%s\n" "${C_GREEN}" "${C_RESET}"
    printf "  output directory : %s\n" "${DEFAULT_OUTPUT_DIR}"
    if [[ -f "${manifest}" ]]; then
        printf "  manifest         : %s\n" "${manifest}"
    fi
    if [[ "${FLAG_NO_DEPLOY}" -eq 0 ]]; then
        printf "  cluster context  : kind-%s\n" "${DEFAULT_CLUSTER_NAME}"
        printf "  next:  kubectl --context kind-%s get postgresclusters.database.cnoe.io\n" \
            "${DEFAULT_CLUSTER_NAME}"
    else
        printf "  cluster          : skipped (--no-deploy)\n"
    fi
    printf "\n"
    step_ok
}

# ----------------------------------------------------------------------------
# Sub-commands
# ----------------------------------------------------------------------------

cmd_check() {
    require_python
    require_or_install_tools
    require_docker
    log_ok "all prerequisites present"
}

cmd_install() {
    require_python
    install_kubectl_if_missing
    install_kind_if_missing
    log_ok "tooling installation complete"
}

cmd_demo() {
    require_python
    ensure_venv
    require_or_install_tools
    if [[ "${FLAG_NO_DEPLOY}" -eq 0 ]]; then
        require_docker
    fi
    verify_secret_or_offer_demo_mode
    if [[ "${FLAG_NO_DEPLOY}" -eq 0 ]]; then
        ensure_kind_cluster
    fi
    run_generation
    verify_resources
    render_summary
}

cmd_teardown() {
    teardown_cluster
}

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

main() {
    parse_args "$@"
    case "${SUBCOMMAND}" in
        help)     usage ;;
        check)    cmd_check ;;
        install)  cmd_install ;;
        teardown) cmd_teardown ;;
        demo)     cmd_demo ;;
        *)
            log_err "unhandled sub-command: ${SUBCOMMAND}"
            usage
            exit 2
            ;;
    esac
}

main "$@"
