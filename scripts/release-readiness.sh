#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="dry-run"
BASE_URL="${BASE_URL:-http://localhost:8088}"
CLEAN_MIGRATION_TIMEOUT="${CLEAN_MIGRATION_TIMEOUT:-180}"

usage() {
  cat <<'USAGE'
Usage: scripts/release-readiness.sh [mode] [options]

Routes ByteBites release checks without hiding which checks are offline and
which checks require live local services.

Modes:
  --dry-run       Print release checklist only. This is the default.
  --offline       Run fast local contract checks; no live Web/Java/AI/Nginx required.
  --full          Run scripts/verify-portfolio.sh.
  --live-local    Run local clean DB smoke and strict Nginx public-proxy smoke.

Options:
  --base-url URL  Public proxy base URL for --live-local. Default: http://localhost:8088
  -h, --help      Show this help.

Environment:
  BASE_URL
  CLEAN_MIGRATION_TIMEOUT
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      MODE="dry-run"
      shift
      ;;
    --offline)
      MODE="offline"
      shift
      ;;
    --full)
      MODE="full"
      shift
      ;;
    --live-local)
      MODE="live-local"
      shift
      ;;
    --base-url)
      if [ "$#" -lt 2 ]; then
        printf "%s\n" "--base-url requires a URL" >&2
        usage >&2
        exit 2
      fi
      BASE_URL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf "unknown option: %s\n" "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

run_step() {
  local label="$1"
  shift
  printf "\n==> %s\n" "$label"
  "$@"
}

print_checklist() {
  cat <<CHECKLIST
ByteBites release readiness dry run
base_url=$BASE_URL
clean_migration_timeout=$CLEAN_MIGRATION_TIMEOUT

Offline release gate:
  scripts/release-readiness.sh --offline

Full portfolio gate:
  scripts/release-readiness.sh --full

Local live rehearsal, after Web/Java/AI/Nginx public proxy are running:
  scripts/release-readiness.sh --live-local --base-url $BASE_URL

Manual GitHub Actions rehearsal:
  .github/workflows/clean-mysql-migration-smoke.yml

Commit grouping:
  1. Booking operations
  2. AI orchestration
  3. Web operations UI
  4. Deployment boundary
  5. Migration reliability
  6. Evidence and docs
CHECKLIST
}

cd "$ROOT_DIR"

case "$MODE" in
  dry-run)
    print_checklist
    ;;
  offline)
    run_step "Whitespace check" git diff --check
    run_step "Nginx deployment contract" python3 scripts/verify-nginx-template.py
    run_step "Clean migration workflow contract" python3 scripts/verify-clean-migration-workflow.py
    run_step "Release boundary contract" python3 scripts/verify-release-boundary.py
    run_step "Data-quality evidence contract" python3 scripts/verify-data-quality.py
    run_step "Smoke script syntax" bash -c "bash -n scripts/demo-readiness.sh && bash -n scripts/smoke-nginx-public-proxy.sh && bash -n scripts/smoke-clean-mysql-migrations.sh && bash -n scripts/release-readiness.sh"
    run_step "Smoke script dry-runs" bash -c "scripts/demo-readiness.sh --dry-run >/dev/null && scripts/smoke-nginx-public-proxy.sh --dry-run >/dev/null && scripts/smoke-clean-mysql-migrations.sh --dry-run >/dev/null && scripts/release-readiness.sh --dry-run >/dev/null"
    printf "\nRelease offline readiness passed.\n"
    ;;
  full)
    run_step "Portfolio verification" scripts/verify-portfolio.sh
    ;;
  live-local)
    run_step "Clean MySQL migration smoke" scripts/smoke-clean-mysql-migrations.sh --timeout "$CLEAN_MIGRATION_TIMEOUT"
    run_step "Strict local public-proxy smoke" scripts/demo-readiness.sh --base-url "$BASE_URL" --live-smoke --strict
    printf "\nRelease live-local readiness passed.\n"
    ;;
  *)
    printf "unsupported mode: %s\n" "$MODE" >&2
    exit 2
    ;;
esac
