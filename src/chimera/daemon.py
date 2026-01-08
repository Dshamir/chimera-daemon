"""CHIMERA daemon - main orchestrator.

This is the heart of CHIMERA. It coordinates:
- File watching
- Job queue processing
- Extraction pipeline
- Correlation engine
- API server
- Scheduled tasks
"""

import asyncio
import signal
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI

from chimera import __version__
from chimera.config import ChimeraConfig, ensure_config_dir, load_config
from chimera.queue import Job, JobPriority, JobQueue, JobStatus, JobType
from chimera.utils.logging import get_logger, setup_logging
from chimera.watcher import FileWatcher

logger = get_logger(__name__)


class ChimeraDaemon:
    """Main CHIMERA daemon process."""
    
    def __init__(
        self,
        config: ChimeraConfig | None = None,
        dev_mode: bool = False,
    ) -> None:
        self.config = config or load_config()
        self.dev_mode = dev_mode
        self.running = False
        self.started_at: datetime | None = None
        
        # Components (initialized on start)
        self.watcher: FileWatcher | None = None
        self.queue: JobQueue | None = None
        self.pipeline = None
        self.correlation_engine = None
        self._worker_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None  # Store main event loop
        
        # Stats
        self.files_detected = 0
        self.files_indexed = 0
        self.jobs_processed = 0
        self.jobs_failed = 0
        self.correlations_run = 0
        self.discoveries_surfaced = 0
        self.patterns_detected = 0

        # Current operation tracking (for both queued and sync operations)
        self._current_operation: dict | None = None
        self._operation_start_time: datetime | None = None
        self._last_correlation_time: float | None = None  # For ETA

        # Completion indicator (show for 3 seconds after completion)
        self._last_completed_operation: dict | None = None
        self._completion_display_until: datetime | None = None

        # Job timing history for ETA calculation (by job type)
        self._job_timing_history: dict[str, list[float]] = {}

        # Startup state tracking
        self._startup_complete: bool = False
        self._startup_result = None  # StartupResult from startup manager
    
    @property
    def uptime_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        return (datetime.now() - self.started_at).total_seconds()

    def start_operation(self, operation_type: str, details: dict | None = None) -> None:
        """Start tracking a current operation (for dashboard visibility)."""
        self._current_operation = {
            "type": operation_type,
            "details": details or {},
            "started_at": datetime.now().isoformat(),
        }
        self._operation_start_time = datetime.now()

    def end_operation(self, success: bool = True, error: str | None = None) -> None:
        """End current operation tracking with completion status."""
        from datetime import timedelta

        if self._current_operation and self._operation_start_time:
            total_time = (datetime.now() - self._operation_start_time).total_seconds()
            operation_type = self._current_operation.get("type", "unknown")

            # Store timing for future ETA calculations
            if operation_type not in self._job_timing_history:
                self._job_timing_history[operation_type] = []
            self._job_timing_history[operation_type].append(total_time)
            # Keep only last 10 timings per job type
            if len(self._job_timing_history[operation_type]) > 10:
                self._job_timing_history[operation_type] = self._job_timing_history[operation_type][-10:]

            # Store completion for 3-second display
            self._last_completed_operation = {
                **self._current_operation,
                "status": "completed" if success else "failed",
                "error": error,
                "total_time": total_time,
                "completed_at": datetime.now().isoformat(),
            }
            self._completion_display_until = datetime.now() + timedelta(seconds=3)

        self._current_operation = None
        self._operation_start_time = None

    def _estimate_eta(self, operation_type: str, elapsed: float) -> float | None:
        """Estimate remaining time based on historical average."""
        # For correlation, use last correlation time if available
        if operation_type == "correlation" and self._last_correlation_time:
            return max(0, self._last_correlation_time - elapsed)

        # For other operations, use historical average
        history = self._job_timing_history.get(operation_type, [])
        if not history:
            return None

        avg_time = sum(history) / len(history)
        return max(0, avg_time - elapsed)

    def get_current_operation(self) -> dict | None:
        """Get current operation with elapsed time, ETA, or recent completion."""
        # Show completion indicator for 3 seconds after operation ends
        if self._last_completed_operation and self._completion_display_until:
            if datetime.now() < self._completion_display_until:
                return self._last_completed_operation
            else:
                # Clear completed operation after display period
                self._last_completed_operation = None
                self._completion_display_until = None

        if not self._current_operation:
            return None

        elapsed = None
        eta = None
        if self._operation_start_time:
            elapsed = (datetime.now() - self._operation_start_time).total_seconds()
            operation_type = self._current_operation.get("type", "unknown")
            eta = self._estimate_eta(operation_type, elapsed)

        return {
            **self._current_operation,
            "status": "running",
            "elapsed_seconds": elapsed,
            "eta_seconds": eta,
        }
    
    def _get_pipeline(self):
        if self.pipeline is None:
            from chimera.extractors.pipeline import ExtractionPipeline
            self.pipeline = ExtractionPipeline()
        return self.pipeline
    
    def _get_correlation_engine(self):
        if self.correlation_engine is None:
            from chimera.correlation.engine import CorrelationEngine
            self.correlation_engine = CorrelationEngine(
                min_discovery_confidence=self.config.fae.min_confidence_to_surface,
            )
        return self.correlation_engine
    
    async def start(self) -> None:
        logger.info(f"Starting CHIMERA daemon v{__version__}")
        logger.info(f"Dev mode: {self.dev_mode}")

        # Store event loop reference for thread-safe callbacks
        self._loop = asyncio.get_running_loop()

        config_dir = ensure_config_dir()
        logger.info(f"Config directory: {config_dir}")

        # Phase 1: Run pre-flight checks
        from chimera.startup import StartupManager

        startup_mgr = StartupManager(config_dir)
        self._startup_result = startup_mgr.run_startup_sequence(
            on_progress=self._log_startup_progress
        )

        if not self._startup_result.success:
            logger.error("Startup checks failed - aborting")
            raise RuntimeError(f"Startup failed: {self._startup_result.errors}")

        # Phase 2: Initialize components
        self.queue = JobQueue()
        await self.queue.load_pending_jobs()
        pending = await self.queue.get_pending_count()
        logger.info(f"Job queue initialized. {pending} pending jobs.")
        
        self.watcher = FileWatcher(self.config)
        self.watcher.on_file_change = self._on_file_change
        
        self.running = True
        self.started_at = datetime.now()
        
        self.watcher.start()
        logger.info("File watcher started.")
        
        self._worker_task = asyncio.create_task(self._job_worker())
        logger.info("Job worker started.")

        # Phase 3: Mark startup complete
        self._startup_complete = True
        logger.info("CHIMERA daemon started successfully - ALL SYSTEMS READY")

    def _log_startup_progress(self, check_name: str, status: str) -> None:
        """Log startup check progress."""
        icons = {"checking": "...", "passed": "[OK]", "failed": "[FAIL]", "skipped": "[SKIP]"}
        logger.debug(f"  {icons.get(status, '?')} {check_name}")
    
    async def stop(self) -> None:
        logger.info("Stopping CHIMERA daemon...")
        self.running = False
        self._shutdown_event.set()
        
        if self.watcher:
            self.watcher.stop()
            logger.info("File watcher stopped.")
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Job worker stopped.")
        
        logger.info("CHIMERA daemon stopped.")
    
    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()
    
    def _on_file_change(self, path: Path, event_type: str) -> None:
        """Handle file change events from watchdog thread."""
        self.files_detected += 1
        logger.debug(f"File {event_type}: {path}")

        if event_type in ("created", "modified"):
            job = Job(
                job_type=JobType.FILE_EXTRACTION,
                priority=JobPriority.P3_RECENT,
                payload={"path": str(path), "event": event_type},
            )
            # Use stored event loop reference (thread-safe from watchdog thread)
            if self._loop is not None and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self._enqueue_job(job), self._loop)
            else:
                logger.warning(f"Event loop not available, skipping file: {path}")
    
    async def _enqueue_job(self, job: Job) -> None:
        if self.queue:
            await self.queue.enqueue(job)
    
    async def _job_worker(self) -> None:
        logger.info("Job worker running...")
        
        while self.running:
            try:
                job = await self.queue.dequeue()
                if job is None:
                    continue
                
                logger.debug(f"Processing job: {job.id} ({job.job_type.value})")
                await self.queue.update_status(job.id, JobStatus.RUNNING)
                
                try:
                    await self._process_job(job)
                    await self.queue.update_status(job.id, JobStatus.COMPLETED)
                    self.jobs_processed += 1
                except Exception as e:
                    logger.error(f"Job {job.id} failed: {e}")
                    await self.queue.update_status(job.id, JobStatus.FAILED, error=str(e))
                    self.jobs_failed += 1
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Job worker error: {e}")
                await asyncio.sleep(1)
    
    async def _process_job(self, job: Job) -> None:
        if job.job_type == JobType.FILE_EXTRACTION:
            await self._process_file_extraction(job)
        elif job.job_type == JobType.BATCH_EXTRACTION:
            await self._process_batch_extraction(job)
        elif job.job_type == JobType.FAE_PROCESSING:
            await self._process_fae(job)
        elif job.job_type == JobType.CORRELATION:
            await self._process_correlation(job)
        elif job.job_type == JobType.DISCOVERY:
            await self._process_discovery(job)
        else:
            logger.warning(f"Unknown job type: {job.job_type}")
    
    async def _process_file_extraction(self, job: Job) -> None:
        path = Path(job.payload.get("path", ""))
        
        if not path.exists():
            logger.warning(f"File no longer exists: {path}")
            return
        
        logger.info(f"Extracting: {path}")
        
        pipeline = self._get_pipeline()
        result = await pipeline.process_file(path)
        
        if result.success:
            self.files_indexed += 1
            logger.info(
                f"Indexed: {path.name} "
                f"({result.chunk_count} chunks, {result.entity_count} entities)"
            )
        else:
            logger.error(f"Extraction failed: {path}: {result.error}")
    
    async def _process_fae(self, job: Job) -> None:
        path = Path(job.payload.get("path", ""))
        provider = job.payload.get("provider", "auto")
        
        logger.info(f"Processing FAE: {path} (provider: {provider})")
        
        from chimera.extractors.fae import FAEProcessor
        
        processor = FAEProcessor()
        result = processor.process(path, provider if provider != "auto" else None)
        
        if result.success:
            logger.info(
                f"FAE processed: {path.name} "
                f"({len(result.conversations)} conversations, provider: {result.provider})"
            )
        else:
            logger.error(f"FAE failed: {path}: {result.error}")
    
    async def _process_correlation(self, job: Job) -> None:
        logger.info("Running correlation analysis...")
        self.start_operation("correlation", {"source": "queued_job", "job_id": job.id})

        success = False
        error = None
        try:
            engine = self._get_correlation_engine()
            result = await engine.run_correlation()

            if result.success:
                success = True
                self.correlations_run += 1
                self.discoveries_surfaced = result.discoveries_surfaced
                self.patterns_detected = result.patterns_detected
                self._last_correlation_time = result.total_time  # For ETA
                logger.info(
                    f"Correlation complete: {result.patterns_detected} patterns, "
                    f"{result.discoveries_surfaced} discoveries"
                )
            else:
                error = result.error
                logger.error(f"Correlation failed: {result.error}")
        except Exception as e:
            error = str(e)
            logger.error(f"Correlation failed: {e}")
        finally:
            self.end_operation(success=success, error=error)
    
    async def _process_discovery(self, job: Job) -> None:
        logger.info("Surfacing discoveries...")
        engine = self._get_correlation_engine()
        discoveries = engine.discovery_surfacer.surface_all()
        self.discoveries_surfaced = len(discoveries)
        logger.info(f"Surfaced {len(discoveries)} discoveries")

    async def _process_batch_extraction(self, job: Job) -> None:
        """Process batch extraction (excavation) - discover and queue files."""
        scope = job.payload.get("scope", {})
        explicit_paths = job.payload.get("paths")

        logger.info(f"Starting batch extraction. Scope: {scope}")

        files_queued = 0

        # Process explicit paths if provided
        if explicit_paths:
            logger.info(f"Processing {len(explicit_paths)} explicit paths")
            for p in explicit_paths:
                path = Path(p)
                if path.exists():
                    if path.is_file():
                        await self._queue_file_extraction(path)
                        files_queued += 1
                    elif path.is_dir():
                        # Recursively find files in directory
                        for file in self._discover_files_in_path(path):
                            await self._queue_file_extraction(file)
                            files_queued += 1
                else:
                    logger.warning(f"Path does not exist: {path}")

        # Discover files from configured sources if no explicit paths and files enabled
        elif scope.get("files", True):
            logger.info("Discovering files from configured sources...")
            for file in self._discover_source_files():
                await self._queue_file_extraction(file)
                files_queued += 1

        logger.info(f"Queued {files_queued} files for extraction")

        # Process FAE exports if requested
        if scope.get("fae", True) and self.config.fae.enabled:
            fae_queued = 0
            for fae_path_str in self.config.fae.watch_paths:
                fae_path = Path(fae_path_str)
                if fae_path.exists():
                    for export_file in self._discover_fae_exports(fae_path):
                        fae_job = Job(
                            job_type=JobType.FAE_PROCESSING,
                            priority=JobPriority.P2_FAE,
                            payload={"path": str(export_file), "provider": "auto"},
                        )
                        await self.queue.enqueue(fae_job)
                        fae_queued += 1
            if fae_queued:
                logger.info(f"Queued {fae_queued} FAE exports for processing")

        # Queue correlation if requested
        if scope.get("correlate", True):
            corr_job = Job(
                job_type=JobType.CORRELATION,
                priority=JobPriority.P4_SCHEDULED,  # Lower priority, runs after extractions
                payload={},
            )
            await self.queue.enqueue(corr_job)
            logger.info("Queued correlation analysis")

    async def _queue_file_extraction(self, path: Path) -> None:
        """Queue a single file for extraction."""
        file_job = Job(
            job_type=JobType.FILE_EXTRACTION,
            priority=JobPriority.P2_FAE,
            payload={"path": str(path), "event": "excavate"},
        )
        await self.queue.enqueue(file_job)

    def _discover_source_files(self) -> list[Path]:
        """Discover files from configured sources."""
        import fnmatch

        files = []
        for source in self.config.sources:
            if not source.enabled:
                continue
            source_path = Path(source.path)
            if not source_path.exists():
                logger.warning(f"Source path does not exist: {source_path}")
                continue

            logger.debug(f"Scanning source: {source_path}")

            # Build glob patterns based on file types
            extensions = source.file_types or ["*"]
            for ext in extensions:
                pattern = f"**/*.{ext}" if source.recursive else f"*.{ext}"
                try:
                    for file in source_path.glob(pattern):
                        if file.is_file() and self._should_include_file(file):
                            files.append(file)
                except PermissionError:
                    logger.debug(f"Permission denied: {source_path}")
                except Exception as e:
                    logger.debug(f"Error scanning {source_path}: {e}")

        logger.info(f"Discovered {len(files)} files from {len(self.config.sources)} sources")
        return files

    def _discover_files_in_path(self, directory: Path) -> list[Path]:
        """Discover all supported files in a directory."""
        files = []
        try:
            for file in directory.rglob("*"):
                if file.is_file() and self._should_include_file(file):
                    files.append(file)
        except PermissionError:
            logger.debug(f"Permission denied: {directory}")
        return files

    def _discover_fae_exports(self, fae_path: Path) -> list[Path]:
        """Discover FAE export files (JSON/HTML conversation exports)."""
        exports = []
        patterns = ["*.json", "*.html"]
        for pattern in patterns:
            try:
                for file in fae_path.glob(pattern):
                    if file.is_file():
                        exports.append(file)
            except PermissionError:
                pass
        return exports

    def _should_include_file(self, file: Path) -> bool:
        """Check if a file should be included based on exclusion rules."""
        import fnmatch

        file_str = str(file)

        # Check path exclusions
        for pattern in self.config.exclude.paths:
            if fnmatch.fnmatch(file_str, pattern):
                return False

        # Check filename pattern exclusions
        for pattern in self.config.exclude.patterns:
            if fnmatch.fnmatch(file.name, pattern):
                return False

        # Check size limit
        try:
            size_limit = self._parse_size(self.config.exclude.size_max)
            if file.stat().st_size > size_limit:
                return False
        except (OSError, ValueError):
            pass

        return True

    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '100MB' to bytes."""
        size_str = size_str.strip().upper()
        multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
        for suffix, mult in multipliers.items():
            if size_str.endswith(suffix):
                return int(size_str[:-len(suffix)]) * mult
        return int(size_str)
    
    def get_status(self) -> dict:
        catalog_stats = {}
        vector_stats = {}
        correlation_stats = {}

        try:
            # Always get catalog stats from database (even if pipeline not initialized)
            from chimera.storage.catalog import CatalogDB
            catalog = CatalogDB()
            catalog_stats = catalog.get_stats()
        except Exception:
            pass

        try:
            if self.pipeline:
                vector_stats = self.pipeline.vectors.get_stats()
            if self.correlation_engine:
                correlation_stats = self.correlation_engine.get_stats()
        except Exception:
            pass
        
        return {
            "version": __version__,
            "running": self.running,
            "uptime_seconds": self.uptime_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "dev_mode": self.dev_mode,
            "stats": {
                "files_detected": self.files_detected,
                "files_indexed": self.files_indexed,
                "jobs_processed": self.jobs_processed,
                "jobs_failed": self.jobs_failed,
                "correlations_run": self.correlations_run,
                "patterns_detected": self.patterns_detected,
                "discoveries_surfaced": self.discoveries_surfaced,
            },
            "catalog": catalog_stats,
            "vectors": vector_stats,
            "correlation": correlation_stats,
            "config": {
                "sources": len(self.config.sources),
                "fae_enabled": self.config.fae.enabled,
                "api_port": self.config.api.port,
            },
        }


# Global daemon instance
_daemon: ChimeraDaemon | None = None


def get_daemon() -> ChimeraDaemon:
    if _daemon is None:
        raise RuntimeError("Daemon not initialized")
    return _daemon


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _daemon
    logger.info("API server starting...")
    if _daemon is not None:
        await _daemon.start()
    yield
    logger.info("API server shutting down...")
    if _daemon is not None:
        await _daemon.stop()


def create_app(daemon: ChimeraDaemon | None = None) -> FastAPI:
    global _daemon
    _daemon = daemon
    from chimera.api.server import create_api_app
    return create_api_app(lifespan=lifespan)


def run_daemon(
    host: str = "127.0.0.1",
    port: int = 7777,
    dev_mode: bool = False,
    config: ChimeraConfig | None = None,
) -> None:
    global _daemon
    
    log_level = "DEBUG" if dev_mode else "INFO"
    setup_logging(level=log_level)
    
    _daemon = ChimeraDaemon(config=config, dev_mode=dev_mode)
    app = create_app(_daemon)
    
    def handle_signal(signum: int, frame: object) -> None:
        logger.info(f"Received signal {signum}, initiating shutdown...")
        if _daemon:
            _daemon._shutdown_event.set()
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning" if not dev_mode else "info")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="CHIMERA Daemon")
    parser.add_argument("--host", default="127.0.0.1", help="API host")
    parser.add_argument("--port", type=int, default=7777, help="API port")
    parser.add_argument("--dev", action="store_true", help="Development mode")
    args = parser.parse_args()
    run_daemon(host=args.host, port=args.port, dev_mode=args.dev)


if __name__ == "__main__":
    main()
