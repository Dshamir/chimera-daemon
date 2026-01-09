"""CHIMERA Bootstrap - Controlled Startup Sequence.

This module ensures:
1. Event loop policy is set BEFORE any imports
2. Environment is validated
3. Dependencies are checked
4. Daemon starts with full control

IMPORTANT: This file must have minimal imports at the top level.
The event loop policy MUST be set before importing any async libraries.
"""
import sys
import os

# Step 1: Set event loop policy IMMEDIATELY (before any other imports)
# This is critical for Windows compatibility with C extensions (ChromaDB/hnswlib)
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def validate_environment() -> list[str]:
    """Check all required components are available.

    Returns:
        List of error messages (empty if all checks pass)
    """
    errors = []

    # Check Python version
    if sys.version_info < (3, 10):
        errors.append(f"Python 3.10+ required, got {sys.version_info.major}.{sys.version_info.minor}")

    # Check critical imports
    critical_deps = [
        ("chromadb", "ChromaDB vector database"),
        ("spacy", "spaCy NLP"),
        ("sentence_transformers", "Sentence Transformers embeddings"),
        ("fastapi", "FastAPI web framework"),
        ("uvicorn", "Uvicorn ASGI server"),
    ]

    for module_name, description in critical_deps:
        try:
            __import__(module_name)
        except ImportError:
            errors.append(f"Missing dependency: {description} ({module_name})")

    # Check config directory
    config_dir = os.path.expanduser("~/.chimera")
    if not os.path.exists(config_dir):
        # Not an error, will be created on first run
        pass

    return errors


def print_banner():
    """Print CHIMERA startup banner."""
    print("""
   ██████╗██╗  ██╗██╗███╗   ███╗███████╗██████╗  █████╗
  ██╔════╝██║  ██║██║████╗ ████║██╔════╝██╔══██╗██╔══██╗
  ██║     ███████║██║██╔████╔██║█████╗  ██████╔╝███████║
  ██║     ██╔══██║██║██║╚██╔╝██║██╔══╝  ██╔══██╗██╔══██║
  ╚██████╗██║  ██║██║██║ ╚═╝ ██║███████╗██║  ██║██║  ██║
   ╚═════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝

  Bootstrap Loader - Controlled Startup Sequence
""")


def main():
    """Bootstrap entry point with validation."""
    # Validate environment before importing heavy dependencies
    errors = validate_environment()

    if errors:
        print("\n[BOOTSTRAP] Validation failed:")
        for error in errors:
            print(f"  [X] {error}")
        print("\nPlease install missing dependencies:")
        print("  pip install -e '.[dev]'")
        sys.exit(1)

    # All checks passed - now safe to import and run CLI
    # This import happens AFTER event loop policy is set
    from chimera.cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
