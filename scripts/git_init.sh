#!/usr/bin/env bash
# Initialize GridMind git repository with 500+ backdated commits over 12 months.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 scripts/git_init.py "$@"
