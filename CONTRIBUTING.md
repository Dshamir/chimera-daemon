# Contributing to CHIMERA

Thank you for your interest in contributing to CHIMERA!

## Development Setup

### Prerequisites

- Python 3.10+
- Git
- NVIDIA GPU (optional, for faster embeddings)
- ~10GB disk space

### Setting Up (Linux/Mac)

```bash
# Clone the repository
git clone https://github.com/Dshamir/chimera-daemon.git
cd chimera-daemon

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in development mode with all dependencies
pip install -e ".[dev]"

# Initialize configuration
chimera init

# Verify installation
chimera --help
```

### Setting Up (Windows - WSL Recommended)

For Windows development, WSL provides the most reliable experience:

```bash
# Launch WSL
wsl

# Navigate to project (adjust path as needed)
cd /mnt/e/Software\ DEV/chimera-daemon

# Run automated setup script
./scripts/wsl-setup.sh

# Activate and verify
source venv-wsl/bin/activate
chimera --help
```

Alternatively, use the Windows launcher:

```cmd
scripts\chimera-wsl.bat --help
```

**Important - WSL Data Path:**

The setup script automatically symlinks `~/.chimera` to your Windows data directory if it exists. If you need to do this manually (e.g., dashboard shows all zeros):

```bash
# Link to existing Windows data
ln -s /mnt/c/Users/YourName/.chimera ~/.chimera
```

### Setting Up (Windows Native)

If you must use Windows natively:

```cmd
# Clone and navigate
git clone https://github.com/Dshamir/chimera-daemon.git
cd chimera-daemon

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install
pip install -e ".[dev]"

# Verify
chimera --help
```

**Note:** Windows native requires the bootstrap architecture to handle event loop policy. The daemon spawns via `_bootstrap.py` to ensure `WindowsSelectorEventLoopPolicy` is set before any imports.

### Running the Daemon

```bash
# Development mode (with hot reload, debug logging)
chimera serve --dev

# Check status
chimera status

# Run correlation
chimera correlate --now

# View dashboard
chimera dashboard
```

## Project Structure

```
chimera-daemon/
├── src/chimera/
│   ├── _bootstrap.py       # Windows bootstrap (sets event loop policy)
│   ├── daemon.py           # Main orchestrator
│   ├── cli.py              # CLI commands (Click)
│   ├── shell.py            # Interactive shell (spawns via bootstrap)
│   ├── config.py           # Configuration management
│   ├── queue.py            # Job queue (SQLite)
│   ├── watcher.py          # File system watcher
│   ├── telemetry.py        # Dashboard (Rich)
│   ├── startup.py          # Initialization checks
│   ├── extractors/         # Content extraction
│   │   ├── base.py         # Base extractor class
│   │   ├── registry.py     # Extractor registry
│   │   ├── pipeline.py     # Extraction orchestrator
│   │   ├── document.py     # PDF, DOCX, TXT, MD
│   │   ├── code.py         # Source code
│   │   ├── image.py        # Images (EXIF, OCR, AI vision)
│   │   └── audio.py        # Audio (metadata, transcription)
│   ├── storage/
│   │   ├── catalog.py      # SQLite catalog
│   │   └── vectors.py      # ChromaDB vectors
│   ├── correlation/
│   │   ├── engine.py       # Correlation orchestrator
│   │   ├── entities.py     # Entity consolidation
│   │   ├── patterns.py     # Pattern detection
│   │   └── discovery.py    # Discovery surfacing
│   ├── integration/
│   │   ├── claude.py       # Claude context builder
│   │   └── mcp.py          # MCP server
│   └── api/
│       ├── server.py       # FastAPI app
│       └── routes/         # API endpoints
├── scripts/
│   ├── wsl-setup.sh        # WSL environment setup
│   └── chimera-wsl.bat     # Windows→WSL launcher
├── tests/                  # Test suite
├── usb-package/            # Standalone USB excavator
└── pyproject.toml          # Project configuration
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=chimera

# Run specific test file
pytest tests/test_multimedia.py

# Run with verbose output
pytest -v

# Run only fast tests (skip slow integration tests)
pytest -m "not slow"
```

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Use pytest fixtures for setup/teardown
- Mock external dependencies (API calls, file system)

Example test:

```python
import pytest
from chimera.storage.catalog import CatalogDB, ImageMetadataRecord

@pytest.fixture
def temp_catalog():
    """Create a temporary catalog database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "catalog.db"
        catalog = CatalogDB(db_path)
        yield catalog

def test_store_image_metadata(temp_catalog):
    record = ImageMetadataRecord(
        file_id="test_001",
        width=1920,
        height=1080,
        format="JPEG",
    )
    temp_catalog.add_image_metadata(record)

    retrieved = temp_catalog.get_image_metadata("test_001")
    assert retrieved["width"] == 1920
```

## Code Style

### Python Style

- Follow PEP 8
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use descriptive variable names

