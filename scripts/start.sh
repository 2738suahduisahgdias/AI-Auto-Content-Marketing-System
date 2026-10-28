#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -f "$ROOT/data/seed.json" ]]; then
  cp "$ROOT/data/seed.example.json" "$ROOT/data/seed.json"
fi
if [[ ! -f "$ROOT/web/react-dist/index.html" ]]; then
  echo "前端尚未构建，请先运行 bash scripts/setup.sh"
  exit 1
fi
if command -v open >/dev/null 2>&1; then
  (sleep 2; open "http://127.0.0.1:8765/setup") &
fi
exec python3 app.py --port 8765
