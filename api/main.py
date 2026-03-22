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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional in production

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.models.schema import PipelineConfig, PipelineOutput
from src.persistence.ke_store import create_ke_store
from src.pipeline.orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Protocol Table Extractor",
    description="Extracts and digitizes tables from clinical trial protocol PDFs",
    version="0.1.0",
)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

_allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    FRONTEND_URL,
]


def _cors_origin_allowed(origin: str) -> bool:
    """Allow explicit origins + any *.up.railway.app subdomain."""
    if origin in _allowed_origins:
        return True
    if origin.endswith(".up.railway.app") and origin.startswith("https://"):
        return True
    return False


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.up\.railway\.app",
    allow_origins=_allowed_origins,
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


# ---------------------------------------------------------------------------
# Protocol workspace request/response models
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    """Request body for protocol Q&A."""

    question: str
    section_context: str | None = None


class AskSource(BaseModel):
    """Source citation in an assistant answer."""

    section: str = ""
    page: int = 0


class AskResponse(BaseModel):
    """Response from protocol Q&A."""

    role: str = "assistant"
    content: str = ""
    sources: list[AskSource] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    """Request body for cell review actions."""

    table_id: str
    row: int
    col: int
    action: str  # "accept", "correct", "flag"
    correct_value: str | None = None
    flag_reason: str | None = None


class ReviewResponse(BaseModel):
    """Response from cell review."""

    success: bool = True


class ProcedureLibraryEntry(BaseModel):
    """A single procedure in the canonical library."""

    canonical_name: str
    cpt_code: str = ""
    code_system: str = ""
    category: str = ""
    cost_tier: str = ""
    aliases: str = ""


