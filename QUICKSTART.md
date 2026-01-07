# CHIMERA USB Excavator - Quick Start

## What's New

Sprint U1-U4 complete:

- **U1**: USB Excavator Core (portable excavation)
- **U2**: Advanced Telemetry (gotop-style dashboard)
- **U3**: GPU Acceleration (FAISS-GPU, cuML)
- **U4**: Cross-Machine Discovery (patterns across machines)

## Quick Start

### 1. Pull the Branch

```powershell
cd "E:\Software DEV\chimera-daemon"
git fetch origin
git checkout usb-excavator
pip install -e . --break-system-packages
```

### 2. Build USB Package

```powershell
python -m chimera.usb.build "F:\CHIMERA-USB"
```

### 3. Test USB Excavator

```powershell
# Direct test (without USB)
python -m chimera.usb.excavator
```

### 4. Excavate a Target Drive

1. Plug USB into any Windows machine
2. Run `launch.bat` as Administrator
3. Select target drive
4. Wait for excavation (gotop-style dashboard shows progress)
5. Output saved to `excavations/` on USB

### 5. Sync Back to Server

```powershell
# In CHIMERA shell
chimera> /sync

# Or directly
python -m chimera.sync.cli sync
```

### 6. Run Cross-Machine Discovery

```powershell
chimera> /discover

# Or with GPU
chimera> /correlate --gpu
```

## New Shell Commands

| Command | Description |
|---------|-------------|
| `/sync` | Sync USB excavations to server |
| `/merge <path>` | Merge excavations directory |
| `/discover` | Cross-machine pattern discovery |
| `/gpu` | Check GPU status |

## GPU Setup (for 4070)

```powershell
# Check GPU
python -m chimera.gpu.setup

# Install GPU packages
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install faiss-gpu
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CHIMERA DISTRIBUTED SYSTEM                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                     │
│  │ USB Drive 1 │  │ USB Drive 2 │  │ USB Drive N │                     │
│  │ (Machine A) │  │ (Machine B) │  │ (Machine X) │                     │
│  │             │  │             │  │             │                     │
│  │ excavate → │  │ excavate → │  │ excavate → │                     │
│  │ local save  │  │ local save  │  │ local save  │                     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                     │
│         │                │                │                             │
│         └────────────────┼────────────────┘                             │
│                          │                                              │
│                          ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    CENTRAL SERVER (Your PC)                      │  │
│  │                                                                  │  │
│  │  /sync          /merge           /correlate --gpu    /discover  │  │
│  │     │              │                   │                 │       │  │
│  │     ▼              ▼                   ▼                 ▼       │  │
│  │  ┌──────┐    ┌──────────┐    ┌──────────────┐    ┌──────────┐   │  │
│  │  │ USB  │    │ Catalog  │    │ GPU Engine   │    │ Cross-   │   │  │
│  │  │ Sync │───▶│ Merger   │───▶│ (RTX 4070)   │───▶│ Machine  │   │  │
│  │  └──────┘    └──────────┘    │ FAISS-GPU    │    │ Discovery│   │  │
│  │                              │ cuML         │    └──────────┘   │  │
│  │                              └──────────────┘                    │  │
│  │                                                                  │  │
│  │  ┌─────────────────────────────────────────────────────────┐    │  │
│  │  │                    MASTER CATALOG                        │    │  │
│  │  │  - All excavations merged                                │    │  │
│  │  │  - Entities consolidated                                 │    │  │
│  │  │  - Cross-machine patterns                                │    │  │
│  │  │  - Discoveries surfaced                                  │    │  │
│  │  └─────────────────────────────────────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Files Added

```
src/chimera/
├── usb/
│   ├── excavator.py       # Main USB excavator
│   ├── telemetry.py       # Basic telemetry
│   ├── telemetry_advanced.py  # Gotop-style dashboard
│   ├── sync.py            # USB sync to server
│   ├── build.py           # Build portable package
│   └── launcher.py        # Cross-platform launcher
├── gpu/
│   ├── __init__.py        # GPU detection
│   ├── vectors.py         # FAISS-GPU vector index
│   ├── correlation.py     # cuML correlation engine
│   └── setup.py           # GPU setup utilities
├── sync/
│   ├── __init__.py
│   ├── merger.py          # Catalog merger
│   ├── discovery.py       # Cross-machine discovery
│   └── cli.py             # Sync CLI commands
└── shell_extensions.py    # New shell commands

usb-package/
├── launch.bat             # Windows launcher
├── launch.sh              # Linux/Mac launcher
├── .chimera-usb           # USB marker file
└── README.md              # Quick start
```

## What's Next

1. Test USB excavator on your machines
2. Bring excavations back to server
3. Run `/sync` to merge
4. Run `/discover` for cross-machine insights
5. Use GPU correlation for speed

---

*Kimera, ready for distributed cognitive archaeology.* 🧬
