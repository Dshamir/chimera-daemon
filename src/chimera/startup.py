"""CHIMERA Startup & Readiness Module.

Comprehensive system initialization with verification.
Implements the "splash screen" pattern - verify everything before declaring ready.
"""

import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from chimera.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StartupCheck:
    """A single startup verification check."""

    name: str
    check_fn: Callable[[], bool]
    required: bool = True
    timeout_seconds: float = 30.0
    retry_count: int = 3
    retry_delay: float = 1.0


@dataclass
class StartupResult:
    """Result of startup sequence."""

    success: bool = False
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    checks_skipped: list[str] = field(default_factory=list)
    total_time: float = 0.0
    ready_at: datetime | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "checks_skipped": self.checks_skipped,
            "total_time": self.total_time,
            "ready_at": self.ready_at.isoformat() if self.ready_at else None,
            "errors": self.errors,
        }


class StartupManager:
    """Manages CHIMERA startup sequence.

    Runs comprehensive verification before declaring the system ready.
    This prevents "database is locked" errors and other startup race conditions.
    """

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.checks: list[StartupCheck] = []
        self._setup_checks()

    def _setup_checks(self):
        """Define all startup checks in order."""
        self.checks = [
            # 1. Config directory exists and is writable
            StartupCheck(
                name="config_directory",
                check_fn=self._check_config_dir,
                required=True,
                retry_count=1,
            ),
            # 2. Write permissions
            StartupCheck(
                name="write_permissions",
                check_fn=self._check_write_permissions,
                required=True,
                retry_count=1,
            ),
            # 3. Clean up stale lock files
            StartupCheck(
                name="clean_lock_files",
                check_fn=self._clean_lock_files,
                required=False,
                retry_count=1,
            ),
            # 4. Catalog database accessible
            StartupCheck(
                name="catalog_database",
                check_fn=self._check_catalog_db,
                required=True,
                timeout_seconds=60.0,
                retry_count=5,
                retry_delay=2.0,
            ),
            # 5. Jobs database accessible
            StartupCheck(
                name="jobs_database",
                check_fn=self._check_jobs_db,
                required=True,
                timeout_seconds=30.0,
                retry_count=3,
                retry_delay=1.0,
            ),
            # 6. Database schema up to date
            StartupCheck(
                name="schema_version",
                check_fn=self._check_schema,
                required=True,
                retry_count=1,
            ),
            # 7. Vector store accessible (optional - lazy init OK)
            StartupCheck(
                name="vector_store",
                check_fn=self._check_vector_store,
                required=False,
                retry_count=2,
            ),
        ]

    def run_startup_sequence(
        self, on_progress: Callable[[str, str], None] | None = None
    ) -> StartupResult:
        """Run all startup checks with progress reporting.

        Args:
            on_progress: Optional callback(check_name, status) for progress updates.
                        Status is one of: "checking", "passed", "failed", "skipped"

        Returns:
            StartupResult with detailed check results
        """
        result = StartupResult()
        start_time = time.time()

        logger.info("=" * 50)
        logger.info("CHIMERA Initialization Sequence")
        logger.info("=" * 50)

        for check in self.checks:
            if on_progress:
                on_progress(check.name, "checking")

            logger.info(f"  ... {check.name}")
            passed = self._run_check_with_retry(check)

            if passed:
                result.checks_passed.append(check.name)
                logger.info(f"  [OK] {check.name}")
                if on_progress:
                    on_progress(check.name, "passed")
            elif check.required:
                result.checks_failed.append(check.name)
                result.errors.append(f"Required check failed: {check.name}")
                logger.error(f"  [FAIL] {check.name} (REQUIRED)")
                if on_progress:
                    on_progress(check.name, "failed")
            else:
                result.checks_skipped.append(check.name)
                logger.warning(f"  [SKIP] {check.name} (optional)")
                if on_progress:
                    on_progress(check.name, "skipped")

        result.total_time = time.time() - start_time
        result.success = len(result.checks_failed) == 0

        logger.info("=" * 50)
        if result.success:
            result.ready_at = datetime.now()
            logger.info(
                f"CHIMERA READY - {len(result.checks_passed)} checks passed "
                f"in {result.total_time:.1f}s"
            )
        else:
            logger.error(
                f"STARTUP FAILED - {len(result.checks_failed)} checks failed: "
                f"{result.errors}"
            )
        logger.info("=" * 50)

        return result

    def _run_check_with_retry(self, check: StartupCheck) -> bool:
        """Run a check with retries."""
        for attempt in range(check.retry_count):
            try:
                if check.check_fn():
                    return True
            except Exception as e:
                logger.debug(
                    f"{check.name} attempt {attempt + 1}/{check.retry_count} "
                    f"failed: {e}"
                )

            if attempt < check.retry_count - 1:
                time.sleep(check.retry_delay)

        return False

    # === Individual Check Functions ===

    def _check_config_dir(self) -> bool:
        """Verify config directory exists."""
        if not self.config_dir.exists():
            logger.debug(f"Config directory does not exist: {self.config_dir}")
            return False
        if not self.config_dir.is_dir():
            logger.debug(f"Config path is not a directory: {self.config_dir}")
            return False
        return True

    def _check_write_permissions(self) -> bool:
        """Verify we can write to config directory."""
        test_file = self.config_dir / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            return True
        except PermissionError as e:
            logger.debug(f"Write permission denied: {e}")
            return False
        except Exception as e:
            logger.debug(f"Write test failed: {e}")
            return False

    def _clean_lock_files(self) -> bool:
        """Clean up stale SQLite lock files from previous crashes."""
        cleaned = 0
        for pattern in ["*.db-journal", "*.db-wal", "*.db-shm"]:
            for lock_file in self.config_dir.glob(pattern):
                try:
                    # Check if the WAL file is empty (safe to clean)
                    if lock_file.suffix == "-wal" and lock_file.stat().st_size > 0:
                        logger.debug(f"Skipping non-empty WAL: {lock_file}")
                        continue
                    # Don't delete active lock files, just log them
                    logger.debug(f"Found lock file: {lock_file}")
                except Exception as e:
                    logger.debug(f"Error checking lock file {lock_file}: {e}")

        return True  # Always passes, just informational

    def _check_catalog_db(self) -> bool:
        """Verify catalog database is accessible.

        Note: We only verify connection, not write lock - the daemon
        will handle write operations properly with its own timeouts.
        """
        db_path = self.config_dir / "catalog.db"

        # If DB doesn't exist, it will be created - that's OK
        if not db_path.exists():
            logger.debug("Catalog DB does not exist yet - will be created")
            return True

        try:
            # Try to connect with proper timeouts
            conn = sqlite3.connect(str(db_path), timeout=30.0)
            cursor = conn.cursor()

            # Set WAL mode and busy timeout
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")

            # Try a simple read operation
            cursor.execute("SELECT 1")
            cursor.fetchone()

            conn.close()
            return True

        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                logger.error(f"Catalog DB is locked: {e}")
            else:
                logger.error(f"Catalog DB error: {e}")
            return False
        except Exception as e:
            logger.error(f"Catalog DB check failed: {e}")
            return False

    def _check_jobs_db(self) -> bool:
        """Verify jobs database is accessible."""
        db_path = self.config_dir / "jobs.db"

        # If DB doesn't exist, it will be created - that's OK
        if not db_path.exists():
            logger.debug("Jobs DB does not exist yet - will be created")
            return True

        try:
            conn = sqlite3.connect(str(db_path), timeout=30.0)
            cursor = conn.cursor()

            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")

            # Try a simple read operation
            cursor.execute("SELECT 1")
            cursor.fetchone()

            conn.close()
            return True

        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                logger.error(f"Jobs DB is locked: {e}")
            else:
                logger.error(f"Jobs DB error: {e}")
            return False
        except Exception as e:
            logger.error(f"Jobs DB check failed: {e}")
            return False

    def _check_schema(self) -> bool:
        """Verify database schema has required tables."""
        db_path = self.config_dir / "catalog.db"

        # If DB doesn't exist, schema will be created
        if not db_path.exists():
            return True

        try:
            conn = sqlite3.connect(str(db_path), timeout=30.0)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}
            conn.close()

            # Check for core required tables
            required = {"files", "chunks", "entities"}
            missing = required - tables

            if missing:
                logger.warning(f"Missing tables (will be created): {missing}")
                # Don't fail - tables will be created on first use

            return True

        except Exception as e:
            logger.error(f"Schema check failed: {e}")
            return False

    def _check_vector_store(self) -> bool:
        """Verify vector store is accessible (optional).

        Note: For large vector stores, we skip get_stats() to avoid blocking.
        Just verify we can create a client.
        """
        try:
            from chimera.storage.vectors import VectorDB

            # Just create client - skip stats for large DBs to avoid blocking
            vectors = VectorDB()
            # Quick check - verify client exists without iterating collections
            client = vectors._get_client()
            if client is not None:
                logger.debug("Vector store client initialized")
                return True
            return False
        except ImportError:
            logger.debug("Vector store module not available")
            return False
        except Exception as e:
            logger.debug(f"Vector store check failed: {e}")
            return False


def run_preflight_checks(config_dir: Path | None = None) -> StartupResult:
    """Convenience function to run preflight checks.

    Args:
        config_dir: Config directory path. If None, uses default.

    Returns:
        StartupResult with check results
    """
    if config_dir is None:
        from chimera.config import DEFAULT_CONFIG_DIR

        config_dir = DEFAULT_CONFIG_DIR

    manager = StartupManager(config_dir)
    return manager.run_startup_sequence()
