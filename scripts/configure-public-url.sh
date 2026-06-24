#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC_URL=""
ALLOW_LOCAL_HTTP=false
DRY_RUN=false

usage() {
  cat <<'USAGE'
Usage: scripts/configure-public-url.sh --public-url URL [options]

Updates local ignored env files so Web, Java, AI, LINE Login, and LINE
action links use one public entrypoint.

Options:
  --public-url URL       Public Nginx URL, for example https://demo.example.com
  --allow-local-http     Allow http://localhost:* for route rehearsal only.
  --dry-run              Print planned changes without writing env files.
  -h, --help             Show this help.

This script intentionally edits only local ignored env files:
  .env
  backend-java/.env
  ai-service-python/.env
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --public-url)
      if [ "$#" -lt 2 ]; then
        printf "--public-url requires a URL\n" >&2
        exit 2
      fi
      PUBLIC_URL="$2"
      shift 2
      ;;
    --allow-local-http)
      ALLOW_LOCAL_HTTP=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
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

if [ -z "$PUBLIC_URL" ]; then
  usage >&2
  exit 2
fi

PUBLIC_URL="${PUBLIC_URL%/}"

case "$PUBLIC_URL" in
  https://*) ;;
  http://localhost:*|http://127.0.0.1:*)
    if [ "$ALLOW_LOCAL_HTTP" != "true" ]; then
      printf "LINE Login needs a public HTTPS URL. Use --allow-local-http only for local Nginx route rehearsal.\n" >&2
      exit 2
    fi
    ;;
  *)
    printf "public URL must be https://... for LINE Login, or localhost with --allow-local-http for rehearsal.\n" >&2
    exit 2
    ;;
esac

export PUBLIC_URL DRY_RUN ROOT_DIR

python3 <<'PY'
from __future__ import annotations

import os
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
public_url = os.environ["PUBLIC_URL"]
dry_run = os.environ["DRY_RUN"] == "true"

callback = f"{public_url}/api/java/api/auth/line/callback"
cookie_path = "/api/java/api/auth/line"

updates_by_file = {
    ".env": {
        "LINE_REDIRECT_URI": callback,
        "FRONTEND_URL": public_url,
        "LINE_OAUTH_COOKIE_PATH": cookie_path,
        "CORS_ALLOWED_ORIGIN_PATTERNS": public_url,
    },
    "backend-java/.env": {
        "LINE_REDIRECT_URI": callback,
        "FRONTEND_URL": public_url,
        "LINE_OAUTH_COOKIE_PATH": cookie_path,
        "CORS_ALLOWED_ORIGIN_PATTERNS": public_url,
    },
    "ai-service-python/.env": {
        "LINE_PUBLIC_WEB_URL": public_url,
    },
}


def merge_env(text: str, updates: dict[str, str]) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for line in text.splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            output.append(line)
            continue
        key = line.split("=", 1)[0]
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")
    return "\n".join(output) + "\n"


for relative, updates in updates_by_file.items():
    path = root / relative
    if not path.exists():
        raise SystemExit(f"missing env file: {relative}")
    current = path.read_text()
    new = merge_env(current, updates)
    if dry_run:
        print(f"DRY-RUN {relative}")
        for key, value in updates.items():
            print(f"  {key}={value}")
    elif new != current:
        path.write_text(new)
        print(f"UPDATED {relative}")
    else:
        print(f"UNCHANGED {relative}")
PY

printf "\nNext steps:\n"
printf "  1. Restart Java and AI so they reload env values.\n"
printf "  2. Register this LINE Login callback in LINE Developers:\n"
printf "     %s/api/java/api/auth/line/callback\n" "$PUBLIC_URL"
printf "  3. Register this LINE Messaging webhook if using the bot:\n"
printf "     %s/api/line/webhook\n" "$PUBLIC_URL"
printf "  4. Verify:\n"
printf "     EXPECTED_LINE_REDIRECT_URI=%s/api/java/api/auth/line/callback scripts/smoke-nginx-public-proxy.sh --base-url %s\n" "$PUBLIC_URL" "$PUBLIC_URL"
