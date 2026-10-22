#!/usr/bin/env bash
# Structural bench for the brain + harness. Run: bash ~/.config/opencode/scripts/bench.sh
set -uo pipefail

CONFIG="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
export OPENCODE_CONFIG_DIR="$CONFIG"
python3 "$(dirname "${BASH_SOURCE[0]}")/bench.py"
