# Protocol Workspace UI — Branch Integration Guide

## Overview

This branch adds a Protocol Workspace UI and Knowledge Element (KE) persistence layer to ProtoExtract. The protocol is now a first-class data object that can be navigated, explored, and persisted to a Neo4j knowledge graph.

**New code: ~2,100 lines** (471 backend + 1,674 frontend)

---

## Architecture

### Backend: Protocol + KE Layer

```
src/models/protocol.py      — Protocol, KnowledgeElement, SectionNode models
src/persistence/__init__.py  — Package init
src/persistence/ke_store.py  — Abstract KEStore + JsonKEStore + Neo4jKEStore
api/main.py                  — 6 new endpoints (appended to existing)
```

**Protocol model** (`src/models/protocol.py`)
- `Protocol` — composes metadata, sections, tables, procedures, budget lines, and KEs
- `KnowledgeElement` — atomic unit of the protocol graph, with type, status, version, relationships
- `SectionNode` — recursive section tree that maps to KE types
- `KEType` enum: PROTOCOL, SECTION, SOA_TABLE, PROCEDURE, FOOTNOTE, INCLUSION_CRITERIA, etc.
- `KEStatus` enum: DRAFT, VERIFIED, LOCKED
- `Protocol.to_ke_graph()` — converts the protocol to a flat list of KEs for Neo4j

**KE persistence** (`src/persistence/ke_store.py`)
- `KEStore` — abstract base with save_protocol, load_protocol, list_protocols, save/get KEs
- `JsonKEStore` — file-based default, stores in `data/protocols/`
- `Neo4jKEStore` — MERGE-based Neo4j persistence, activated when `NEO4J_URI` env var is set
- `create_ke_store()` — factory that returns Neo4j if configured, else JSON fallback

**New API endpoints** (added to `api/main.py`)
```
GET  /api/protocols                              — List all stored protocols
GET  /api/protocols/{id}                         — Full protocol data
GET  /api/protocols/{id}/sections                — Section tree
GET  /api/protocols/{id}/sections/{number}       — Single section content
GET  /api/protocols/{id}/budget                  — Budget line items
GET  /api/protocols/{id}/knowledge-elements      — KEs (optional ?ke_type= filter)
```

### Frontend: Protocol Workspace

```
web/src/app/protocols/page.tsx                   — Protocol Library (grid of cards)
web/src/app/protocols/[protocolId]/page.tsx       — Protocol Workspace (3-panel)
web/src/app/protocols/[protocolId]/budget/page.tsx — Site Budget module
web/src/app/quality/page.tsx                      — Quality Dashboard

web/src/components/protocol/SectionTree.tsx       — Recursive collapsible section tree
web/src/components/protocol/SectionContent.tsx    — HTML content renderer
web/src/components/protocol/ProtocolMetaCard.tsx  — Metadata card
web/src/components/protocol/ProcedureTable.tsx    — Procedure list with CPT codes
web/src/components/protocol/BudgetTable.tsx       — Budget table with category grouping
web/src/components/protocol/KEBadge.tsx           — KE status badge (DRAFT/VERIFIED/LOCKED)
web/src/components/ui/Tabs.tsx                    — Reusable tab bar component
```

**Updated files:**
- `web/src/lib/api.ts` — 8 new interfaces + 6 new API functions
- `web/src/components/layout/SideNav.tsx` — New navigation structure
- `web/src/app/globals.css` — Section content typography styles

---

## Page Map

| Route | View | Purpose |
|-------|------|---------|
| `/protocols` | Protocol Library | Browse all digitized protocols |
| `/protocols/{id}` | Protocol Workspace | Navigate sections, view tables, procedures, KEs |
| `/protocols/{id}/budget` | Site Budget | Per-patient cost estimate with CPT codes |
| `/quality` | Quality Dashboard | Cross-protocol accuracy metrics |
| `/` | Upload Protocol | Existing upload page |
| `/history` | Extraction Jobs | Existing job history |

---

## KE Persistence Hook — How to Connect

### Default: JSON file storage

Works out of the box. Protocols are stored as JSON in `data/protocols/`. No configuration needed.

### Neo4j: Set environment variables

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

When these are set, `create_ke_store()` returns a `Neo4jKEStore` that writes:
- `(:Protocol)` nodes with metadata properties
- `(:KnowledgeElement)` nodes with type, status, version, content
- `(:Protocol)-[:HAS_KE]->(:KnowledgeElement)` relationships
- Inter-KE relationships via `BELONGS_TO`, `CONTAINS`, `INFORMS`, etc.

### Linking to existing KE system

The `Neo4jKEStore` is designed to be subclassed or replaced. To connect to your existing knowledge graph:

1. Subclass `KEStore` and implement the 5 abstract methods
2. Map `KEType` enum values to your existing node labels
3. Map `KERelationship.rel_type` to your existing relationship types
4. Override `create_ke_store()` or add your implementation to the factory

The key design decision: the `KnowledgeElement` model carries a `ke_id` that follows the pattern `{protocol_id}:{ke_type}:{identifier}`. This can be mapped to your existing ID scheme.

---

## Design System

**Colors (Pfizer-inspired)**
- Primary: `#0093D0` (Pacific Blue) — headers, active states, links
- Secondary: `#0070BF` (French Blue) — section headings, sidebar branding
- Accent: `#00AFF0` (Cerulean) — hover states, secondary actions
- Background: `#F8FAFC` — page background, side panels
- Surface: `#FFFFFF` — cards, content areas
- Success: `#00A950`, Warning: `#F8971D`, Danger: `#CC292B`

**Typography**
- Headings: Inter 600 (semibold)
- Body: Inter 400 (regular)
- Code/numbers: JetBrains Mono 400

**Layout patterns**
- 3-panel workspace: left (260px) | center (flex) | right (300px)
- Card-based dashboard views with KPI cards at top
- Data tables with sticky headers, hover states, subtle alternating rows

---

## What's NOT included (for future phases)

- PDF viewer overlay (needs `react-pdf` dependency)
- Real-time WebSocket processing updates
- Inline annotation editing (SoA cell correction workflow)
- ICF / CTA / CSR module views
- User authentication
- Protocol version diffing UI
