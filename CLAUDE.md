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
│   ├── telemetry.py        # Real-time dashboard
│   ├── extractors/         # Content extraction
│   │   ├── image.py        # EXIF, GPS, thumbnails, AI vision
│   │   └── audio.py        # Audio metadata, transcription
│   ├── ai/                 # AI integrations
│   │   └── vision.py       # OpenAI, Claude, BLIP-2 vision
│   ├── storage/            # SQLite + ChromaDB
│   ├── correlation/        # Intelligence layer
│   │   ├── engine.py       # Orchestrator (ThreadPoolExecutor)
│   │   ├── entities.py     # Consolidation
│   │   ├── patterns.py     # Detection
│   │   └── discovery.py    # Unknown knowns
│   ├── integration/        # External integrations
│   │   ├── claude.py       # Claude context builder
│   │   └── mcp.py          # MCP server
│   ├── usb/                # USB excavation
│   │   ├── excavator.py    # USB device scanning
│   │   └── telemetry.py    # Standalone USB telemetry
│   ├── gpu/                # GPU utilities
│   │   └── vectors.py      # GPU-accelerated embeddings
│   ├── sync/               # Graph sync utilities
│   │   └── discovery.py    # Discovery sync
│   └── api/                # FastAPI server
├── usb-package/            # Standalone USB excavator
└── tests/
```

## Current Data Statistics

| Metric | Value |
|--------|-------|
| Files Indexed | 59,122 |
| Content Size | 1.74 GB |
| Chunks Created | 916,675 |
| Raw Entities | 6,607,007 |
| Unique Entities | 525,589 (92% dedup) |
| Patterns Detected | 23,133 |
| Discoveries | 15,443 |
| Vector DB Size | 9.7 GB |
| Catalog DB Size | 3.3 GB |

## Sprint Status

| Sprint | Focus | Status |
|--------|-------|--------|
| 0 | Foundation | ✅ Complete |
| 1 | Core Daemon | ✅ Complete |
| 2 | Extractors & Index | ✅ Complete |
| 3 | Correlation Engine | ✅ Complete |
| 4 | Integration & Polish | ✅ Complete |
| 5 | Bug Fixes & Hardening | ✅ Complete |

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
| `stop` | Stop daemon gracefully |
| `restart` | Restart daemon (stop + start) |
| `ping` | Quick status check (● green/red dot) |
| `status` | Show status (with ● indicator) |
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

### Daemon Control Commands

```bash
# Quick status check (colored dot)
chimera ping
# Output: ● Daemon running (green) or ● Daemon stopped (red)

# Stop running daemon (with spinner)
chimera stop

# Restart daemon (stops if running, then starts)
chimera restart --dev

# Status shows colored dot indicator
chimera status
# Output: ● CHIMERA Status (green dot if running)
```

### Real-Time Telemetry Dashboard

```bash
# Launch live dashboard (like htop for CHIMERA)
chimera dashboard

