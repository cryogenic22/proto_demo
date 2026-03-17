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

    # Run extraction in background
    asyncio.create_task(_run_extraction(job_id, pdf_bytes, file.filename))

    return {"job_id": job_id, "status": "pending"}


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
    """Background task to run the extraction pipeline."""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = 5
        jobs[job_id]["message"] = "Initializing pipeline..."

        config = PipelineConfig(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        orchestrator = PipelineOrchestrator(config)

        jobs[job_id]["progress"] = 10
        jobs[job_id]["message"] = "Ingesting PDF..."

        result = await orchestrator.run(pdf_bytes, filename)

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = f"Extracted {len(result.tables)} tables"
        jobs[job_id]["result"] = json.loads(result.model_dump_json())
        jobs[job_id]["completed_at"] = time.time()

    except Exception as e:
        logger.exception(f"Extraction failed for job {job_id}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = 0
        jobs[job_id]["message"] = f"Extraction failed: {str(e)}"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = time.time()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
