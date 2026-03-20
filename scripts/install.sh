#!/usr/bin/env bash
#
# hardware-test-platform installer - Bootstrap script
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/stellar/hardware-test-platform/master/scripts/install.sh | bash
#   curl -sSL https://raw.githubusercontent.com/stellar/hardware-test-platform/master/scripts/install.sh | bash -s -- --install-dir /opt/htp
#   curl -sSL https://raw.githubusercontent.com/stellar/hardware-test-platform/master/scripts/install.sh | bash -s -- --update-only
#

set -euo pipefail

# Color codes
readonly COLOR_BLUE='\033[94m'
readonly COLOR_GREEN='\033[92m'
readonly COLOR_RED='\033[91m'
readonly COLOR_YELLOW='\033[93m'
readonly COLOR_RESET='\033[0m'
readonly COLOR_BOLD='\033[1m'

# Configuration
REPO_OWNER="${REPO_OWNER:-StarSphere-1024}"
REPO_NAME="${REPO_NAME:-hardware-test-platform}"
BRANCH="${BRANCH:-master}"
INSTALLER_URL="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${BRANCH}/scripts/_install_installer.py"
COMMON_URL="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${BRANCH}/scripts/_install_common.py"

# Temporary directory for installer files
TEMP_DIR=""

# Cleanup function
cleanup() {
    if [[ -n "${TEMP_DIR}" && -d "${TEMP_DIR}" ]]; then
        rm -rf "${TEMP_DIR}"
    fi
}
trap cleanup EXIT

# Logging functions
log_info() {
    echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} $1"
}

log_success() {
    echo -e "${COLOR_GREEN}[SUCCESS]${COLOR_RESET} $1"
}

log_error() {
    echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} $1" >&2
}

log_warn() {
    echo -e "${COLOR_YELLOW}[WARN]${COLOR_RESET} $1" >&2
}

# Check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()

    if ! command_exists python3; then
        missing+=("python3")
    fi

    if ! command_exists git; then
        missing+=("git")
    fi

    if ! command_exists curl; then
        missing+=("curl")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required commands: ${missing[*]}"
        log_info "Please install the missing commands and try again."
        return 1
    fi

    # Check Python version
    local python_version
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    log_info "Found Python ${python_version}"

    log_success "Prerequisites check passed"
}

# Download file with retry
download_with_retry() {
    local url="$1"
    local output="$2"
    local max_retries=3
    local retry_count=0

    while [[ $retry_count -lt $max_retries ]]; do
        if curl -sSL --fail --retry 3 --retry-delay 2 -o "$output" "$url"; then
            return 0
        fi
        retry_count=$((retry_count + 1))
        if [[ $retry_count -lt $max_retries ]]; then
            log_warn "Download failed (attempt ${retry_count}/${max_retries}), retrying..."
            sleep 2
        fi
    done

    log_error "Failed to download ${url} after ${max_retries} attempts"
    return 1
}

# Main function
main() {
    # Parse arguments - pass through to Python installer
    local args=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --install-dir|--branch|--repo-owner|--repo-name|--update-only|--force|--no-bashrc|--dry-run|--verbose)
                args+=("$1")
                shift
                ;;
            --*=*)
                args+=("$1")
                shift
                ;;
            *)
                args+=("$1")
                shift
                ;;
        esac
    done

    # Add default repo-owner and repo-name if not provided
    local has_owner=false
    local has_name=false
    for arg in "${args[@]}"; do
        [[ "$arg" == "--repo-owner" ]] && has_owner=true
        [[ "$arg" == "--repo-name" ]] && has_name=true
    done

    if [[ "$has_owner" == false ]]; then
        args+=("--repo-owner" "$REPO_OWNER")
    fi
    if [[ "$has_name" == false ]]; then
        args+=("--repo-name" "$REPO_NAME")
    fi

    # Check prerequisites
    check_prerequisites || exit 1

    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    log_info "Using temporary directory: ${TEMP_DIR}"

    # Download installer scripts
    log_info "Downloading installer..."
    if ! download_with_retry "${INSTALLER_URL}" "${TEMP_DIR}/_install_installer.py"; then
        exit 1
    fi

    if ! download_with_retry "${COMMON_URL}" "${TEMP_DIR}/_install_common.py"; then
        exit 1
    fi

    # Run Python installer
    log_info "Running installer..."
    python3 "${TEMP_DIR}/_install_installer.py" "${args[@]}"
    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_success "Installation script completed successfully"
    else
        log_error "Installation script failed with exit code ${exit_code}"
    fi

    exit $exit_code
}

main "$@"
