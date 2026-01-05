"""CHIMERA daemon - main orchestrator.

This is the heart of CHIMERA. It coordinates:
- File watching
- Job queue processing
- Extraction pipeline
- API server
- Scheduled tasks
"""

import asyncio
import signal
import sys
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
    """Main CHIMERA daemon process.
    
    Orchestrates all components:
    - Config loading
    - File watching
    - Job queue
    - Extraction pipeline
    - API server
    - Scheduled tasks
    """
    
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
        self.pipeline = None  # Lazy loaded
        self._worker_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        
        # Stats
        self.files_detected = 0
        self.files_indexed = 0
        self.jobs_processed = 0
        self.jobs_failed = 0
    
    @property
    def uptime_seconds(self) -> float:
        """Get daemon uptime in seconds."""
        if self.started_at is None:
            return 0.0
        return (datetime.now() - self.started_at).total_seconds()
    
    def _get_pipeline(self):
        """Lazy load extraction pipeline."""
        if self.pipeline is None:
            from chimera.extractors.pipeline import ExtractionPipeline
            self.pipeline = ExtractionPipeline()
        return self.pipeline
    
    async def start(self) -> None:
        """Start the daemon and all components."""
        logger.info(f"Starting CHIMERA daemon v{__version__}")
        logger.info(f"Dev mode: {self.dev_mode}")
        
        # Ensure config directory exists
        config_dir = ensure_config_dir()
        logger.info(f"Config directory: {config_dir}")
        
        # Initialize job queue
        self.queue = JobQueue()
        await self.queue.load_pending_jobs()
        pending = await self.queue.get_pending_count()
        logger.info(f"Job queue initialized. {pending} pending jobs.")
        
        # Initialize file watcher
        self.watcher = FileWatcher(self.config)
        self.watcher.on_file_change = self._on_file_change
        
        # Mark as running
        self.running = True
        self.started_at = datetime.now()
        
        # Start file watcher
        self.watcher.start()
        logger.info("File watcher started.")
        
        # Start job worker
        self._worker_task = asyncio.create_task(self._job_worker())
        logger.info("Job worker started.")
        
        logger.info("CHIMERA daemon started successfully.")
    
    async def stop(self) -> None:
        """Stop the daemon gracefully."""
        logger.info("Stopping CHIMERA daemon...")
        self.running = False
        self._shutdown_event.set()
        
        # Stop file watcher
        if self.watcher:
            self.watcher.stop()
            logger.info("File watcher stopped.")
        
        # Cancel worker task
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Job worker stopped.")
        
        logger.info("CHIMERA daemon stopped.")
    
    async def wait_for_shutdown(self) -> None:
        """Wait until shutdown is requested."""
        await self._shutdown_event.wait()
    
    def _on_file_change(self, path: Path, event_type: str) -> None:
        """Handle file change from watcher."""
        self.files_detected += 1
        logger.debug(f"File {event_type}: {path}")
        
        # Queue extraction job
        if event_type in ("created", "modified"):
            job = Job(
                job_type=JobType.FILE_EXTRACTION,
                priority=JobPriority.P3_RECENT,
                payload={"path": str(path), "event": event_type},
            )
            # Queue in sync context (will be picked up by worker)
            asyncio.create_task(self._enqueue_job(job))
    
    async def _enqueue_job(self, job: Job) -> None:
        """Enqueue a job."""
        if self.queue:
            await self.queue.enqueue(job)
    
    async def _job_worker(self) -> None:
        """Process jobs from the queue."""
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
                    await self.queue.update_status(
                        job.id, JobStatus.FAILED, error=str(e)
                    )
                    self.jobs_failed += 1
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Job worker error: {e}")
                await asyncio.sleep(1)
    
    async def _process_job(self, job: Job) -> None:
        """Process a single job."""
        if job.job_type == JobType.FILE_EXTRACTION:
            await self._process_file_extraction(job)
        elif job.job_type == JobType.FAE_PROCESSING:
            await self._process_fae(job)
        elif job.job_type == JobType.CORRELATION:
            await self._process_correlation(job)
        elif job.job_type == JobType.DISCOVERY:
            await self._process_discovery(job)
        else:
            logger.warning(f"Unknown job type: {job.job_type}")
    
    async def _process_file_extraction(self, job: Job) -> None:
        """Process file extraction job using the pipeline."""
        path = Path(job.payload.get("path", ""))
        
        if not path.exists():
            logger.warning(f"File no longer exists: {path}")
            return
        
        logger.info(f"Extracting: {path}")
        
        # Use the extraction pipeline
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
        """Process FAE (AI export) job."""
        path = Path(job.payload.get("path", ""))
        provider = job.payload.get("provider", "auto")
        
        logger.info(f"Processing FAE: {path} (provider: {provider})")
        
        # TODO: Implement full FAE processing (Sprint 2 continuation)
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
        """Process correlation job."""
        logger.info("Running correlation analysis...")
        
        # TODO: Implement correlation (Sprint 3)
        from chimera.correlation.engine import CorrelationEngine
        
        engine = CorrelationEngine()
        patterns = await engine.run_correlation()
        
        logger.info(f"Correlation complete: {len(patterns)} patterns found")
    
    async def _process_discovery(self, job: Job) -> None:
        """Process discovery surfacing job."""
        logger.info("Surfacing discoveries...")
        
        # TODO: Implement discovery (Sprint 3)
        await asyncio.sleep(0.1)
    
    def get_status(self) -> dict:
        """Get daemon status."""
        # Get storage stats
        catalog_stats = {}
        vector_stats = {}
        
        try:
            if self.pipeline:
                catalog_stats = self.pipeline.catalog.get_stats()
                vector_stats = self.pipeline.vectors.get_stats()
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
            },
            "catalog": catalog_stats,
            "vectors": vector_stats,
            "config": {
                "sources": len(self.config.sources),
                "fae_enabled": self.config.fae.enabled,
                "api_port": self.config.api.port,
            },
        }


