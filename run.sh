#!/usr/bin/env bash
# Lanzador de InZain / Fractal Core.
set -euo pipefail
cd "$(dirname "$0")"

# El python del SISTEMA no tiene PyQt6-WebEngine: usar el venv del proyecto
# o fallar ruidosamente (nunca caer al sistema, que muere en el import).
if [ -x .venv/bin/python ]; then
    exec .venv/bin/python main.py "$@"
else
    echo "ERROR: falta .venv/bin/python (venv del proyecto)." >&2
    echo "Créalo con:  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi
