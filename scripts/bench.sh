#!/usr/bin/env bash
# Harness health bench. Run: bash scripts/bench.sh   (from the workshop root)
set -uo pipefail
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/bench.py"
