# CHIMERA — Claude Development Tracker

## Project Overview

**CHIMERA**: Cognitive History Integration & Memory Extraction Runtime Agent  
**Purpose**: Persistent local daemon for cognitive archaeology (SIF A7/A7.1/A7.2 runtime)  
**Repository**: github.com/Dshamir/chimera-daemon  
**PRD**: github.com/Dshamir/sif-knowledge-base/tree/main/projects/chimera-prd

## Quick Commands

```bash
cd ~/chimera-daemon  # or wherever cloned
source venv/bin/activate
python -m chimera.cli --help
pytest tests/ -v
python -m chimera.daemon --dev
ruff check src/ && mypy src/
```

## Architecture

```
chimera-daemon/
├── src/chimera/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point (click)
│   ├── daemon.py           # Main daemon process
│   ├── config.py           # Configuration loader
│   ├── watcher.py          # File system watcher (watchdog)
│   ├── queue.py            # Job queue (asyncio + SQLite)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── server.py       # FastAPI application
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── query.py
│   │       ├── control.py
│   │       └── graph.py
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── document.py
│   │   ├── code.py
│   │   ├── image.py
│   │   └── fae.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── catalog.py
│   │   └── vectors.py
│   ├── correlation/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── discovery.py
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── hashing.py
├── tests/
├── docs/
├── pyproject.toml
├── .github/workflows/ci.yml
├── Dockerfile
├── .gitignore
├── .python-version
├── README.md
└── CLAUDE.md
```

## Current Sprint: 0 — Foundation

**Goal**: Project structure, dev environment, CI/CD  
**Status**: ✅ COMPLETE

## Task Board

### To Do
- [ ] S1-01: Full daemon integration
- [ ] S1-02: API server startup

### In Progress
_Sprint 0 complete. Sprint 1 ready._

### Done
- [x] S0-01: Create GitHub repository
- [x] S0-02: Python project structure
- [x] S0-03: pyproject.toml with dependencies
- [x] S0-04: pytest, coverage, linting setup
- [x] S0-05: Dockerfile
- [x] S0-06: GitHub Actions CI
- [x] S0-07: Validate core dependencies
- [x] S0-08: ~/.chimera directory structure
- [x] S0-09: Configuration loader
- [x] S0-10: Logging infrastructure
- [x] S0-11: README.md
- [x] S0-12: CLAUDE.md

## Session Protocol

### Starting a Session
1. Read this CLAUDE.md
2. Check task board for current focus
3. Review recent commits: `git log --oneline -10`
4. Run tests: `pytest tests/ -v`
5. Check lint: `ruff check src/`

### During Session
1. Update task status as you work
2. Commit frequently with conventional commits
3. Update tests alongside implementation
4. Document decisions in this file

### Ending a Session
1. Move completed tasks to Done
2. Update "Current Sprint" status
3. Commit and push all changes
4. Add session summary below

## Session Log

### 2026-01-05 — Session 1 (Sprint 0 Bootstrap)
- **Focus**: Project initialization
- **Completed**: Full Sprint 0 - repository, structure, all modules, tests, CI, Docker
- **Next**: Sprint 1 - Core Daemon integration
- **Notes**: Foundation complete. Ready for daemon integration.

## Key Decisions

| Date | Decision | Rationale |
|------|----------|----------|
| 2026-01-05 | SQLite + ChromaDB | Zero-config, embedded, reliable |
| 2026-01-05 | FastAPI + asyncio | Async-native, auto-docs |
| 2026-01-05 | E:\\ as primary source | Daniel's main drive |
| 2026-01-05 | FAE as extractor | AI exports treated as another file type |

## Dependencies Reference

See pyproject.toml for full list.

## Commit Conventions

```
feat(scope): add new feature
fix(scope): fix bug
test(scope): add tests
docs(scope): update documentation
refactor(scope): refactor code
chore(scope): maintenance tasks
```

Scopes: `daemon`, `api`, `cli`, `extractors`, `storage`, `correlation`, `config`, `fae`

## Links

- **PRD**: https://github.com/Dshamir/sif-knowledge-base/tree/main/projects/chimera-prd
- **A7.2 FAE**: https://github.com/Dshamir/sif-knowledge-base/blob/main/amendments/A7.2-full-archaeology-excavation-protocol.md
- **SIF Knowledge Base**: https://github.com/Dshamir/sif-knowledge-base

---

*"We do this right or we don't do it."*
