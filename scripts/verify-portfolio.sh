#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT_DIR/.uv-cache}"

run_step() {
  local label="$1"
  shift
  printf "\n==> %s\n" "$label"
  "$@"
}

run_step "Backend Java contract tests" \
  bash -c "cd '$ROOT_DIR/backend-java' && TAPPAY_PARTNER_KEY=test TAPPAY_MERCHANT_CREDITCARD=test mvn test"

run_step "AI service tests" \
  bash -c "cd '$ROOT_DIR/ai-service-python' && uv run --no-sync pytest tests -q"

run_step "ETL data-quality tests" \
  bash -c "cd '$ROOT_DIR/etl-pipeline' && uv run --no-sync pytest tests -q"

run_step "Portfolio data-quality gate" \
  python3 "$ROOT_DIR/scripts/verify-data-quality.py"

run_step "Nginx deployment template contract" \
  python3 "$ROOT_DIR/scripts/verify-nginx-template.py"

run_step "Clean MySQL migration smoke contract" \
  bash -c "cd '$ROOT_DIR' && bash -n scripts/smoke-clean-mysql-migrations.sh && scripts/smoke-clean-mysql-migrations.sh --dry-run >/dev/null"

run_step "Clean MySQL migration workflow contract" \
  python3 "$ROOT_DIR/scripts/verify-clean-migration-workflow.py"

run_step "GitHub Actions version contract" \
  python3 "$ROOT_DIR/scripts/verify-github-actions-versions.py"

run_step "Release boundary contract" \
  python3 "$ROOT_DIR/scripts/verify-release-boundary.py"

run_step "Performance/query evidence contract" \
  python3 "$ROOT_DIR/scripts/verify-performance-query-evidence.py"

run_step "Web unit/design contract tests" \
  bash -c "cd '$ROOT_DIR/web' && pnpm test"

run_step "Web production build" \
  bash -c "cd '$ROOT_DIR/web' && pnpm build:ci"

printf "\nPortfolio verification passed.\n"
