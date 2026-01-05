# CHIMERA — Claude Development Tracker

## Project Overview

**CHIMERA**: Cognitive History Integration & Memory Extraction Runtime Agent  
**Purpose**: Persistent local daemon for cognitive archaeology (SIF A7/A7.1/A7.2)  
**Repository**: github.com/Dshamir/chimera-daemon  
**PRD**: github.com/Dshamir/sif-knowledge-base/tree/main/projects/chimera-prd

## Quick Start

```bash
cd ~/chimera-daemon
pip install -e ".[dev]"
chimera init
chimera serve --dev

# In another terminal:
chimera status
chimera correlate --now
chimera discoveries
```

## Architecture

```
chimera-daemon/
├── src/chimera/
│   ├── daemon.py           # Main orchestrator
│   ├── cli.py              # Full CLI (Sprint 4)
│   ├── extractors/         # Content extraction
│   ├── storage/            # SQLite + ChromaDB
│   ├── correlation/        # Intelligence layer
│   │   ├── engine.py       # Orchestrator
│   │   ├── entities.py     # Consolidation
│   │   ├── patterns.py     # Detection
│   │   └── discovery.py    # Unknown knowns
│   ├── integration/        # External integrations
│   │   ├── claude.py       # Claude context builder
│   │   └── mcp.py          # MCP server
│   └── api/                # FastAPI server
└── tests/
```

## All Sprints Complete ✅

| Sprint | Focus | Status |
|--------|-------|--------|
| 0 | Foundation | ✅ |
| 1 | Core Daemon | ✅ |
| 2 | Extractors & Index | ✅ |
| 3 | Correlation Engine | ✅ |
| 4 | Integration & Polish | ✅ |

## Sprint 4 Deliverables

### Enhanced CLI Commands

```bash
# Search with rich output
chimera query "thermal control" --limit 10 --min-score 0.6

# List discoveries with filtering
chimera discoveries --type expertise --min-confidence 0.8

# Provide feedback
chimera feedback disc_001 --action confirm --notes "Accurate"

# List entities
chimera entities --type PERSON --min-occurrences 3

# List patterns
chimera patterns --type expertise

# Run correlation
chimera correlate --now

# Graph export
chimera graph-export -o discoveries.yaml
chimera graph-sync --repo Dshamir/sif-knowledge-base --dry-run

# Claude integration
chimera ask "What do I know about thermal systems?"
chimera summary
```

### Claude Integration

```python
from chimera.integration.claude import ClaudeContextBuilder

builder = ClaudeContextBuilder()
context = builder.build_context("thermal control systems")

# Get XML for Claude
print(context.to_xml())

# Get Markdown
print(context.to_markdown())

# Get system prompt addition
print(builder.get_system_prompt_addition())
```

### MCP Server

```python
from chimera.integration.mcp import ChimeraMCPServer

server = ChimeraMCPServer()

# Get available tools
tools = server.get_tools()
# chimera_search, chimera_discoveries, chimera_entities, chimera_file

# Handle tool call
result = await server.handle_tool_call("chimera_search", {
    "query": "machine learning",
    "limit": 5,
})

# Get MCP manifest
manifest = server.to_mcp_manifest()
```

### Graph Sync API

```bash
# Export discoveries as SIF nodes
curl localhost:7777/api/v1/graph/export

# Sync to GitHub (dry run)
curl -X POST localhost:7777/api/v1/graph/sync \
  -d '{"repo": "Dshamir/sif-knowledge-base", "dry_run": true}'
```

## Full CLI Reference

| Command | Description |
|---------|-------------|
| `serve` | Start daemon |
| `status` | Show status |
| `health` | Check health |
| `init` | Initialize config |
| `config` | Show config |
| `query <text>` | Semantic search |
| `discoveries` | List discoveries |
| `feedback <id>` | Confirm/dismiss discovery |
| `entities` | List entities |
| `patterns` | List patterns |
| `correlate` | Run correlation |
| `excavate` | Full excavation |
| `fae` | Process AI exports |
| `jobs` | Queue stats |
| `logs` | View logs |
| `graph-export` | Export to YAML/JSON |
| `graph-sync` | Sync to GitHub |
| `ask <question>` | Get Claude context |
| `summary` | Knowledge summary |

## API Endpoints

```
GET  /api/v1/health
GET  /api/v1/status
GET  /api/v1/query?q=...
GET  /api/v1/file/{id}
GET  /api/v1/discoveries
POST /api/v1/discoveries/{id}/feedback
GET  /api/v1/entities
GET  /api/v1/patterns
POST /api/v1/excavate
POST /api/v1/fae
POST /api/v1/correlate
POST /api/v1/correlate/run
GET  /api/v1/correlation/stats
GET  /api/v1/jobs
GET  /api/v1/graph/export
POST /api/v1/graph/sync
GET  /api/v1/graph/status
```

## Session Log

### 2026-01-05 — Sprint 0-1
- Repository, daemon, watcher, queue, API

### 2026-01-05 — Sprint 2
- Extractors, chunking, embeddings, storage

### 2026-01-05 — Sprint 3
- Correlation engine, patterns, discoveries

### 2026-01-05 — Sprint 4
- Enhanced CLI with rich output
- Claude context builder
- MCP server implementation
- Graph export/sync
- Full test coverage

## Key Files

| File | Purpose |
|------|--------|
| `daemon.py` | Main orchestrator |
| `cli.py` | Full CLI implementation |
| `extractors/pipeline.py` | Extraction orchestrator |
| `correlation/engine.py` | Correlation orchestrator |
| `integration/claude.py` | Claude context builder |
| `integration/mcp.py` | MCP server |

---

## CHIMERA is Ready

```
┌───────────────────────────────────────────┐
│  Files → Extract → Chunk → Embed → Store  │
│                    ↓                        │
│           Consolidate Entities             │
│                    ↓                        │
│            Detect Patterns                 │
│                    ↓                        │
│          Surface Discoveries               │
│                    ↓                        │
│         💡 UNKNOWN KNOWNS 💡                │
└───────────────────────────────────────────┘
```

*"Surface what you know but don't know you know."*
