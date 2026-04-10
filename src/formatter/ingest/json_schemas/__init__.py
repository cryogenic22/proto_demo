"""
JSON Schema Plugins — pluggable detector + parser pairs for the JSON ingestor.

Each module exports a DETECTOR and PARSER instance. ALL_PLUGINS collects them
for registration by create_default_registry().
"""

from __future__ import annotations

from src.formatter.ingest.json_schemas.formatted_doc_ir import (
    DETECTOR as FORMATTED_DOC_DETECTOR,
    PARSER as FORMATTED_DOC_PARSER,
)
from src.formatter.ingest.json_schemas.protocol_ir import (
    DETECTOR as PROTOCOL_DETECTOR,
    PARSER as PROTOCOL_PARSER,
)
from src.formatter.ingest.json_schemas.usdm import (
    DETECTOR as USDM_DETECTOR,
    PARSER as USDM_PARSER,
)

# Order doesn't matter here — the registry sorts by detector.priority()
ALL_PLUGINS = [
    (USDM_DETECTOR, USDM_PARSER),
    (FORMATTED_DOC_DETECTOR, FORMATTED_DOC_PARSER),
    (PROTOCOL_DETECTOR, PROTOCOL_PARSER),
]