# Global daemon instance for API access
_daemon: ChimeraDaemon | None = None


def get_daemon() -> ChimeraDaemon:
    """Get the global daemon instance."""
    if _daemon is None:
        raise RuntimeError("Daemon not initialized")
    return _daemon


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan context manager."""
    global _daemon
    
    # Startup
    logger.info("API server starting...")
    
    if _daemon is not None:
        await _daemon.start()
    
    yield
    
    # Shutdown
    logger.info("API server shutting down...")
    if _daemon is not None:
        await _daemon.stop()


def create_app(daemon: ChimeraDaemon | None = None) -> FastAPI:
    """Create FastAPI application."""
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
    """Run the daemon with API server."""
    global _daemon
    
    # Setup logging
    log_level = "DEBUG" if dev_mode else "INFO"
    setup_logging(level=log_level)
    
    # Create daemon
    _daemon = ChimeraDaemon(config=config, dev_mode=dev_mode)
    
    # Create app
    app = create_app(_daemon)
    
    # Setup signal handlers
    def handle_signal(signum: int, frame: object) -> None:
        logger.info(f"Received signal {signum}, initiating shutdown...")
        if _daemon:
            _daemon._shutdown_event.set()
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Run server
    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning" if not dev_mode else "info",
    )


def main() -> None:
    """CLI entry point for chimerad."""
    import argparse
    
    parser = argparse.ArgumentParser(description="CHIMERA Daemon")
    parser.add_argument("--host", default="127.0.0.1", help="API host")
    parser.add_argument("--port", type=int, default=7777, help="API port")
    parser.add_argument("--dev", action="store_true", help="Development mode")
    
    args = parser.parse_args()
    
    run_daemon(
        host=args.host,
        port=args.port,
        dev_mode=args.dev,
    )


if __name__ == "__main__":
    main()
