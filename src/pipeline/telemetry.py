"""
Pipeline Telemetry — persistent logging for run tracking and debugging.

Writes append-only JSONL logs to .telemetry/ directory:
- pipeline_runs.jsonl: per-job metadata (start, end, status, metrics)
- stage_events.jsonl: per-stage events (timing, errors, warnings)
- ocr_events.jsonl: OCR grounding results per page

Logs survive server restarts. Each line is a self-contained JSON object.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TELEMETRY_DIR = Path(os.environ.get("TELEMETRY_DIR", ".telemetry"))


class TelemetryLogger:
    """Append-only JSONL telemetry logger."""

    def __init__(self, log_dir: Path | None = None):
        self.log_dir = log_dir or TELEMETRY_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._run_log = self.log_dir / "pipeline_runs.jsonl"
        self._stage_log = self.log_dir / "stage_events.jsonl"
        self._ocr_log = self.log_dir / "ocr_events.jsonl"
        self._error_log = self.log_dir / "errors.jsonl"

    def log_run_start(self, job_id: str, document: str, pages: int, config: dict | None = None):
        self._append(self._run_log, {
            "event": "run_start",
            "job_id": job_id,
            "document": document,
            "pages": pages,
            "config": {
                "provider": config.get("llm_provider", "") if config else "",
                "model": config.get("vision_model", "") if config else "",
                "soa_only": config.get("soa_only", True) if config else True,
                "dpi": config.get("render_dpi", 150) if config else 150,
            },
            "ts": self._now(),
        })

    def log_run_end(self, job_id: str, status: str, tables: int, cells: int,
                    footnotes: int, confidence: float, duration_s: float,
                    warnings: int = 0, errors: list[str] | None = None):
        self._append(self._run_log, {
            "event": "run_end",
            "job_id": job_id,
            "status": status,
            "tables": tables,
            "cells": cells,
            "footnotes": footnotes,
            "confidence": round(confidence, 3),
            "duration_s": round(duration_s, 1),
            "warnings": warnings,
            "errors": errors or [],
            "ts": self._now(),
        })

    def log_stage(self, job_id: str, stage: str, table_id: str = "",
                  duration_s: float = 0, detail: str = "", level: str = "info"):
        self._append(self._stage_log, {
            "job_id": job_id,
            "stage": stage,
            "table_id": table_id,
            "duration_s": round(duration_s, 2),
            "detail": detail,
            "level": level,
            "ts": self._now(),
        })

    def log_ocr(self, job_id: str, page: int, words_found: int,
                grounded: int, ungrounded: int, error: str = ""):
        self._append(self._ocr_log, {
            "job_id": job_id,
            "page": page,
            "words_found": words_found,
            "grounded": grounded,
            "ungrounded": ungrounded,
            "error": error,
            "ts": self._now(),
        })

    def log_error(self, job_id: str, stage: str, error: str, traceback: str = ""):
        self._append(self._error_log, {
            "job_id": job_id,
            "stage": stage,
            "error": error,
            "traceback": traceback[:500],
            "ts": self._now(),
        })

    def get_recent_runs(self, limit: int = 20) -> list[dict]:
        """Read recent run events for dashboard display."""
        return self._read_tail(self._run_log, limit)

    def get_errors(self, limit: int = 50) -> list[dict]:
        """Read recent errors."""
        return self._read_tail(self._error_log, limit)

    def _append(self, path: Path, data: dict):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Telemetry write failed: {e}")

    def _read_tail(self, path: Path, limit: int) -> list[dict]:
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return [json.loads(l) for l in lines[-limit:] if l.strip()]
        except Exception:
            return []

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


# Global singleton
_telemetry: TelemetryLogger | None = None


def get_telemetry() -> TelemetryLogger:
    global _telemetry
    if _telemetry is None:
        _telemetry = TelemetryLogger()
    return _telemetry
