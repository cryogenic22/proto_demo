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

# Seed protocol data into the volume on every deploy.
# Railway volumes mount over data/ — git-committed seed files are hidden.
# Always copy seed files to ensure updates (sections, tables) propagate.
# User-uploaded protocols (not in seed) are preserved.
SEED_DIR = Path("data_seed/protocols")
DATA_DIR = Path("data/protocols")
DATA_DIR.mkdir(parents=True, exist_ok=True)

if SEED_DIR.exists():
    seeds = list(SEED_DIR.glob("*.json"))
    updated = 0
    for src in seeds:
        dst = DATA_DIR / src.name
        # Always overwrite seed protocols with latest data
        shutil.copy2(src, dst)
        updated += 1
    print(f"Seeded {updated} protocols into volume.", flush=True)

    # Seed PDFs for source document preview
    PDF_SEED = Path("data_seed/pdfs")
    PDF_DIR = Path("data/pdfs")
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    if PDF_SEED.exists():
        for src in PDF_SEED.glob("*.pdf"):
            dst = PDF_DIR / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
                print(f"  Seeded PDF: {src.name}", flush=True)

    # Remove P-27 if it exists (empty protocol, no extraction data)
    p27 = DATA_DIR / "P-27.json"
    if p27.exists():
        p27.unlink()
        print("  Removed empty P-27.json", flush=True)

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
