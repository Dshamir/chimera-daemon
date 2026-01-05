# CHIMERA — Claude Development Tracker

## Project Overview

**CHIMERA**: Cognitive History Integration & Memory Extraction Runtime Agent  
**Purpose**: Persistent local daemon for cognitive archaeology (SIF A7/A7.1/A7.2 runtime)  
**Repository**: github.com/Dshamir/chimera-daemon  
**PRD**: github.com/Dshamir/sif-knowledge-base/tree/main/projects/chimera-prd

## Quick Commands

```bash
cd ~/chimera-daemon
pip install -e ".[dev]"
chimera init
chimera serve --dev
pytest tests/ -v
```

## Architecture

```
chimera-daemon/
├── src/chimera/
│   ├── daemon.py           # Main orchestrator
│   ├── cli.py              # CLI (click)
│   ├── config.py           # Configuration
│   ├── watcher.py          # File watcher
│   ├── queue.py            # Job queue
│   ├── api/                # FastAPI server
│   ├── extractors/         # Content extraction
│   │   ├── pipeline.py     # Extraction orchestrator
│   │   ├── document.py     # PDF, DOCX, MD, TXT
│   │   ├── code.py         # Python, JS, YAML
│   │   ├── fae.py          # AI conversation exports
│   │   ├── chunker.py      # Text/code chunking
│   │   ├── embeddings.py   # sentence-transformers
│   │   └── entities.py     # spaCy NER
│   ├── storage/
│   │   ├── catalog.py      # SQLite
│   │   └── vectors.py      # ChromaDB
│   ├── correlation/        # Intelligence layer
│   │   ├── engine.py       # Main orchestrator
│   │   ├── entities.py     # Entity consolidation
│   │   ├── patterns.py     # Pattern detection
│   │   └── discovery.py    # Unknown knowns surfacing
│   └── utils/
└── tests/
```

## Current Sprint: 3 — Correlation Engine

**Goal**: Cross-source correlation, pattern detection, discoveries  
**Status**: ✅ COMPLETE

## Task Board

### Sprint 3 - Done
- [x] S3-01: Entity consolidation (merge variants)
- [x] S3-02: Co-occurrence matrix
- [x] S3-03: Expertise detector (domain vocabulary)
- [x] S3-04: Relationship detector (PERSON + ORG/PROJECT)
- [x] S3-05: Workflow detector (naming patterns)
- [x] S3-06: Tech stack detector
- [x] S3-07: Confidence scoring algorithm
- [x] S3-08: Unknown knowns surfacer
- [x] S3-09: Discoveries storage
- [x] S3-10: Confirm/dismiss feedback
- [x] S3-11: Graph node export for SIF
- [x] S3-12: API endpoints for discoveries
- [x] S3-13: Correlation tests

### Sprint 4 - Up Next
- [ ] S4-01: Full semantic search API
- [ ] S4-02: CLI query command
- [ ] S4-03: CLI discoveries commands
- [ ] S4-04: Graph sync to sif-knowledge-base
- [ ] S4-05: Claude Code integration

## Correlation Engine Flow

```
Indexed Content (SQLite + ChromaDB)
    │
    ▼
┌───────────────────────────────┐
│  ENTITY CONSOLIDATION        │
│  "Gabriel" + "Gabe" → gabriel│
└─────────────┬─────────────────┘
              │
              ▼
┌───────────────────────────────┐
│  CO-OCCURRENCE MATRIX        │
│  Which entities appear together│
└─────────────┬─────────────────┘
              │
              ▼
┌───────────────────────────────┐
│  PATTERN DETECTION           │
│  • Expertise (domain vocab)  │
│  • Relationships (co-occur)  │
│  • Workflows (naming)        │
│  • Tech stack                │
└─────────────┬─────────────────┘
              │
              ▼
┌───────────────────────────────┐
│  DISCOVERY SURFACING         │
│  confidence >= 0.7           │
│  sources >= 2                │
│  NOT explicitly stated       │
└─────────────┬─────────────────┘
              │
              ▼
       💡 DISCOVERIES
       (Unknown Knowns)
```

## Confidence Algorithm

```python
confidence = (
    0.35 * evidence_score +      # log10(count + 1) / 2
    0.25 * diversity_score +     # sources / 5
    0.20 * time_score +          # days_span / 365
    0.20 * recency_score         # 1 - (days_since_last / 180)
)
```

## Discovery Types

| Type | Detection Method |
|------|------------------|
| **expertise** | Domain vocabulary density (ML, DevOps, medical...) |
| **relationship** | PERSON + ORG/PROJECT co-occurrence |
| **workflow** | File naming patterns (date prefix, versioning) |
| **skill** | Tech stack profile across files |

## API Endpoints (Sprint 3)

```
GET  /api/v1/query?q=...           # Semantic search
GET  /api/v1/file/{id}             # File details + entities
GET  /api/v1/discoveries           # List discoveries
GET  /api/v1/discoveries/{id}      # Discovery details
POST /api/v1/discoveries/{id}/feedback  # Confirm/dismiss
GET  /api/v1/entities              # List consolidated entities
GET  /api/v1/patterns              # List detected patterns
POST /api/v1/correlate             # Queue correlation job
POST /api/v1/correlate/run         # Run correlation now
GET  /api/v1/correlation/stats     # Correlation statistics
```

## Usage Examples

```bash
# Run correlation
curl -X POST localhost:7777/api/v1/correlate/run

# Get discoveries
curl localhost:7777/api/v1/discoveries

# Confirm a discovery
curl -X POST localhost:7777/api/v1/discoveries/disc_001/feedback \
  -d '{"action": "confirm", "notes": "Accurate"}'

# Search
curl "localhost:7777/api/v1/query?q=thermal+control"

# Get correlation stats
curl localhost:7777/api/v1/correlation/stats
```

## Session Log

### 2026-01-05 — Sprint 0
- Repository structure, CI/CD, Docker

### 2026-01-05 — Sprint 1
- Daemon, watcher, queue, API server

### 2026-01-05 — Sprint 2
- Extraction pipeline, all extractors
- Chunking, embeddings, entities
- SQLite + ChromaDB storage

### 2026-01-05 — Sprint 3
- Entity consolidation with alias resolution
- Co-occurrence matrix for relationships
- Pattern detection: expertise, relationships, workflow, tech stack
- Discovery surfacing with confidence scoring
- Confirm/dismiss feedback system
- Graph node export for SIF integration
- Full API for discoveries and patterns

## Key Decisions

| Date | Decision | Rationale |
|------|----------|----------|
| 2026-01-05 | Name aliases | Consolidate Mike/Michael, Bob/Robert |
| 2026-01-05 | Domain vocab | 6 domains with 10-15 terms each |
| 2026-01-05 | 0.7 confidence | Threshold for unknown knowns |
| 2026-01-05 | 2+ sources | Multi-source requirement |

---

*"Surface what you know but don't know you know."*
