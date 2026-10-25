#!/bin/sh
ROOT=$(CDPATH= cd -- "$(dirname "$0")" && pwd) || exit 1
PYTHONPATH="$ROOT/src" python -m depgraph "$@"
