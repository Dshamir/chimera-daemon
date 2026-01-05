# CHIMERA — Claude Development Tracker

## Project Overview

**CHIMERA**: Cognitive History Integration & Memory Extraction Runtime Agent  
**Purpose**: Persistent local daemon for cognitive archaeology (SIF A7/A7.1/A7.2 runtime)  
**Repository**: github.com/Dshamir/chimera-daemon  
**PRD**: github.com/Dshamir/sif-knowledge-base/tree/main/projects/chimera-prd

## Quick Commands

```bash
cd ~/chimera-daemon  # or wherever cloned
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
│   ├── cli.py              # CLI entry point (click)
│   ├── daemon.py           # Main daemon orchestrator
│   ├── config.py           # Configuration loader
│   ├── watcher.py          # File system watcher (watchdog)
│   ├── queue.py            # Job queue (asyncio + SQLite)
│   ├── api/
│   │   ├── server.py       # FastAPI application
│   │   └── routes/         # API endpoints
│   ├── extractors/         # Sprint 2
│   ├── storage/            # Sprint 2
│   ├── correlation/        # Sprint 3
│   └── utils/
├── tests/
├── deploy/
│   ├── chimera.service    # Systemd service
│   └── install.sh         # Install script
├── pyproject.toml
├── Dockerfile
└── CLAUDE.md
```

## Current Sprint: 1 — Core Daemon

**Goal**: Daemon runs, watches files, API responds  
**Status**: ✅ COMPLETE

## Task Board

### Sprint 1 - Done
- [x] S1-01: Daemon entry point
- [x] S1-02: File watcher (watchdog)
- [x] S1-03: Job queue (asyncio+SQLite)
- [x] S1-04: FastAPI server
- [x] S1-05: /health endpoint
- [x] S1-06: /status endpoint
- [x] S1-07: Graceful shutdown
- [x] S1-08: Systemd service file
- [x] S1-09: Daemon tests
- [x] S1-10: Watcher tests

### Sprint 2 - Up Next
- [ ] S2-01: SQLite schema
- [ ] S2-02: File catalog manager
- [ ] S2-03: Base extractor interface
- [ ] S2-04: PDF extractor
- [ ] S2-05: DOCX extractor
- [ ] S2-06: Embedding generator
- [ ] S2-07: ChromaDB setup

## Sprint 1 Acceptance Criteria

```bash
# Start daemon
chimera serve --dev &

# Health check
curl localhost:7777/api/v1/health
# {"status": "healthy", "version": "0.1.0"}

# Status check
chimera status
# Shows running status, uptime, stats

# File detection (create file in watched dir)
touch ~/Documents/test.txt
# Log shows: File created: /home/user/Documents/test.txt
```

## Session Protocol

### Starting a Session
1. Read this CLAUDE.md
2. Check task board for current focus
3. Review recent commits: `git log --oneline -10`
4. Run tests: `pytest tests/ -v`
5. Check lint: `ruff check src/`

### Ending a Session
1. Move completed tasks to Done
2. Update "Current Sprint" status
3. Commit and push all changes
4. Add session summary below

## Session Log

### 2026-01-05 — Session 1 (Sprint 0)
- Created repository structure
- Set up pyproject.toml, CI, Docker

### 2026-01-05 — Session 2 (Sprint 1)
- Implemented full daemon orchestrator
- File watcher with debouncing and FAE detection
- Async job queue with SQLite persistence
- FastAPI server with health/status/control endpoints
- Full CLI with all commands
- Systemd service and install script
- Tests for daemon, API, watcher, queue

## Key Decisions

| Date | Decision | Rationale |
|------|----------|----------|
| 2026-01-05 | SQLite + ChromaDB | Zero-config, embedded, reliable |
| 2026-01-05 | FastAPI + asyncio | Async-native, auto-docs |
| 2026-01-05 | E:\\ as primary source | Daniel's main drive |
| 2026-01-05 | FAE as extractor | AI exports treated as another file type |
| 2026-01-05 | Global daemon singleton | Allows API routes to access daemon state |

## API Endpoints

```
GET  /                        # Root info
GET  /api/v1/health           # Health check
GET  /api/v1/status           # Daemon status
GET  /api/v1/jobs             # Job queue stats
GET  /api/v1/query?q=...      # Semantic search (Sprint 2)
POST /api/v1/excavate         # Trigger excavation
POST /api/v1/fae              # Trigger FAE
POST /api/v1/correlate        # Trigger correlation
GET  /api/v1/discoveries      # List discoveries (Sprint 3)
GET  /api/v1/graph/export     # Export graph (Sprint 4)
```

## CLI Commands

```bash
chimera serve [--dev] [--host] [--port]  # Start daemon
chimera status                            # Show status
chimera health                            # Health check
chimera query "search term"               # Search
chimera excavate [--files] [--fae]        # Run excavation
chimera fae [path] [--provider]           # Process AI exports
chimera discoveries                       # List discoveries
chimera config                            # Show config
chimera init                              # Initialize
chimera jobs                              # Queue stats
chimera logs                              # View logs
```

## Links

- **PRD**: https://github.com/Dshamir/sif-knowledge-base/tree/main/projects/chimera-prd
- **A7.2 FAE**: https://github.com/Dshamir/sif-knowledge-base/blob/main/amendments/A7.2-full-archaeology-excavation-protocol.md
- **SIF Knowledge Base**: https://github.com/Dshamir/sif-knowledge-base

---

*"We do this right or we don't do it."*