# Custom refresh rate
chimera dashboard --refresh 0.5
```

Dashboard panels:

| Panel | Content |
|-------|---------|
| **CPU** | Real CPU usage with progress bar (via psutil) |
| **Memory** | RAM usage, vectors/catalog size |
| **GPU** | NVIDIA GPU utilization, VRAM (via nvidia-smi) |
| **Extraction Velocity** | Files/min, chunks/min with sparklines |
| **Entities Extracted** | Breakdown by type (PERSON, ORG, TECH, etc.) |
| **Correlation Results** | Patterns count + Discoveries by type |
| **Current Operation** | Running job with elapsed time, ETA, progress bar |
| **Job Queue** | Pending jobs, processed count, correlations run |
| **Storage** | Catalog DB size, vectors size, total |
| **Live Feed** | Recent jobs with timestamps and status |

**Current Operation Features:**
- Shows CLI operations (`chimera correlate --now` shows `[CLI: --now]`)
- ETA calculation based on historical timing
- Progress bar during long operations
- Spinner animation for active operations

### Telemetry Features

All commands now include:
- **Status dots**: Green ● (running) or Red ● (stopped)
- **Spinners**: Progress indicators during API calls
- **Error handling**: Clear error messages with details
- **Progress feedback**: Visual confirmation of actions

```bash
# Example: excavate with telemetry
chimera excavate
# ● Excavation
#   ✓ Files
#   ✓ FAE exports
#   ✓ Correlation
# ⠋ Queueing excavation job...
# ✓ Excavation started
#   Job ID: abc123
```

## API Endpoints

### Core Endpoints
```
GET  /api/v1/health              # Health check
GET  /api/v1/status              # Daemon status and stats
POST /api/v1/shutdown            # Graceful shutdown
```

### Search & Query
```
GET  /api/v1/query?q=...         # Semantic search
GET  /api/v1/file/{id}           # Get file details
GET  /api/v1/discoveries         # List discoveries
POST /api/v1/discoveries/{id}/feedback  # Confirm/dismiss
GET  /api/v1/entities            # List entities
GET  /api/v1/patterns            # List patterns
```

### Operations
```
POST /api/v1/excavate            # Trigger full excavation
POST /api/v1/fae                 # Process AI exports
POST /api/v1/correlate           # Queue correlation job
POST /api/v1/correlate/run       # Run correlation synchronously
GET  /api/v1/correlation/stats   # Correlation statistics
```

### Jobs & Telemetry
```
GET  /api/v1/jobs                # Job queue stats
GET  /api/v1/jobs/current        # Currently running job
GET  /api/v1/jobs/recent?limit=N # Recent job history
GET  /api/v1/telemetry           # Comprehensive telemetry (for dashboard)
```

### Graph Sync
```
GET  /api/v1/graph/export        # Export as SIF nodes
POST /api/v1/graph/sync          # Sync to GitHub
GET  /api/v1/graph/status        # Sync status
```

### Telemetry Response Structure

```json
{
  "status": { "version", "running", "uptime_seconds", "stats", "catalog" },
  "system": { "cpu_percent", "memory_used_gb", "memory_total_gb" },
  "gpu": { "available", "device", "utilization_percent", "memory_used_gb" },
  "current_job": { "type", "elapsed_seconds", "eta_seconds", "details" },
  "storage": { "catalog_mb", "jobs_db_mb", "vectors_gb" },
  "patterns_detected": 22719,
  "entities_by_type": { "PERSON": 1234, "ORG": 567, ... },
  "discoveries_by_type": { "relationship": 14606, "expertise": 6, ... },
  "top_discoveries": [{ "id", "type", "title", "confidence", "status" }]
}
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

### 2026-01-06 — Bug Fixes (Excavation & Correlation)

#### Issue 1: Excavation Not Working

**Symptom:** `chimera excavate` queued a job but no files were processed.

**Root Cause:** Payload mismatch between API endpoint and job processor.
- `control.py` created job with `payload={"scope": {...}, "type": "excavate"}`
- `daemon.py` expected `payload.get("path")` → got empty string
- `Path("").exists()` = False → job silently exited

**Fix:**
- Changed `/api/v1/excavate` to use `JobType.BATCH_EXTRACTION`
- Added `_process_batch_extraction()` method that discovers files from configured sources
- Added helper methods: `_discover_source_files()`, `_should_include_file()`, `_discover_fae_exports()`

**Files Modified:**
- `src/chimera/api/routes/control.py` — Use BATCH_EXTRACTION job type
- `src/chimera/daemon.py` — Add batch extraction handler and file discovery

#### Issue 2: File Watcher Threading Crash

**Symptom:**
```
RuntimeError: no running event loop
coroutine 'ChimeraDaemon._enqueue_job' was never awaited
```

**Root Cause:** Watchdog runs callbacks in a separate thread. `asyncio.create_task()` requires an event loop in the current thread.

**Fix:** Use `asyncio.run_coroutine_threadsafe()` to schedule coroutine on main event loop.

**File Modified:** `src/chimera/daemon.py:128-153`

