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
- **Sovereignty First** — All processing local, no external API calls, your data stays yours

## Quick Start

```bash
# Install
pip install chimera-daemon

# Configure
chimera init

# Start daemon
chimera serve

# Query
chimera query "thermal control PID"

# Full excavation
chimera excavate
```

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

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  CHIMERA DAEMON                              │
├─────────────────────────────────────────────────────────────┤
│  Watcher → Queue → Extractors → Storage                     │
│                                                              │
│  Extractors: Docs | Code | Image | FAE                      │
│  Storage: SQLite (catalog) + ChromaDB (vectors)             │
│  API: REST (port 7777) + CLI                                │
└─────────────────────────────────────────────────────────────┘
```

## Documentation

- [PRD](https://github.com/Dshamir/sif-knowledge-base/tree/main/projects/chimera-prd) — Full Product Requirements Document
- [A7.2 FAE Protocol](https://github.com/Dshamir/sif-knowledge-base/blob/main/amendments/A7.2-full-archaeology-excavation-protocol.md) — AI export detection and processing

## Status

**Version:** 0.0.1-dev  
**Status:** Sprint 0 — Foundation  
**Python:** 3.11+  

## License

MIT

---

*"We do this right or we don't do it."*
