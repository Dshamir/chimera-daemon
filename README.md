# CHIMERA

**Cognitive History Integration & Memory Extraction Runtime Agent**

> *"Surface what you know but don't know you know — automatically, continuously, sovereignly."*

CHIMERA is a persistent local daemon that performs cognitive archaeology on your file system and AI conversation exports. It extracts patterns, correlates across sources, and surfaces "unknown knowns" — insights buried in your digital history.

## Features

- **File System Monitoring** — Watch directories for changes, extract content automatically
- **Multi-Format Extraction** — PDF, DOCX, MD, TXT, code files, images (OCR)
- **FAE Protocol** — Auto-detect and process AI conversation exports (Claude, ChatGPT, Gemini, Grok)
- **Semantic Search** — Query your knowledge base with natural language
- **Pattern Correlation** — Cross-source synthesis, entity merging, confidence scoring
- **Discovery Surfacing** — Automatically surface high-confidence patterns
- **Real-Time Dashboard** — Live monitoring with CPU/GPU stats, ETA, progress
- **Sovereignty First** — All processing local, no external API calls, your data stays yours

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure
chimera init

# Start daemon
chimera serve --dev

# In another terminal:
chimera status
chimera dashboard          # Live monitoring
chimera correlate --now    # Run correlation
chimera discoveries        # View discoveries
```

## Real-Time Dashboard

```bash
chimera dashboard
```

```
┌─────────────────────────────────────────────────────────────┐
│ * CHIMERA v0.1.0 | Jobs: 0 pending | Updated: 17:50:23      │
├─────────────────────────────────────────────────────────────┤
│ CPU: 12%  ████░░░░░░░    │  Patterns: 22,719                │
│ Memory: 8/16 GB          │  Discoveries: 14,617             │
│ GPU: RTX 4070 12%        │    relationship: 14,606          │
├──────────────────────────┼──────────────────────────────────┤
│ Current Operation        │  Entities Extracted              │
│ ⠋ Correlation            │  PERSON   ████████  12,345       │
│   Elapsed: 33s | ETA: 2m │  ORG      ████      5,678        │
│   ██████░░░░░░░░░░ 18%   │  TECH     ███       3,456        │
└──────────────────────────┴──────────────────────────────────┘
```

Features:
- Real CPU/Memory stats (psutil)
- NVIDIA GPU monitoring (nvidia-smi)
- Current operation with ETA and progress bar
- Patterns and discoveries from correlation
- Live feed of recent jobs

## What is Excavation?

**Excavation** = Complete cognitive archaeology

| Component | Scope |
|-----------|-------|
| **Files** | Local drives, documents, code, images (OCR) |
| **FAE** | AI conversation exports (Claude, ChatGPT, Gemini, Grok) |
| **Correlate** | Cross-source synthesis, unknown knowns |

```bash
chimera excavate              # Everything
chimera excavate --files      # Files only
chimera excavate --fae        # Conversations only
chimera fae "E:\AI Exports"   # Specific FAE path
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `serve` | Start daemon |
| `stop` | Stop daemon gracefully |
| `restart` | Restart daemon |
| `ping` | Quick status check (colored dot) |
| `status` | Show detailed status |
| `dashboard` | Real-time monitoring |
| `query <text>` | Semantic search |
| `discoveries` | List discoveries |
| `entities` | List entities |
| `patterns` | List patterns |
| `correlate` | Run correlation |
| `excavate` | Full excavation |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CHIMERA DAEMON                           │
├─────────────────────────────────────────────────────────────┤
│  Watcher → Queue → Extractors → Storage → Correlation       │
│                                                              │
│  Extractors: Docs | Code | Image | FAE                      │
│  Storage: SQLite (catalog) + ChromaDB (vectors)             │
│  Correlation: Entity Consolidation → Pattern Detection      │
│               → Discovery Surfacing                         │
│  API: REST (port 7777) + CLI + Dashboard                    │
└─────────────────────────────────────────────────────────────┘
```

```
chimera-daemon/
├── src/chimera/
│   ├── daemon.py           # Main orchestrator
│   ├── cli.py              # CLI commands
│   ├── telemetry.py        # Real-time dashboard
│   ├── extractors/         # Content extraction
│   ├── storage/            # SQLite + ChromaDB
│   ├── correlation/        # Intelligence layer
│   ├── integration/        # Claude/MCP integration
│   └── api/                # FastAPI server
└── tests/
```

## API Endpoints

```
GET  /api/v1/health           # Health check
GET  /api/v1/status           # Daemon status
GET  /api/v1/telemetry        # Comprehensive telemetry
GET  /api/v1/query?q=...      # Semantic search
GET  /api/v1/discoveries      # List discoveries
GET  /api/v1/entities         # List entities
POST /api/v1/excavate         # Trigger excavation
POST /api/v1/correlate/run    # Run correlation
GET  /api/v1/jobs/current     # Current operation
```

## Documentation

- [CLAUDE.md](./CLAUDE.md) — Development tracker & session logs
- [PRD](https://github.com/Dshamir/sif-knowledge-base/tree/main/projects/chimera-prd) — Full Product Requirements Document
- [A7.2 FAE Protocol](https://github.com/Dshamir/sif-knowledge-base/blob/main/amendments/A7.2-full-archaeology-excavation-protocol.md) — AI export detection and processing

## Status

**Version:** 0.1.0
**Status:** All Sprints Complete
**Python:** 3.11+

| Sprint | Focus | Status |
|--------|-------|--------|
| 0 | Foundation | Complete |
| 1 | Core Daemon | Complete |
| 2 | Extractors & Index | Complete |
| 3 | Correlation Engine | Complete |
| 4 | Integration & Polish | Complete |

## Requirements

- Python 3.11+
- NVIDIA GPU (optional, for faster embeddings)
- ~4GB disk space for vectors

## License

MIT

---

*"We do this right or we don't do it."*
