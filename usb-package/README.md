# CHIMERA USB Excavator

Portable cognitive archaeology system.

## Quick Start

### Windows
1. Right-click `launch.bat`
2. Select "Run as administrator"
3. Follow prompts

### Linux/Mac
```bash
sudo ./launch.sh
```

## What It Does

1. Scans target drive(s) for supported files
2. Extracts text chunks and entities
3. Saves everything to `excavations/` folder on this USB
4. Take USB to central server and run `/sync`

## Supported File Types

- Documents: `.txt`, `.md`, `.pdf`, `.docx`, `.doc`
- Code: `.py`, `.js`, `.ts`, `.java`, `.c`, `.cpp`, `.h`
- Data: `.json`, `.yaml`, `.yml`, `.xml`, `.csv`
- Web: `.html`, `.css`, `.sql`

## Output Structure

```
excavations/
└── {machine-id}_{timestamp}/
    ├── chunks/           # Text chunks per file
    ├── entities/         # Extracted entities
    └── metadata/
        └── excavation.json
```

## Sync with Server

Plug USB into server running CHIMERA and run:
```
chimera> /sync
```

---
*Kimera - Cognitive History Integration & Memory Extraction*
