#!/usr/bin/env bash
#
# Tidy all Go modules in the repository.
# Usage: ./tidy_go.sh [-v]
#  -v   verbose (echo commands)
set -euo pipefail

VERBOSE=0
if [[ "${1:-}" == "-v" ]]; then
  VERBOSE=1
fi

log() {
  printf '[tidy] %s\n' "$*" >&2
}

run() {
  if [[ $VERBOSE -eq 1 ]]; then
    printf '  > %s\n' "$*" >&2
  fi
  eval "$@"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if ! command -v go >/dev/null 2>&1; then
  log "go toolchain not found in PATH"
  exit 1
fi

log "Root: ${ROOT_DIR}"
log "Go version: $(go version)"

# Collect go.mod files (exclude vendor)
mapfile -t MODULE_FILES < <(find "${ROOT_DIR}" -type f -name go.mod -not -path '*/vendor/*' | sort)

if [[ ${#MODULE_FILES[@]} -eq 0 ]]; then
  log "No go.mod files found"
  exit 0
fi

FAILED=0
for modfile in "${MODULE_FILES[@]}"; do
  MOD_DIR="$(dirname "${modfile}")"
  REL_DIR="${MOD_DIR#${ROOT_DIR}/}"
  log "Tidying module: ${REL_DIR}"

  pushd "${MOD_DIR}" >/dev/null
  # Optional: clear stale sum entries first (not strictly required)
  run go mod tidy
  run go mod verify || FAILED=1
  popd >/dev/null
done

if [[ $FAILED -ne 0 ]]; then
  log "One or more modules failed verification"
  exit 1
fi

log "All modules tidied successfully"