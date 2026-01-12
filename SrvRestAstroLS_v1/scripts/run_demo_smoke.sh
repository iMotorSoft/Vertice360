#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export DEMO_DISABLE_META_SEND=1

pytest -q backend/tests

if command -v pnpm >/dev/null 2>&1; then
  if grep -q '"check"' astro/package.json; then
    pnpm -C astro check
  else
    pnpm -C astro build
  fi
else
  test -f astro/src/pages/demo/vertice360-workflow/index.astro
fi
