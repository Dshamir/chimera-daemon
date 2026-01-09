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
│   ├── _bootstrap.py       # Windows bootstrap (event loop policy)
│   ├── daemon.py           # Main orchestrator
│   ├── cli.py              # CLI commands
│   ├── shell.py            # Interactive shell
│   ├── telemetry.py        # Real-time dashboard
│   ├── extractors/         # Content extraction
│   ├── storage/            # SQLite + ChromaDB
│   ├── correlation/        # Intelligence layer
│   ├── integration/        # Claude/MCP integration
│   └── api/                # FastAPI server
├── scripts/
│   ├── wsl-setup.sh        # WSL environment setup
│   └── chimera-wsl.bat     # Windows→WSL launcher
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

## Current Data (Example)

After excavating a developer's file system:

| Metric | Value |
|--------|-------|
| Files Indexed | 59,122 |
| Chunks Created | 916,675 |
| Entities Extracted | 6.6M (525K unique) |
| Patterns Detected | 23,133 |
| Discoveries Surfaced | 15,443 |
| Catalog DB | 3.3 GB |
| Vector DB | 9.7 GB |

## Deployment Options

### Option 1: Virtual Environment (Development)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install in development mode
pip install -e ".[dev]"

# Start daemon
chimera serve --dev
```

### Option 2: Docker (Production)

```bash
# Build container
docker build -t chimera-daemon .

# Run with data persistence
docker run -v ~/.chimera:/root/.chimera -p 7777:7777 chimera-daemon
```

### Option 3: WSL (Windows - Recommended)

For Windows users, running in WSL provides the most reliable experience:

```bash
# From Windows, launch WSL
wsl

# Navigate to project
cd /mnt/e/Software\ DEV/chimera-daemon

# Run setup script (first time only)
./scripts/wsl-setup.sh

# Activate and run
source venv-wsl/bin/activate
chimera serve --dev
```

Or use the Windows launcher:

```cmd
scripts\chimera-wsl.bat serve --dev
```

**Important - WSL Data Path:**

WSL uses `~/.chimera` (Linux path) for data. If you have existing data from Windows native mode at `C:\Users\YourName\.chimera`, the setup script will automatically create a symlink. If you need to do this manually:

```bash
# Link WSL path to existing Windows data
ln -s /mnt/c/Users/YourName/.chimera ~/.chimera
```

**Note:** These are separate deployment options. The venv is for local development, Docker is for production, WSL is for Windows users who want Linux-native behavior. They are NOT nested.

## Troubleshooting

### Common Issues

| Error | Solution |
|-------|----------|
| `Connection refused :7777` | Start daemon: `chimera serve --dev` |
| `database is locked` | Restart daemon, wait for operations to complete |
| `Daemon not responding` | Heavy operation in progress - check `chimera dashboard` |
| `Exit code 3221225477` (Windows) | Fixed in v0.1.0 - update to latest version |
| `WinError 10054` (Windows) | Fixed in v0.1.0 - startup race condition resolved |
| Dashboard shows all zeros (WSL) | Data path mismatch - run `ln -s /mnt/c/Users/YourName/.chimera ~/.chimera` |

### Windows-Specific Notes

CHIMERA is fully compatible with Windows. Key compatibility features:

- **Bootstrap Architecture**: Uses `_bootstrap.py` to set event loop policy BEFORE any imports
- **Event Loop**: Uses `WindowsSelectorEventLoopPolicy` for C extension compatibility (ChromaDB)
- **Startup**: 3-second delay before readiness polling to prevent socket storms
- **Paths**: Supports both Windows (`C:\Users\...`) and WSL (`/mnt/c/...`) paths
- **WSL Option**: For maximum stability, run via WSL (see deployment options above)

If you encounter Windows-specific issues, try running in WSL or ensure you have the latest version.

### Health Checks

```bash
chimera ping           # Quick check (colored dot)
chimera health         # Detailed health
chimera dashboard      # Live monitoring
```

### Database Issues

```bash
# Check database sizes
ls -lh ~/.chimera/*.db

# Verify integrity
sqlite3 ~/.chimera/catalog.db "PRAGMA integrity_check"

# Check journal mode (should be WAL)
sqlite3 ~/.chimera/catalog.db "PRAGMA journal_mode"
```

### Correlation Performance

With 6.6M entities, correlation takes ~3 minutes. The daemon remains responsive during correlation (ThreadPoolExecutor). Monitor progress with `chimera dashboard`.

## Status

**Version:** 0.1.0
**Python:** 3.10+ (WSL compatible)

| Sprint | Focus | Status |
|--------|-------|--------|
| 0 | Foundation | ✅ Complete |
| 1 | Core Daemon | ✅ Complete |
| 2 | Extractors & Index | ✅ Complete |
| 3 | Correlation Engine | ✅ Complete |
| 4 | Integration & Polish | ✅ Complete |
| 5 | Bug Fixes & Hardening | ✅ Complete |

### Recent Fixes (Sprint 5)

- Fixed Windows daemon crash (exit code 3221225477) - C extension compatibility
- Fixed startup race condition causing socket storms on Windows
- Fixed multimedia metadata storage (image, audio, GPS)
- Improved error handling (fail fast, not silent)
- Added integration tests for multimedia pipeline

## Requirements

- Python 3.10+
- NVIDIA GPU (optional, for faster embeddings)
- ~10GB disk space for vectors + catalog
- psutil (for system monitoring)

## License

MIT

---

*"Surface what you know but don't know you know."*
