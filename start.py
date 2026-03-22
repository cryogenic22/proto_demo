"""Railway startup script — wraps uvicorn with diagnostic output."""
import os
import sys

print("=" * 60, flush=True)
print("ProtoExtract — Railway Startup", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"PORT: {os.environ.get('PORT', 'NOT SET')}", flush=True)
print(f"Working dir: {os.getcwd()}", flush=True)
print("=" * 60, flush=True)

# Test critical imports before uvicorn tries
try:
    print("Importing api.main...", flush=True)
    import api.main  # noqa: F401
    print("OK: api.main imported successfully", flush=True)
except Exception as e:
    print(f"FATAL: Failed to import api.main: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Start uvicorn
port = int(os.environ.get("PORT", 8000))
print(f"Starting uvicorn on port {port}...", flush=True)

import uvicorn
uvicorn.run("api.main:app", host="0.0.0.0", port=port, log_level="info")
