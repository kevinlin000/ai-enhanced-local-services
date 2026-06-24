#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC_URL=""

usage() {
  cat <<'USAGE'
Usage: scripts/verify-public-url-env.sh --public-url URL

Checks local ignored env files for public URL drift. Use this before a demo
when Nginx is the public entrypoint.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --public-url)
      PUBLIC_URL="${2:-}"
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

if [ -z "$PUBLIC_URL" ]; then
  usage >&2
  exit 2
fi

PUBLIC_URL="${PUBLIC_URL%/}"
export ROOT_DIR PUBLIC_URL

python3 <<'PY'
from __future__ import annotations

import os
from pathlib import Path

root = Path(os.environ["ROOT_DIR"])
public_url = os.environ["PUBLIC_URL"]
callback = f"{public_url}/api/java/api/auth/line/callback"
cookie_path = "/api/java/api/auth/line"

checks = {
    ".env": {
        "LINE_REDIRECT_URI": callback,
        "FRONTEND_URL": public_url,
        "LINE_OAUTH_COOKIE_PATH": cookie_path,
    },
    "backend-java/.env": {
        "LINE_REDIRECT_URI": callback,
        "FRONTEND_URL": public_url,
        "LINE_OAUTH_COOKIE_PATH": cookie_path,
    },
    "ai-service-python/.env": {
        "LINE_PUBLIC_WEB_URL": public_url,
    },
}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


failed = False
for relative, expected in checks.items():
    path = root / relative
    if not path.exists():
        print(f"FAIL missing {relative}")
        failed = True
        continue
    values = load_env(path)
    for key, expected_value in expected.items():
        actual = values.get(key)
        if actual != expected_value:
            print(f"FAIL {relative} {key}")
            print(f"  expected: {expected_value}")
            print(f"  actual:   {actual or '<missing>'}")
            failed = True
        else:
            print(f"PASS {relative} {key}")

if failed:
    raise SystemExit(1)

print("Public URL env verification passed.")
PY
