#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
export PYTHONPATH="$PWD/backend:$PYTHONPATH"
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
