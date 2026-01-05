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
chimera --help
chimera serve --dev
pytest tests/ -v
ruff check src/ && mypy src/
```

## Architecture

```
chimera-daemon/
├── src/chimera/
│   ├── __init__.py
│   ├── cli.py              # CLI (click)
│   ├── daemon.py           # Main orchestrator
│   ├── config.py           # Configuration
│   ├── watcher.py          # File watcher (watchdog)
│   ├── queue.py            # Job queue (asyncio+SQLite)
│   ├── api/                # FastAPI server
│   ├── extractors/
│   │   ├── base.py         # Base extractor
│   │   ├── registry.py     # Extractor registry
│   │   ├── document.py     # PDF, DOCX, MD, TXT, HTML
│   │   ├── code.py         # Python, JS, TS, YAML, JSON
│   │   ├── image.py        # OCR (Tesseract)
│   │   ├── fae.py          # AI exports (Claude, ChatGPT)
│   │   ├── chunker.py      # Text/code chunking
│   │   ├── embeddings.py   # sentence-transformers
│   │   ├── entities.py     # spaCy NER
│   │   └── pipeline.py     # Extraction orchestrator
│   ├── storage/
│   │   ├── catalog.py      # SQLite (full schema)
│   │   └── vectors.py      # ChromaDB
│   ├── correlation/        # Sprint 3
│   └── utils/
├── tests/
├── deploy/
└── pyproject.toml
```

## Current Sprint: 2 — Extractors & Index

**Goal**: Document/code extraction, embeddings, entities  
**Status**: ✅ COMPLETE

## Task Board

### Sprint 2 - Done
- [x] S2-01: SQLite schema (full PRD spec)
- [x] S2-02: File catalog manager
- [x] S2-03: Base extractor interface
- [x] S2-04: PDF extractor (pypdf)
- [x] S2-05: DOCX extractor (python-docx)
- [x] S2-06: MD/TXT/HTML extractors
- [x] S2-07: Python extractor (AST)
- [x] S2-08: JS/TS/YAML/JSON extractors
- [x] S2-09: Image extractor (Tesseract OCR)
- [x] S2-10: Extractor registry
- [x] S2-11: Text chunker (500-1000 tokens)
- [x] S2-12: Code chunker (by functions/classes)
- [x] S2-13: Embedding generator (sentence-transformers)
- [x] S2-14: Entity extractor (spaCy + tech patterns)
- [x] S2-15: ChromaDB setup
- [x] S2-16: Extraction pipeline orchestrator
- [x] S2-17: Daemon integration
- [x] S2-18: FAE parsers (Claude, ChatGPT)
- [x] S2-19: Extractor tests
- [x] S2-20: Storage tests
- [x] S2-21: FAE tests

### Sprint 3 - Up Next
- [ ] S3-01: Entity consolidation
- [ ] S3-02: Co-occurrence matrix
- [ ] S3-03: Expertise detector
- [ ] S3-04: Relationship detector
- [ ] S3-05: Confidence scoring
- [ ] S3-06: Unknown knowns surfacer
- [ ] S3-07: Discoveries storage

## Sprint 2 Acceptance Criteria

```bash
# Start daemon
chimera serve --dev &

# Process a file
curl -X POST localhost:7777/api/v1/excavate

# Check status - should show indexed files
chimera status

# Query (returns chunks)
curl "localhost:7777/api/v1/query?q=test"

# >= 50 docs/minute extraction rate
```

## Extraction Pipeline Flow

```
File Detected
    │
    ▼
Job Queue (SQLite)
    │
    ▼
Extractor Registry → Get extractor by extension
    │
    ▼
Extract Content (PDF/DOCX/code/image)
    │
    ▼
Chunk (500-1000 tokens, semantic boundaries)
    │
    ▼
Extract Entities (spaCy + tech patterns)
    │
    ▼
Generate Embeddings (sentence-transformers, 384d)
    │
    ▼
Store (SQLite catalog + ChromaDB vectors)
```

## Supported File Types

| Type | Extensions | Extractor |
|------|------------|----------|
| Documents | pdf, docx, md, txt, html | document.py |
| Code | py, js, ts, jsx, tsx, yaml, json | code.py |
| Images | png, jpg, gif, bmp, tiff | image.py (OCR) |
| AI Exports | conversations.json | fae.py |

## Key Components

### ExtractionPipeline
```python
from chimera.extractors.pipeline import get_pipeline

pipeline = get_pipeline()
result = await pipeline.process_file(Path("document.pdf"))
print(f"Chunks: {result.chunk_count}, Entities: {result.entity_count}")
```

### CatalogDB
```python
from chimera.storage.catalog import CatalogDB

catalog = CatalogDB()
stats = catalog.get_stats()
print(f"Total files: {stats['total_files']}")
```

### VectorDB
```python
from chimera.storage.vectors import VectorDB

vectors = VectorDB()
results = vectors.query_text("documents", "thermal control")
```

## Session Log

### 2026-01-05 — Session 1 (Sprint 0)
- Created repository structure
- Set up pyproject.toml, CI, Docker

### 2026-01-05 — Session 2 (Sprint 1)
- Full daemon orchestrator
- File watcher, job queue, API server
- CLI commands

### 2026-01-05 — Session 3 (Sprint 2)
- Complete extraction pipeline
- All document/code/image extractors
- Chunking, embeddings, entity extraction
- SQLite + ChromaDB storage
- FAE parsers for Claude & ChatGPT
- Full test coverage

## Links

- **PRD**: https://github.com/Dshamir/sif-knowledge-base/tree/main/projects/chimera-prd
- **A7.2 FAE**: https://github.com/Dshamir/sif-knowledge-base/blob/main/amendments/A7.2-full-archaeology-excavation-protocol.md
- **SIF Knowledge Base**: https://github.com/Dshamir/sif-knowledge-base

---

*"We do this right or we don't do it."*
