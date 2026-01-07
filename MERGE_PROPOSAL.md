# CHIMERA Branch Merge Proposal

## Executive Summary

**Two parallel development streams that complement each other perfectly:**

| Branch | Focus | Strengths |
|--------|-------|-----------|
| **main** | Server-side daemon, CLI, API, telemetry | Production-grade dashboard, job tracking, real-time metrics |
| **usb-excavator** | Portable excavation, GPU acceleration, cross-machine sync | Distributed archaeology, offline operation, GPU correlation |

## Branch Comparison

### Main Branch (Today's Work)
```
src/chimera/
├── telemetry.py (781 lines) ✨ NEW
│   - TelemetryDashboard with Rich Live
│   - Real psutil metrics (CPU, RAM, disk I/O)
│   - GPU monitoring (torch.cuda)
│   - Velocity sparklines
│   - Entity breakdown by type
│   - Current job with ETA
│   - Recent jobs feed
│   - API-driven polling
│
├── cli.py (31KB) - Enhanced
│   - `/dashboard` command
│   - Sync correlation with progress
│   - Better error handling
│   - api_request_with_spinner()
│
├── shell.py (31KB) - Enhanced
│   - Unified interactive shell
│   - Session logging
│   - Command history
│   - Auto-complete
│
├── daemon.py - Enhanced
│   - Operation tracking
│   - Current job exposure
│
├── queue.py - Enhanced
│   - current_job tracking
│   - recent_jobs list
│
└── storage/catalog.py - Enhanced
    - entities_by_type() method
```

### USB-Excavator Branch
```
src/chimera/
├── usb/
│   ├── excavator.py (23KB) ✨ NEW
│   │   - Portable USB excavation
│   │   - WSL-aware drive detection
│   │   - Cross-platform (Win/Linux/Mac)
│   │   - Admin elevation handling
│   │   - Pattern-based entity extraction
│   │
│   ├── telemetry.py (basic) ✨ NEW
│   ├── telemetry_advanced.py (gotop-style) ✨ NEW
│   ├── sync.py (USB sync) ✨ NEW
│   ├── build.py (PyInstaller) ✨ NEW
│   └── launcher.py ✨ NEW
│
├── gpu/
│   ├── __init__.py ✨ NEW
│   │   - GPU detection
│   │   - FAISS/cuML availability
│   │
│   ├── vectors.py ✨ NEW
│   │   - GPUVectorIndex (FAISS-GPU)
│   │   - HybridVectorStore
│   │
│   ├── correlation.py ✨ NEW
│   │   - GPUCorrelationEngine
│   │   - Co-occurrence matrix (cuPy)
│   │   - PMI calculation
│   │   - Entity clustering
│   │   - UMAP/PCA reduction
│   │
│   └── setup.py ✨ NEW
│       - GPU setup utilities
│
└── sync/
    ├── __init__.py ✨ NEW
    ├── merger.py ✨ NEW
    │   - CatalogMerger
    │   - Content deduplication
    │   - Entity normalization
    │
    ├── discovery.py ✨ NEW
    │   - CrossMachineDiscovery
    │   - Pattern detection across machines
    │   - Insight generation
    │
    └── cli.py ✨ NEW
        - /sync, /merge, /discover commands
```

---

## Merge Strategy

### Phase 1: Non-Conflicting Additions (Clean Merge)

These files exist ONLY in usb-excavator - direct copy:

```
src/chimera/usb/          → ADD ENTIRELY
src/chimera/gpu/          → ADD ENTIRELY  
src/chimera/sync/         → ADD ENTIRELY
```

### Phase 2: Telemetry Consolidation

**Challenge:** Both branches have `telemetry.py` but different purposes.

**Solution:** Rename and integrate:

| File | Purpose |
|------|---------|
| `telemetry.py` | Main branch version - API-driven dashboard (KEEP) |
| `usb/telemetry.py` | USB excavator simple telemetry (KEEP as-is) |
| `usb/telemetry_advanced.py` | Gotop-style for USB (KEEP as-is) |

### Phase 3: Shell Integration

Add new commands to `shell.py`:

```python
# Add to ChimeraShell.commands
"/sync": self.cmd_sync,           # USB sync
"/merge": self.cmd_merge,         # Catalog merge  
"/discover": self.cmd_discover,   # Cross-machine discovery
"/gpu": self.cmd_gpu,             # GPU status
"/usb": self.cmd_usb,             # Launch USB excavator
```

### Phase 4: CLI Integration

Add new commands to `cli.py`:

```python
@main.command()
def usb():
    """Launch USB excavator mode."""
    from chimera.usb.excavator import main as usb_main
    usb_main()

@main.command()  
def gpu():
    """Check GPU status and setup."""
    from chimera.gpu.setup import setup_gpu
    setup_gpu()
```

---

## Proposed New Features (Post-Merge Upgrades)

### Tier 1: High Value, Low Effort

