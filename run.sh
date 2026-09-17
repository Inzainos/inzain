#!/usr/bin/env bash
# Lanzador de InZain / Fractal Core.
set -euo pipefail
cd "$(dirname "$0")"
exec python main.py "$@"