def _build_config(**overrides) -> PipelineConfig:
    """Build PipelineConfig from environment variables. Single source of truth."""
    return PipelineConfig(
        llm_provider=os.environ.get("LLM_PROVIDER", "anthropic"),
        llm_model=os.environ.get("LLM_MODEL", ""),
        vision_model=os.environ.get("VISION_MODEL", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        azure_openai_api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
        azure_openai_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        azure_openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        azure_openai_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", ""),
        render_dpi=150,
        max_concurrent_llm_calls=int(os.environ.get("MAX_CONCURRENT_LLM_CALLS", "10")),
        openai_batch_mode=os.environ.get("OPENAI_BATCH_MODE", "").lower() in ("true", "1", "yes"),
        soa_only=True,
        **overrides,
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/telemetry/runs")
async def get_telemetry_runs(limit: int = 20):
    """Get recent pipeline run telemetry."""
    from src.pipeline.telemetry import get_telemetry
    return {"runs": get_telemetry().get_recent_runs(limit)}


@app.get("/api/telemetry/errors")
async def get_telemetry_errors(limit: int = 50):
    """Get recent pipeline errors with tracebacks."""
    from src.pipeline.telemetry import get_telemetry
    return {"errors": get_telemetry().get_errors(limit)}


@app.get("/api/checkpoints/{doc_hash}")
async def get_checkpoint(doc_hash: str):
    """Recover extracted tables from a crashed pipeline run."""
    from src.pipeline.orchestrator import _CheckpointManager
    data = _CheckpointManager.load_checkpoint(doc_hash)
    if not data:
        raise HTTPException(status_code=404, detail="No checkpoint found")
    return data


@app.get("/api/benchmark")
async def get_benchmark():
    """Get benchmark comparison across all tested protocols."""
    from src.pipeline.benchmark import load_benchmark
    benchmarks = load_benchmark()
    return {"protocols": [b.__dict__ for b in benchmarks], "total": len(benchmarks)}


@app.get("/api/benchmark/report")
async def get_benchmark_report():
    """Get benchmark HTML report."""
    from fastapi.responses import HTMLResponse
    from src.pipeline.benchmark import generate_benchmark_html
    html = generate_benchmark_html()
    return HTMLResponse(html)


@app.get("/api/procedures/mapping")
async def get_procedure_mapping():
    """Export the full procedure mapping table for clinical review."""
    from src.pipeline.procedure_normalizer import ProcedureNormalizer
    normalizer = ProcedureNormalizer()
    return {"procedures": normalizer.get_mapping_table(), "total": len(normalizer.get_mapping_table())}


@app.post("/api/sections")
async def parse_sections(file: UploadFile = File(...), use_llm: bool = False):
    """Parse all sections from a PDF or DOCX. Returns the full document outline.

    Args:
        use_llm: Force LLM-assisted parsing (recommended for non-standard documents)
    """
    from src.pipeline.section_parser import SectionParser
    from src.llm.client import LLMClient

    file_bytes = await file.read()
    parser = SectionParser()
    sections = parser.parse(file_bytes, filename=file.filename or "")

    # Auto-trigger LLM fallback if deterministic parsing found too few sections
    if (use_llm or parser.needs_llm_fallback) and len(sections) < 10:
        logger.info(f"Section parser found {len(sections)} sections — using LLM fallback")
        config = _build_config()
        llm = LLMClient(config)
        llm_sections = await parser.parse_with_llm(file_bytes, llm_client=llm)
        if len(llm_sections) > len(sections):
            sections = llm_sections

    return {
        "sections": [s.to_dict() for s in sections],
        "total": len(sections),
        "outline": parser.to_outline(sections),
        "method": "llm_fallback" if parser.needs_llm_fallback else "deterministic",
    }


@app.post("/api/verbatim")
async def extract_verbatim(
    file: UploadFile = File(...),
    instruction: str = "",
    include_subsections: bool = True,
    output_format: str = "text",
):
    """Extract verbatim content from a protocol PDF/DOCX.

    The LLM locates the content; PyMuPDF/python-docx extracts the exact text.
    Zero hallucination — the output text is never LLM-generated.

    Args:
        instruction: What to extract (e.g., "Copy Section 5.1")
        include_subsections: Include subsection content (default True)
        output_format: "text" (plain), "html" (semantic HTML with paragraphs, lists, tables),
            "docx" (Word document download)

    Example instructions:
    - "Copy Section 5.1"
    - "Extract the inclusion criteria"
    - "Get the Schedule of Activities table"
    - "Copy the primary endpoint definition from Section 3"
    """
    if not instruction:
        raise HTTPException(status_code=400, detail="Provide an 'instruction' query parameter")

    from src.pipeline.verbatim_extractor import VerbatimExtractor
    file_bytes = await file.read()
    config = _build_config()
    extractor = VerbatimExtractor(config)
    result = await extractor.extract(
        file_bytes, instruction, filename=file.filename or "",
        output_format=output_format,
    )

    # DOCX output: return as downloadable file
    if output_format == "docx" and result.sections_found:
        from fastapi.responses import Response
        section = extractor.section_parser.find(
            extractor.section_parser.parse(file_bytes, filename=file.filename or ""),
            result.sections_found[0],
        )
        if section:
            docx_bytes = extractor.section_parser.get_section_formatted(
                file_bytes, section, output="docx"
            )
            return Response(
                content=docx_bytes,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'attachment; filename="section_{result.sections_found[0]}.docx"'},
            )

    return {
        "instruction": result.instruction,
        "sections_found": result.sections_found,
        "content_type": result.content_type,
        "text": result.text,
        "tables": result.tables,
        "source_pages": result.source_pages,
        "explanation": result.explanation,
        "is_verbatim": result.is_verbatim,
    }


@app.post("/api/procedures/check")
async def check_procedure_mapping(names: list[str]):
    """Check which procedure names can/cannot be mapped."""
    from src.pipeline.procedure_normalizer import ProcedureNormalizer
    normalizer = ProcedureNormalizer()
    mapped = [normalizer.normalize(n).model_dump() for n in names]
    unmapped = normalizer.get_unmapped_report(names)
    return {"mapped": mapped, "unmapped": unmapped}


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


@app.get("/api/jobs/{job_id}/review")
async def get_job_review(job_id: str, format: str = "json"):
    """Get extraction results formatted for medical writer review.

    Args:
        format: "json" for structured review, "markdown" for human-readable doc
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job is {job['status']}, not completed")

    from src.models.schema import PipelineOutput as PipelineOutputModel
    from src.pipeline.review_exporter import export_review_document, export_review_json

    result = PipelineOutputModel.model_validate(job["result"])

    if format == "markdown":
        from fastapi.responses import PlainTextResponse
        md = export_review_document(result)
        return PlainTextResponse(md, media_type="text/markdown")
    elif format == "html":
        from fastapi.responses import HTMLResponse
        from src.pipeline.html_report import generate_html_report
        from src.pipeline.run_comparator import compare_runs
        # Compare against previous run if available
        comparison = compare_runs(job["result"])
        comparison_html = comparison.to_html_section() if comparison else ""
        html = generate_html_report(result, comparison_html=comparison_html)
        return HTMLResponse(html)
    elif format == "budget":
        from fastapi.responses import HTMLResponse
        from src.pipeline.budget_calculator import generate_budget_html
        html = generate_budget_html(result)
        return HTMLResponse(html)
    else:
        return export_review_json(result)


async def _run_extraction(job_id: str, pdf_bytes: bytes, filename: str):
    """Background task to run the extraction pipeline.

    Wrapped in broad exception handling so the server NEVER crashes —
    any failure is captured and reported back through the job status.
    """
    from src.pipeline.telemetry import get_telemetry
    tel = get_telemetry()
    start_time = time.time()

    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = 5
        jobs[job_id]["message"] = "Initializing pipeline..."

        config = _build_config()
        orchestrator = PipelineOrchestrator(config)

        jobs[job_id]["progress"] = 10
        jobs[job_id]["message"] = "Ingesting PDF..."

        tel.log_run_start(job_id, filename, 0, config.model_dump())

        def on_progress(pct: int, msg: str):
            jobs[job_id]["progress"] = pct
            jobs[job_id]["message"] = msg
            tel.log_stage(job_id, "progress", detail=f"{pct}% {msg}")

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

        total_cells = sum(len(t.cells) for t in result.tables)
        total_fn = sum(len(t.footnotes) for t in result.tables)
        avg_conf = sum(t.overall_confidence for t in result.tables) / max(len(result.tables), 1)

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = f"Extracted {len(result.tables)} tables"
        jobs[job_id]["result"] = result_json
        jobs[job_id]["completed_at"] = time.time()

        # Persist protocol to the knowledge-element store
        try:
            from src.persistence.protocol_bridge import (
                pipeline_output_to_protocol,
            )

            protocol = pipeline_output_to_protocol(result_json, filename)
            store = create_ke_store()
            store.save_protocol(protocol)
            logger.info("Saved protocol %s to store", protocol.protocol_id)
        except Exception as bridge_err:
            logger.warning("Protocol persistence failed: %s", bridge_err)

        # Auto-record benchmark
        try:
            from src.pipeline.benchmark import from_pipeline_output, add_benchmark
            bm = from_pipeline_output(result_json, job_id)
            add_benchmark(bm)
        except Exception as bm_err:
            logger.warning(f"Benchmark recording failed: {bm_err}")

        tel.log_run_end(
            job_id, "completed", tables=len(result.tables), cells=total_cells,
            footnotes=total_fn, confidence=avg_conf,
            duration_s=time.time() - start_time, warnings=len(result.warnings),
        )

    except MemoryError:
        logger.error(f"Out of memory processing job {job_id}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = 0
        jobs[job_id]["message"] = "Out of memory — try a smaller document or reduce DPI"
        jobs[job_id]["error"] = "MemoryError: document too large"
        jobs[job_id]["completed_at"] = time.time()
        tel.log_run_end(job_id, "failed_oom", 0, 0, 0, 0, time.time() - start_time,
                        errors=["MemoryError"])

    except Exception as e:
        logger.exception(f"Extraction failed for job {job_id}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = 0
        jobs[job_id]["message"] = f"Extraction failed: {str(e)}"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = time.time()
        import traceback
        tel.log_run_end(job_id, "failed", 0, 0, 0, 0, time.time() - start_time,
                        errors=[str(e)])
        tel.log_error(job_id, "pipeline", str(e), traceback.format_exc())

    finally:
        import gc
        gc.collect()


# ---------------------------------------------------------------------------
# Protocol workspace endpoints (ask, review, procedure library)
# ---------------------------------------------------------------------------


@app.post("/api/protocols/{protocol_id}/ask", response_model=AskResponse)
async def ask_protocol_endpoint(protocol_id: str, body: AskRequest):
    """Ask a question about a stored protocol."""
    store = create_ke_store()
    protocol = store.load_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(status_code=404, detail="Protocol not found")

    return AskResponse(
        role="assistant",
        content=(
            "LLM-based Q&A is not yet configured. "
            f"Protocol '{protocol.document_name}' has "
            f"{len(protocol.tables)} table(s) and "
            f"{protocol.total_pages} page(s)."
        ),
        sources=[AskSource(section="metadata", page=0)],
    )


@app.post("/api/protocols/{protocol_id}/review", response_model=ReviewResponse)
async def review_protocol_cell(protocol_id: str, body: ReviewRequest):
    """Accept, correct, or flag a cell in a stored protocol."""
    store = create_ke_store()
    protocol = store.load_protocol(protocol_id)
    if protocol is None:
        raise HTTPException(status_code=404, detail="Protocol not found")

    table = next(
        (t for t in protocol.tables if t.get("table_id") == body.table_id),
        None,
    )
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")

    cells = table.get("cells", [])
    cell = next(
        (c for c in cells if c.get("row") == body.row and c.get("col") == body.col),
        None,
    )

    if body.action == "accept" and cell is not None:
        cell["confidence"] = 1.0
    elif body.action == "correct" and cell is not None:
        cell["raw_value"] = body.correct_value or ""
    elif body.action == "flag":
        review_items = table.setdefault("review_items", [])
        review_items.append({
            "row": body.row,
            "col": body.col,
            "reason": body.flag_reason or "",
            "action": "flag",
        })
    else:
        raise HTTPException(
            status_code=400, detail="Invalid action or cell not found"
        )

    store.save_protocol(protocol)
    return ReviewResponse(success=True)


@app.get("/api/procedures/library", response_model=list[ProcedureLibraryEntry])
async def get_procedures_library():
    """Return the full canonical procedure library with CPT codes."""
    from src.pipeline.procedure_normalizer import ProcedureNormalizer

    normalizer = ProcedureNormalizer()
    rows = normalizer.get_mapping_table()
    return [
        ProcedureLibraryEntry(
            canonical_name=r["canonical_name"],
            cpt_code=r.get("cpt_code", ""),
            code_system=r.get("code_system", ""),
            category=r.get("category", ""),
            cost_tier=r.get("cost_tier", ""),
            aliases=r.get("aliases", ""),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Protocol & Knowledge Element endpoints
# ---------------------------------------------------------------------------


@app.get("/api/protocols")
async def list_protocols():
    """List all stored protocols."""
    store = create_ke_store()
    return store.list_protocols()


@app.get("/api/protocols/{protocol_id}")
async def get_protocol(protocol_id: str):
    """Get full protocol data."""
    store = create_ke_store()
    protocol = store.load_protocol(protocol_id)
    if not protocol:
        raise HTTPException(
            status_code=404, detail=f"Protocol {protocol_id} not found"
        )
    return protocol.model_dump(mode="json")


@app.get("/api/protocols/{protocol_id}/sections")
async def get_protocol_sections(protocol_id: str):
    """Get the section tree for a protocol."""
    store = create_ke_store()
    protocol = store.load_protocol(protocol_id)
    if not protocol:
        raise HTTPException(
            status_code=404, detail=f"Protocol {protocol_id} not found"
        )
    return [s.model_dump() for s in protocol.sections]


@app.get("/api/protocols/{protocol_id}/sections/{section_number:path}")
async def get_section_content(protocol_id: str, section_number: str):
    """Get content for a specific section."""
    store = create_ke_store()
    protocol = store.load_protocol(protocol_id)
    if not protocol:
        raise HTTPException(
            status_code=404, detail=f"Protocol {protocol_id} not found"
        )

    def find_section(sections, number):
        for s in sections:
            if s.number == number:
                return s
            found = find_section(s.children, number)
            if found:
                return found
        return None

    section = find_section(protocol.sections, section_number)
    if not section:
        raise HTTPException(
            status_code=404, detail=f"Section {section_number} not found"
        )
    return section.model_dump()


@app.get("/api/protocols/{protocol_id}/budget")
async def get_protocol_budget(protocol_id: str):
    """Get budget line items for a protocol."""
    store = create_ke_store()
    protocol = store.load_protocol(protocol_id)
    if not protocol:
        raise HTTPException(
            status_code=404, detail=f"Protocol {protocol_id} not found"
        )
    return protocol.budget_lines


@app.get("/api/protocols/{protocol_id}/knowledge-elements")
async def get_knowledge_elements(
    protocol_id: str, ke_type: str | None = None
):
    """Get knowledge elements, optionally filtered by type."""
    store = create_ke_store()
    kes = store.get_knowledge_elements(protocol_id, ke_type)
    return [ke.model_dump() for ke in kes]


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