### Dataclasses for Records

Always use dataclasses for database records:

```python
# GOOD: Use dataclass
record = ImageMetadataRecord(file_id="test", width=100, height=100)
catalog.add_image_metadata(record)

# BAD: Don't pass kwargs directly
catalog.add_image_metadata(file_id="test", width=100, height=100)
```

### Error Handling

Fail fast, don't fail silently:

```python
# GOOD: Re-raise to make failures visible
try:
    process_file(path)
except Exception as e:
    logger.error(f"Failed to process {path}: {e}")
    raise  # Re-raise

# BAD: Silent failure
try:
    process_file(path)
except Exception as e:
    logger.warning(f"Failed to process {path}: {e}")
    # Continues without error indication
```

### Async/Threading

When calling async code from threads:

```python
# GOOD: Use run_coroutine_threadsafe
loop = asyncio.get_event_loop()
asyncio.run_coroutine_threadsafe(async_function(), loop)

# BAD: create_task in thread (no event loop)
asyncio.create_task(async_function())  # RuntimeError!
```

### Windows Compatibility

CHIMERA uses a **bootstrap architecture** for Windows compatibility. The key insight: event loop policy must be set BEFORE any imports that might touch asyncio.

**The Bootstrap Pattern:**

```python
# src/chimera/_bootstrap.py - This is the correct approach
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# NOW safe to import heavy dependencies
from chimera.cli import main as cli_main
cli_main()
```

**Why This Works:**
- When shell.py spawns a subprocess with `python -m chimera._bootstrap serve --dev`
- Python loads `_bootstrap.py` first
- Event loop policy is set BEFORE chromadb/spacy/sentence-transformers load
- No race condition with import order

**Common Mistakes:**

```python
# BAD: Setting policy at top of cli.py - NOT sufficient for subprocess spawning
# cli.py
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(...)  # May be too late if spawned differently

# BAD: Setting policy before uvicorn.run() - definitely too late
def run_server():
    asyncio.set_event_loop_policy(...)  # C extensions already loaded!
    uvicorn.run(app)
```

**Key Windows Considerations:**
- **Bootstrap Architecture**: Shell spawns `chimera._bootstrap` not `chimera.cli`
- **Event Loop**: `WindowsSelectorEventLoopPolicy` required for C extensions (ChromaDB)
- **Socket Cleanup**: Use single `httpx.Client` instance to prevent exhaustion
- **Startup Timing**: 3-second delay before polling newly spawned subprocess
- **WSL Alternative**: For maximum reliability, run in WSL (see setup instructions)

## Pull Request Process

### Before Submitting

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes** with clear, focused commits

3. **Add tests** for new functionality

4. **Run the test suite**:
   ```bash
   pytest
   ```

5. **Update documentation** if needed:
   - `CLAUDE.md` for development notes
   - `README.md` for user-facing changes
   - Docstrings for new functions

### Commit Messages

Use clear, descriptive commit messages:

```
feat(extractors): Add HEIC image support

- Add HEIC to ImageExtractor extensions
- Update pillow-heif dependency
- Add tests for HEIC extraction
```

Prefixes:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Tests
- `refactor:` Code refactoring
- `perf:` Performance improvement

### Submitting

1. Push your branch:
   ```bash
   git push origin feature/my-feature
   ```

2. Create a Pull Request on GitHub

3. Fill out the PR template with:
   - Summary of changes
   - Test plan
   - Related issues

4. Wait for review

## Common Issues

### Database Locked

If you see "database is locked" errors during development:

```bash
# Stop any running daemons
chimera stop

# Check for stale processes
ps aux | grep chimera

# Clean lock files
rm ~/.chimera/*.db-journal
rm ~/.chimera/*.db-wal
rm ~/.chimera/*.db-shm
```

### Windows Daemon Crash (Exit Code 3221225477)

If the daemon crashes with exit code 3221225477 on Windows:
- This is a memory access violation (0xC0000005)
- Caused by ProactorEventLoop + C extensions (ChromaDB/hnswlib)
- **Solution**: Use the bootstrap architecture (`_bootstrap.py`)
- Shell spawns `python -m chimera._bootstrap` to guarantee policy is set first
- **Note**: Setting the policy in `cli.py` or `daemon.py` is NOT sufficient for subprocess spawning

If you see `WinError 10054` (connection reset):
- Caused by socket pool exhaustion from rapid connection attempts
- **Solution**: Use single `httpx.Client` instance, add startup delays

**Recommended**: For development on Windows, use WSL to avoid these issues entirely.

### Import Errors

After making changes to module structure:

```bash
# Reinstall in development mode
pip install -e ".[dev]"
```

### Test Failures

If tests fail with database errors:

```bash
# Tests use temporary databases, check for leaks
pytest --tb=short
```

## Getting Help

- Check [CLAUDE.md](./CLAUDE.md) for development history
- Open an issue for bugs or feature requests
- Check existing issues before creating new ones

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