#### Issue 3: Correlation Produces 0 Discoveries Despite Patterns

**Symptom:**
```
Detected 2 patterns
Stored 0 discoveries
Surfaced 0 discoveries
```

**Root Cause:** Discovery filtering in `_pattern_to_discovery()`:
```python
if pattern.confidence < self.min_confidence:  # 0.7
    return None
if source_count < self.min_sources:  # 2
    return None
```

Problems:
1. Patterns created at confidence 0.3+ but discoveries need 0.7+
2. Workflow patterns never set `source_files` → `source_count = 0`

**Fix:** Added `source_files=data["file_ids"]` to workflow patterns.

**File Modified:** `src/chimera/correlation/patterns.py:241-297`

#### Issue 4: Co-occurrence Matrix Hangs on Large Entity Sets

**Symptom:** With 516K unique entities, `build_co_occurrence_matrix()` hangs building O(n²) pairs (~266 billion).

**Root Cause:** No size limits on entity count or pair generation.

**Fix:** Added configurable limits:
- `max_entities=50000` — Limits entities (prioritized by occurrence count)
- `max_pairs_per_file=500` — Limits pairs per file
- `max_total_pairs=1000000` — Hard cap on total pairs
- Progress logging every 10K files

**File Modified:** `src/chimera/correlation/entities.py:218-304`

#### Do You Need to Re-excavate?

**NO!** The excavation data is already stored:
- Files are in `~/.chimera/catalog.db` (SQLite)
- Chunks and entities are persisted
- Vector embeddings are in `~/.chimera/vectors/` (ChromaDB)

The correlation fixes work on existing data. Just restart the daemon and run:
```bash
chimera correlate --now
```

#### Verification Commands

```bash
# Check indexed files
sqlite3 ~/.chimera/catalog.db "SELECT COUNT(*) FROM files WHERE status='indexed'"

# Check entities
sqlite3 ~/.chimera/catalog.db "SELECT COUNT(*) FROM entities"

# Check chunks
sqlite3 ~/.chimera/catalog.db "SELECT COUNT(*) FROM chunks"

# Run correlation with new fixes
chimera correlate --now

# Check discoveries
chimera discoveries --min-confidence 0.3
```

### 2026-01-06 — Telemetry Dashboard & CLI Enhancements

Major improvements to the real-time monitoring capabilities and daemon responsiveness.

#### Issue 5: Daemon Unresponsive During Correlation

**Symptom:** Running `chimera dashboard` reports "daemon not running" even while daemon IS running with 59K files indexed. Health checks time out during correlation (~3 minutes for 6.6M entities).

**Root Cause:** Correlation engine's `run_correlation()` calls synchronous blocking methods:
- `consolidator.consolidate_all()` - processes millions of entities
- `consolidator.build_co_occurrence_matrix()` - builds 1M pairs
- `pattern_detector.detect_all()` - detects 23K patterns
- `discovery_surfacer.surface_all()` - surfaces discoveries

These block the asyncio event loop for ~3 minutes, preventing FastAPI from responding to health checks.

**Fix:** Run CPU-intensive operations in a `ThreadPoolExecutor`:
```python
async def run_correlation(self) -> CorrelationResult:
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:
        entities = await loop.run_in_executor(
            executor, self.consolidator.consolidate_all
        )
        # ... other heavy operations in executor
```

**File Modified:** `src/chimera/correlation/engine.py:91-165`

#### Issue 6: Dashboard Not Showing Real-Time Data

**Symptom:** Dashboard showed static data, CPU at 0%, GPU showing "No CUDA", current operation always idle.