| Feature | Description | Effort |
|---------|-------------|--------|
| **OCR Integration** | Add Tesseract to USB excavator for scanned PDFs | 2h |
| **spaCy NER** | Full entity extraction (not just regex) on server | 2h |
| **Progress Persistence** | Save excavation state for resume after interrupt | 3h |
| **Scheduled Excavation** | Cron-like background indexing | 2h |

### Tier 2: AI Provider Integrations

| Provider | Use Case | Value |
|----------|----------|-------|
| **OpenAI Embeddings** | Alternative to sentence-transformers (API vs local) | Better quality, cost tradeoff |
| **Anthropic Claude** | Smart summarization of discoveries | "Why is this pattern important?" |
| **Cohere Rerank** | Improve search result ranking | Better relevance |
| **Voyage AI** | Domain-specific embeddings | Medical/legal/code specialization |

**Recommended Implementation:**

```python
# src/chimera/ai/providers.py
class AIProviderRegistry:
    providers = {
        "embeddings": {
            "local": SentenceTransformerEmbedder,  # Default
            "openai": OpenAIEmbedder,
            "voyage": VoyageEmbedder,
        },
        "summarize": {
            "claude": ClaudeSummarizer,
            "openai": GPT4Summarizer,
        },
        "rerank": {
            "cohere": CohereReranker,
            "local": CrossEncoderReranker,
        }
    }
```

### Tier 3: Advanced Features

| Feature | Description | Complexity |
|---------|-------------|------------|
| **Real-time Sync** | WebSocket-based live excavation updates | Medium |
| **Distributed Workers** | Multiple machines excavating in parallel | High |
| **Knowledge Graph** | Neo4j integration for entity relationships | High |
| **Time Travel** | Query "what did I know on date X" | Medium |
| **Attention Heatmaps** | Visualize which topics you focus on over time | Medium |

---

## Recommended Merge Order

```bash
# 1. Create merge branch
git checkout main
git checkout -b merge-usb-excavator

# 2. Merge usb-excavator (will have conflicts in pyproject.toml only)
git merge usb-excavator

# 3. Resolve pyproject.toml conflict
# Keep main's structure, add usb-excavator's new deps

# 4. Copy non-conflicting directories
# (Already handled by merge)

# 5. Add shell commands
# Edit shell.py to add /sync, /merge, /discover, /gpu, /usb

# 6. Add CLI commands  
# Edit cli.py to add usb, gpu commands

# 7. Test
python -m chimera.cli serve
python -m chimera.usb.excavator
python -m chimera.gpu.setup

# 8. Merge to main
git checkout main
git merge merge-usb-excavator
```

---

## Post-Merge Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      CHIMERA UNIFIED                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │   CLI/Shell     │    │   Dashboard     │                    │
│  │                 │    │  (telemetry.py) │                    │
│  │ /excavate       │    │                 │                    │
│  │ /correlate      │    │ Real-time stats │                    │
│  │ /discoveries    │    │ GPU monitoring  │                    │
│  │ /sync          │◄──►│ Job tracking    │                    │
│  │ /gpu           │    │ Entity breakdown│                    │
│  │ /usb           │    │                 │                    │
│  └────────┬────────┘    └────────┬────────┘                    │
│           │                      │                              │
│           ▼                      ▼                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                     DAEMON (API)                         │   │
│  │  /api/v1/telemetry  /api/v1/correlate  /api/v1/sync     │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                      │                              │
│           ▼                      ▼                              │
│  ┌────────────────┐    ┌────────────────┐    ┌──────────────┐  │
│  │   Extractors   │    │   Correlation  │    │  GPU Engine  │  │
│  │                │    │                │    │              │  │
│  │ Text, PDF,     │    │ Patterns,      │    │ FAISS-GPU    │  │
│  │ DOCX, spaCy    │    │ Discoveries    │    │ cuML/cuPy    │  │
│  └────────────────┘    └────────────────┘    └──────────────┘  │
│           │                      │                  │           │
│           ▼                      ▼                  ▼           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    STORAGE LAYER                         │   │
│  │   CatalogDB (SQLite)  │  VectorDB (Chroma)  │  Files     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   USB EXCAVATOR                          │   │
│  │   Portable  │  Offline  │  Cross-Platform  │  WSL       │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               CROSS-MACHINE SYNC                         │   │
│  │   Merger  │  Deduplication  │  Discovery  │  Insights   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Files Summary

### Keep from Main (Enhanced Today)
- `telemetry.py` - Full dashboard with API polling
- `cli.py` - Enhanced CLI with dashboard command
- `shell.py` - Unified shell with session logging
- `daemon.py` - Operation tracking
- `queue.py` - Job management
- `storage/catalog.py` - entities_by_type

### Add from USB-Excavator
- `usb/*` - Portable excavation system
- `gpu/*` - GPU acceleration
- `sync/*` - Cross-machine sync

### Merge Carefully
- `pyproject.toml` - Combine dependencies

---

## Next Steps

1. **Approve this proposal** → I create the merge
2. **Test merged branch** → Verify both workflows
3. **Implement Tier 1 upgrades** → OCR, spaCy NER
4. **Optional: AI providers** → Based on your preference

Ready to execute merge? 🔀
