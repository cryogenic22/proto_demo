"""Railway startup script — wraps uvicorn with diagnostic output."""
import os
import shutil
import sys
from pathlib import Path

print("=" * 60, flush=True)
print("ProtoExtract — Railway Startup", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"PORT: {os.environ.get('PORT', 'NOT SET')}", flush=True)
print(f"Working dir: {os.getcwd()}", flush=True)
print("=" * 60, flush=True)

# Seed protocol data into the volume on first deploy.
# Railway volumes mount over data/ — so git-committed seed files
# are hidden. Copy them from data_seed/ if the volume is empty.
SEED_DIR = Path("data_seed/protocols")
DATA_DIR = Path("data/protocols")
DATA_DIR.mkdir(parents=True, exist_ok=True)

if SEED_DIR.exists():
    existing = list(DATA_DIR.glob("*.json"))
    seeds = list(SEED_DIR.glob("*.json"))
    if not existing and seeds:
        print(f"Seeding {len(seeds)} protocols into volume...", flush=True)
        for src in seeds:
            dst = DATA_DIR / src.name
            shutil.copy2(src, dst)
            print(f"  Copied {src.name}", flush=True)
    else:
        print(
            f"Volume has {len(existing)} protocols, "
            f"seed has {len(seeds)} — skipping seed.",
            flush=True,
        )

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