**Root Causes:**
1. No real system stats - using hardcoded values
2. PyTorch installed as CPU-only version (can't detect GPU)
3. No tracking for synchronous CLI operations (`chimera correlate --now`)
4. Patterns count not exposed in telemetry

**Fixes:**

1. **Real System Stats (psutil)**
   - Added `psutil>=5.9.0` dependency
   - CPU/memory from `psutil.cpu_percent()`, `psutil.virtual_memory()`
   - Disk I/O rates calculated from `psutil.disk_io_counters()`

2. **GPU Detection via nvidia-smi**
   ```python
   result = subprocess.run(
       ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu',
        '--format=csv,noheader,nounits'],
       capture_output=True, text=True, timeout=5
   )
   ```
   Works even with CPU-only PyTorch. Now shows: `NVIDIA GeForce RTX 4070, 12% util, 2.0/12.0 GB`

3. **Current Operation Tracking**
   - Added `daemon.start_operation()` / `daemon.end_operation()` methods
   - `/correlate/run` endpoint now tracks operation start/end
   - Dashboard shows `[CLI: --now]` for synchronous operations
   - Added ETA calculation based on historical timing

4. **Patterns Count in Telemetry**
   - Added `patterns_detected` to telemetry response
   - Dashboard "Correlation Results" panel shows both patterns AND discoveries

**Files Modified:**
- `src/chimera/daemon.py` — Operation tracking, patterns_detected stat
- `src/chimera/api/routes/control.py` — Telemetry endpoint, GPU detection
- `src/chimera/telemetry.py` — Dashboard panels, ETA display
- `src/chimera/storage/catalog.py` — entities_by_type in get_stats()
- `src/chimera/queue.py` — get_current_job(), get_recent_jobs()
- `pyproject.toml` — Added psutil dependency

#### New Telemetry Endpoint

`GET /api/v1/telemetry` — Comprehensive data for dashboard:
- Real CPU/memory stats (psutil)
- GPU info (nvidia-smi)
- Current operation with ETA
- Patterns detected count
- Discoveries by type
- Storage sizes
- Recent jobs

#### ETA Calculation

After first correlation run, timing is saved. Subsequent correlations show:
```
⠋ Correlation
  Elapsed: 33s | ETA: 157s remaining
  ██████████░░░░░░░░░░░░░░░░░░░░ 18%
  [CLI: --now]
```

### 2026-01-08 — Sprint 5: Bug Fixes & Hardening

Critical bug fixes for Windows daemon crashes, multimedia metadata storage, and improved error handling.

#### Issue 11: Windows Daemon Crash (Exit Code 3221225477)

**Symptom:**
```
WinError 10054: An existing connection was forcibly closed by the remote host
Daemon process exited with code 3221225477
```

Exit code 3221225477 = 0xC0000005 = Windows Access Violation. Crash happened AFTER successful model loading ("Collection ready: documents").

**Root Causes:**

1. **Windows ProactorEventLoop incompatible with C extensions**
   - Windows defaults to `ProactorEventLoop` with Uvicorn
   - ChromaDB uses `hnswlib` (C++ extension)
   - ProactorEventLoop + C extensions = memory corruption

2. **Startup race condition**
   - Shell polled `/readiness` immediately after spawning daemon
   - Daemon still initializing (10-60+ seconds for models)
   - Rapid connection attempts caused socket pool exhaustion

3. **Database access during startup**
   - `/readiness` endpoint tried to access DB before startup complete
   - Caused "database is locked" errors during initialization

**Fixes:**

| Fix | File | Change |
|-----|------|--------|
| Windows event loop policy | `cli.py:5-8`, `shell.py:6-13` | Set `WindowsSelectorEventLoopPolicy` at module load |
| Initial startup delay | `shell.py:417` | 3-second delay before first poll |
| Poll interval | `shell.py:444` | Increased from 1s to 2s |
| Readiness timeout | `shell.py:439` | Increased from 2s to 5s |
| Single httpx.Client | `shell.py:wait_for_ready()` | Prevents socket exhaustion |
| Defensive /readiness | `server.py:70-145` | Return early if startup in progress |

**Key Code Changes:**

```python
# cli.py / shell.py - Windows event loop fix (MUST be at very top, before any imports)
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# shell.py - Startup race condition fix
time.sleep(3)  # Initial delay before polling
with httpx.Client(timeout=READINESS_TIMEOUT) as client:  # Single client
    while time.time() - start < timeout:
        # ... poll with 2-second intervals

# server.py - Defensive readiness endpoint
if not startup_complete:
    return {"ready": False, "reason": "startup_in_progress"}
```

**Critical Note:** The event loop policy MUST be set at module load time (top of file), BEFORE any other imports. Setting it in `daemon.py` before `uvicorn.run()` was too late - other modules had already imported asyncio and created event loops.

**Final Solution: Bootstrap Architecture**

The shell's subprocess spawning had import order race conditions that couldn't be fixed by placing the policy at the top of cli.py. The solution was a dedicated bootstrap module:

```python
# src/chimera/_bootstrap.py - Sets policy BEFORE any imports
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Now safe to import heavy dependencies
from chimera.cli import main as cli_main
cli_main()
```

Shell now spawns: `python -m chimera._bootstrap serve --dev` instead of `python -m chimera.cli serve --dev`

**Files Created/Modified:**
- `src/chimera/_bootstrap.py` — NEW: Bootstrap entry point with validation
- `src/chimera/shell.py` — Use bootstrap for subprocess spawning
- `src/chimera/cli.py` — WindowsSelectorEventLoopPolicy at module load
- `src/chimera/daemon.py` — Backup policy setting
- `src/chimera/api/server.py` — Defensive /readiness endpoint
- `pyproject.toml` — Added `chimera-bootstrap` entry point
- `scripts/wsl-setup.sh` — NEW: WSL environment setup
- `scripts/chimera-wsl.bat` — NEW: Windows→WSL launcher

**Verification:**
Daemon now starts successfully via bootstrap on Windows without crash. Tested with:
- `python -m chimera._bootstrap serve --dev` — 45+ seconds no crash
- ChromaDB initialization (no access violation)
- Model loading (spaCy, sentence-transformers)
- Full startup sequence completes

#### Issue 7: Image Metadata Storage Fails

**Symptom:**
```
ERROR: CatalogDB.add_image_metadata() got an unexpected keyword argument 'file_id'
```

**Root Cause:** API signature mismatch between pipeline and catalog:
- `pipeline.py` called `add_image_metadata(file_id=..., width=..., ...)` with keyword args
- `catalog.py` expected `add_image_metadata(record: ImageMetadataRecord)` with dataclass

**Fix:** Updated `pipeline.py` to construct dataclass instances:
```python
# BEFORE (broken):
self.catalog.add_image_metadata(file_id=file_id, width=...)

# AFTER (correct):
record = ImageMetadataRecord(file_id=file_id, width=...)
self.catalog.add_image_metadata(record)
```

**Files Modified:** `src/chimera/extractors/pipeline.py` lines 261-330

#### Issue 8: Audio Metadata Same Pattern

Same API mismatch for `add_audio_metadata()`. Fixed by constructing `AudioMetadataRecord`.

**File Modified:** `src/chimera/extractors/pipeline.py` lines 332-379

#### Issue 9: GPS Location Same Pattern

Same API mismatch for `add_gps_location()`. Fixed by constructing `GPSLocationRecord`.

**File Modified:** `src/chimera/extractors/pipeline.py` lines 312-324

#### Issue 10: Silent Failures Masking Bugs

**Symptom:** Errors logged but processing continued, making bugs hard to detect.

**Root Cause:** Exception handlers used `logger.warning()` and continued execution.

**Fix:** Changed to `logger.error()` + `raise` for proper error propagation:
```python
except Exception as e:
    logger.error(f"Failed to store image metadata for {file_path}: {e}")
    raise  # Re-raise to make failure visible
```

#### New Tests Added

Created `tests/test_multimedia.py` with integration tests for:
- `ImageMetadataRecord` dataclass creation and storage
- `AudioMetadataRecord` dataclass creation and storage
- `GPSLocationRecord` dataclass creation and storage
- Pipeline multimedia storage methods
- Error handling (fail fast, not silent)

### 2026-01-07 — PR #1 Multimedia Extraction Pipeline Merge

Merged `usb-excavator` branch into main, combining:
- **Main branch**: Daemon responsiveness (ThreadPoolExecutor), telemetry dashboard, psutil
- **USB-excavator**: Multimedia extractors, AI vision providers, USB excavator

#### New Modules Added

| Module | Purpose |
|--------|---------|
| `src/chimera/ai/vision.py` | AI vision providers (OpenAI, Claude, BLIP-2) |
| `src/chimera/extractors/audio.py` | Audio metadata, transcription |
| `src/chimera/usb/` | USB device detection and excavation |
| `src/chimera/gpu/` | GPU utilities for embeddings |
| `src/chimera/sync/` | Graph sync utilities |
| `usb-package/` | Standalone USB excavator package |

#### Image Extractor Enhancements

From USB-excavator branch:
- EXIF metadata extraction (camera, settings, date)
- GPS coordinate parsing with reverse geocoding
- Thumbnail generation
- AI vision integration (multi-provider fallback)

#### Merge Conflict Resolution

Only `pyproject.toml` had conflicts:
- Kept `psutil>=5.9.0` from main
- Added `prompt_toolkit>=3.0.0` from USB-excavator
- Python version already set to 3.10+ for WSL compatibility

#### Preserved from Main

All daemon responsiveness fixes preserved:
- `ThreadPoolExecutor` for non-blocking correlation
- `start_operation()` / `end_operation()` tracking
- ETA calculation based on historical timing
- Real-time telemetry via nvidia-smi and psutil

#### Dashboard Layout (Final)

```
┌─────────────────────────────────────────────────────────────┐
│ * CHIMERA v0.1.0 | Jobs: 0 pending | Updated: 17:50:23      │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────┐  ┌─────────────────────────────────────┐│
│ │ CPU: 12%        │  │ Extraction Velocity                 ││
│ │ ████░░░░░░░░░░░ │  │ ▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅                ││
│ ├─────────────────┤  │ -> 45 files/m                       ││
│ │ Memory          │  │ -> 2.3k chunks/m                    ││
│ │ ████████░░░ 8/16│  ├─────────────────────────────────────┤│
│ ├─────────────────┤  │ Entities Extracted                  ││
│ │ GPU             │  │ PERSON   ████████████░░░░  12,345   ││
│ │ RTX 4070        │  │ ORG      ██████░░░░░░░░░░   5,678   ││
│ │ GPU: ██░░░░ 12% │  │ TECH     ████░░░░░░░░░░░░   3,456   ││
│ │ Mem: ██░░░ 2/12G│  │ DATE     ███░░░░░░░░░░░░░   2,345   ││
│ └─────────────────┘  └─────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────┐ ┌─────────────────────────────┤│
│ │ Live Feed                 │ │ Correlation Results         ││
│ │ 17:50:21 OK server.py     │ │ Patterns: 22,719           ││
│ │ 17:50:19 OK daemon.py     │ │ Discoveries: 14,617        ││
│ │ 17:50:15 >> entities.py   │ │   relationship: 14,606     ││
│ │ 17:50:12 OK pipeline.py   │ │   expertise: 6             ││
│ │ 17:50:08 !! config.py     │ │   workflow: 4              ││
│ └───────────────────────────┘ └─────────────────────────────┤│
├─────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────┐ ┌────────────────────┤│
│ │ Current Operation                  │ │ Job Queue          ││
│ │ ⠋ Correlation                      │ │ Pending: 0         ││
│ │   Elapsed: 33s | ETA: 157s         │ │ Processed: 8,234   ││
│ │   ██████████░░░░░░░░░░░░░░░░ 18%   │ │ Correlations: 2    ││
│ │   [CLI: --now]                     │ ├────────────────────┤│
│ │                                    │ │ Storage            ││
│ │                                    │ │ Catalog: 2,345 MB  ││
│ │                                    │ │ Vectors: 1.23 GB   ││
│ │                                    │ │ Total: 3.57 GB     ││
│ └────────────────────────────────────┘ └────────────────────┤│
├─────────────────────────────────────────────────────────────┤
│ Files: 59,234 | Chunks: 1,234,567 | Entities: 6,600,000     │
│ Uptime: 2h 34m | Press Ctrl+C to exit                       │
└─────────────────────────────────────────────────────────────┘
```

## Key Files

| File | Purpose |
|------|--------|
| `daemon.py` | Main orchestrator, operation tracking |
| `cli.py` | Full CLI implementation |
| `telemetry.py` | Real-time dashboard (Rich library) |
| `api/routes/control.py` | API endpoints, telemetry endpoint |
| `extractors/pipeline.py` | Extraction orchestrator |
| `extractors/image.py` | EXIF, GPS, thumbnails, AI vision |
| `extractors/audio.py` | Audio metadata, transcription |
| `ai/vision.py` | OpenAI, Claude, BLIP-2 vision providers |
| `correlation/engine.py` | Correlation orchestrator (ThreadPoolExecutor) |
| `storage/catalog.py` | SQLite catalog, entity stats |
| `queue.py` | Job queue, current/recent jobs |
| `usb/excavator.py` | USB device scanning |
| `gpu/vectors.py` | GPU-accelerated embeddings |
| `integration/claude.py` | Claude context builder |
| `integration/mcp.py` | MCP server |

---

## Known Issues & Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `database is locked` | SQLite concurrent access | Restart daemon, wait for operations to complete |
| `no running event loop` | Thread calling async code | Use `asyncio.run_coroutine_threadsafe()` |
| `unexpected keyword argument` | API signature mismatch | Construct dataclass, don't pass kwargs |
| `Daemon not responding` | Heavy operation blocking | Wait for correlation to complete (check dashboard) |
| `Connection refused :7777` | Daemon not running | Start with `chimera serve --dev` |
| `Exit code 3221225477` | Windows ProactorEventLoop + C extensions | Fixed in Sprint 5 (WindowsSelectorEventLoopPolicy) |
| `WinError 10054` | Windows socket reset during startup | Fixed in Sprint 5 (startup race condition) |

### Health Check Troubleshooting

```bash
# Quick check if daemon is running
chimera ping

# Full health check with details
chimera health

# Check via API directly
curl http://127.0.0.1:7777/api/v1/health

# Check readiness (all systems initialized)
curl http://127.0.0.1:7777/api/v1/readiness
```

### Database Issues

```bash
# Check database sizes
ls -lh ~/.chimera/*.db

# Verify catalog integrity
sqlite3 ~/.chimera/catalog.db "PRAGMA integrity_check"

# Check current journal mode (should be WAL)
sqlite3 ~/.chimera/catalog.db "PRAGMA journal_mode"

# Set WAL mode if needed
sqlite3 ~/.chimera/catalog.db "PRAGMA journal_mode=WAL"

# Check for stale lock files
ls ~/.chimera/*.db-*
```

### Correlation Taking Too Long

With 6.6M entities, correlation takes ~3 minutes. During this time:
- Health checks may be slow (but responsive due to ThreadPoolExecutor fix)
- Use dashboard to monitor progress: `chimera dashboard`
- Check ETA in current operation panel

### Multimedia Not Being Processed

If images/audio are detected but metadata not stored:
1. Check logs for errors: `chimera logs`
2. Verify extractors registered: Check `get_registry().list_extractors()`
3. Ensure file extensions match extractor patterns

### Development vs Production

| Feature | `--dev` Mode | Production |
|---------|--------------|------------|
| Hot reload | Yes | No |
| Debug logging | Yes | No |
| Auto-restart | No | Recommended (systemd) |
| Port | 7777 | Configurable |

### Deployment Options

**Option 1: Virtual Environment (Development)**
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[dev]"
chimera serve --dev
```

**Option 2: Docker (Production)**
```bash
docker build -t chimera-daemon .
docker run -v ~/.chimera:/root/.chimera -p 7777:7777 chimera-daemon
```

Note: These are **separate deployment options**, not nested. The venv is for local development, Docker is for production deployment.

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
