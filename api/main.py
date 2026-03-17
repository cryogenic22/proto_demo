"""
FastAPI backend for the Protocol Table Extraction Pipeline.

Provides endpoints for:
- PDF upload and extraction
- Status polling for long-running extractions
- Result retrieval
- Golden set evaluation
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.models.schema import PipelineConfig, PipelineOutput
from src.pipeline.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Protocol Table Extractor",
    description="Extracts and digitizes tables from clinical trial protocol PDFs",
    version="0.1.0",
)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (production: use Redis or database)
jobs: dict[str, dict[str, Any]] = {}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all so the server never crashes on unhandled errors."""
    logger.exception(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


class JobStatus(BaseModel):
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: int  # 0-100
    message: str
    document_name: str
    result: dict | None = None
    error: str | None = None
    created_at: float
    completed_at: float | None = None


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/extract")
async def extract_protocol(file: UploadFile = File(...)):
    """
    Upload a protocol PDF and start extraction.
    Returns a job_id for polling status.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    if len(pdf_bytes) > 100 * 1024 * 1024:  # 100MB limit
        raise HTTPException(status_code=400, detail="File too large (max 100MB)")

    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "message": "Queued for processing",
        "document_name": file.filename,
        "result": None,
        "error": None,
        "created_at": time.time(),
        "completed_at": None,
    }

    # Run extraction in background with error logging
    task = asyncio.create_task(_run_extraction(job_id, pdf_bytes, file.filename))
    task.add_done_callback(_task_done_callback)

    return {"job_id": job_id, "status": "pending"}


def _task_done_callback(task: asyncio.Task):
    """Log any unhandled exception from background tasks so they don't crash the server."""
    if task.cancelled():
        logger.warning("Extraction task was cancelled")
        return
    exc = task.exception()
    if exc:
        logger.error(f"Extraction task failed with unhandled exception: {exc}", exc_info=exc)


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of an extraction job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        document_name=job["document_name"],
        result=job["result"],
        error=job["error"],
        created_at=job["created_at"],
        completed_at=job["completed_at"],
    )


@app.get("/api/jobs")
async def list_jobs():
    """List all jobs."""
    return [
        JobStatus(
            job_id=jid,
            status=j["status"],
            progress=j["progress"],
            message=j["message"],
            document_name=j["document_name"],
            result=None,  # Don't include full results in list view
            error=j["error"],
            created_at=j["created_at"],
            completed_at=j["completed_at"],
        )
        for jid, j in sorted(jobs.items(), key=lambda x: x[1]["created_at"], reverse=True)
    ]


@app.delete("/api/jobs")
async def clear_all_jobs():
    """Clear all jobs from the queue."""
    count = len(jobs)
    jobs.clear()
    return {"cleared": count}


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a specific job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    del jobs[job_id]
    return {"deleted": job_id}


@app.get("/api/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    """Get the full result of a completed extraction job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job is {job['status']}, not completed")

    return job["result"]


async def _run_extraction(job_id: str, pdf_bytes: bytes, filename: str):
    """Background task to run the extraction pipeline.

    Wrapped in broad exception handling so the server NEVER crashes —
    any failure is captured and reported back through the job status.
    """
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = 5
        jobs[job_id]["message"] = "Initializing pipeline..."

        config = PipelineConfig(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            render_dpi=150,  # Lower DPI for memory safety on large docs
            max_concurrent_llm_calls=5,
            soa_only=True,  # Focus on Schedule of Activities tables for site budgeting
        )
        orchestrator = PipelineOrchestrator(config)

        jobs[job_id]["progress"] = 10
        jobs[job_id]["message"] = "Ingesting PDF..."

        def on_progress(pct: int, msg: str):
            jobs[job_id]["progress"] = pct
            jobs[job_id]["message"] = msg

        result = await orchestrator.run(pdf_bytes, filename, on_progress=on_progress)

        # Serialize result — use try/except to handle serialization errors
        try:
            result_json = json.loads(result.model_dump_json())
        except Exception as ser_err:
            logger.error(f"Result serialization failed: {ser_err}")
            result_json = {
                "document_name": filename,
                "tables": [],
                "total_pages": result.total_pages,
                "warnings": result.warnings + [f"Serialization error: {ser_err}"],
            }

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = f"Extracted {len(result.tables)} tables"
        jobs[job_id]["result"] = result_json
        jobs[job_id]["completed_at"] = time.time()

    except MemoryError:
        logger.error(f"Out of memory processing job {job_id}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = 0
        jobs[job_id]["message"] = "Out of memory — try a smaller document or reduce DPI"
        jobs[job_id]["error"] = "MemoryError: document too large"
        jobs[job_id]["completed_at"] = time.time()

    except Exception as e:
        logger.exception(f"Extraction failed for job {job_id}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = 0
        jobs[job_id]["message"] = f"Extraction failed: {str(e)}"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = time.time()

    finally:
        # Force garbage collection after processing
        import gc
        gc.collect()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
