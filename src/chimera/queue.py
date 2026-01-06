"""Job queue for CHIMERA extraction tasks.

Async job queue backed by SQLite for persistence.
"""

import asyncio
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from chimera.config import DEFAULT_CONFIG_DIR
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


class JobType(Enum):
    """Types of extraction jobs."""
    FILE_EXTRACTION = "file_extraction"
    BATCH_EXTRACTION = "batch_extraction"
    FAE_PROCESSING = "fae_processing"
    CORRELATION = "correlation_analysis"
    DISCOVERY = "discovery_surfacing"
    GRAPH_UPDATE = "graph_update"


class JobStatus(Enum):
    """Job status values."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Job priority levels."""
    P1_USER = 1      # User-triggered
    P2_FAE = 2       # FAE processing
    P3_RECENT = 3    # Recent file changes
    P4_SCHEDULED = 4 # Scheduled tasks
    P5_BACKGROUND = 5 # Background tasks


@dataclass
class Job:
    """A queued extraction job."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_type: JobType = JobType.FILE_EXTRACTION
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.P3_RECENT
    payload: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3


class JobQueue:
    """Persistent job queue backed by SQLite."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = DEFAULT_CONFIG_DIR / "jobs.db"
        self.db_path = db_path
        self._queue: asyncio.PriorityQueue[tuple[int, str, Job]] = asyncio.PriorityQueue()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with WAL mode for concurrency."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                priority INTEGER NOT NULL DEFAULT 3,
                payload TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error TEXT,
                retry_count INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status 
            ON jobs(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_priority 
            ON jobs(priority, created_at)
        """)
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Job database initialized: {self.db_path}")
    
    def _row_to_job(self, row: tuple) -> Job:
        """Convert database row to Job."""
        return Job(
            id=row[0],
            job_type=JobType(row[1]),
            status=JobStatus(row[2]),
            priority=JobPriority(row[3]),
            payload=json.loads(row[4]) if row[4] else {},
            created_at=datetime.fromisoformat(row[5]),
            started_at=datetime.fromisoformat(row[6]) if row[6] else None,
            completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
            error=row[8],
            retry_count=row[9] or 0,
        )
    
    async def enqueue(self, job: Job) -> str:
        """Add a job to the queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO jobs (id, job_type, status, priority, payload, created_at, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            job.id,
            job.job_type.value,
            job.status.value,
            job.priority.value,
            json.dumps(job.payload),
            job.created_at.isoformat(),
            job.retry_count,
        ))
        
        conn.commit()
        conn.close()
        
        # Add to in-memory queue
        await self._queue.put((job.priority.value, job.created_at.isoformat(), job))
        
        logger.debug(f"Job enqueued: {job.id} ({job.job_type.value})")
        return job.id
    
    async def dequeue(self, timeout: float = 1.0) -> Job | None:
        """Get the next job from the queue."""
        try:
            _, _, job = await asyncio.wait_for(
                self._queue.get(), 
                timeout=timeout
            )
            return job
        except asyncio.TimeoutError:
            return None
    
    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
    ) -> None:
        """Update job status."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        if status == JobStatus.RUNNING:
            cursor.execute("""
                UPDATE jobs SET status = ?, started_at = ?
                WHERE id = ?
            """, (status.value, now, job_id))
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
            cursor.execute("""
                UPDATE jobs SET status = ?, completed_at = ?, error = ?
                WHERE id = ?
            """, (status.value, now, error, job_id))
        else:
            cursor.execute("""
                UPDATE jobs SET status = ?
                WHERE id = ?
            """, (status.value, job_id))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Job {job_id} status updated: {status.value}")
    
    async def get_pending_count(self) -> int:
        """Get count of pending jobs."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM jobs WHERE status = 'pending'
        """)
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    async def get_stats(self) -> dict:
        """Get job queue statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Count by status
        cursor.execute("""
            SELECT status, COUNT(*) FROM jobs GROUP BY status
        """)
        stats["by_status"] = dict(cursor.fetchall())
        
        # Count by type
        cursor.execute("""
            SELECT job_type, COUNT(*) FROM jobs GROUP BY job_type
        """)
        stats["by_type"] = dict(cursor.fetchall())
        
        # Recent failures
        cursor.execute("""
            SELECT COUNT(*) FROM jobs 
            WHERE status = 'failed' 
            AND completed_at > datetime('now', '-1 hour')
        """)
        stats["recent_failures"] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    async def load_pending_jobs(self) -> int:
        """Load pending jobs from database into memory queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM jobs 
            WHERE status = 'pending'
            ORDER BY priority, created_at
        """)
        
        count = 0
        for row in cursor.fetchall():
            job = self._row_to_job(row)
            await self._queue.put((job.priority.value, job.created_at.isoformat(), job))
            count += 1
        
        conn.close()
        logger.debug(f"Loaded {count} pending jobs from database")
        return count
    
    async def cleanup_old_jobs(self, days: int = 7) -> int:
        """Remove completed/failed jobs older than specified days."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM jobs
            WHERE status IN ('completed', 'failed', 'cancelled')
            AND completed_at < datetime('now', ?)
        """, (f"-{days} days",))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Cleaned up {deleted} old jobs")
        return deleted

    async def get_current_job(self) -> Job | None:
        """Get the currently running job."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM jobs
            WHERE status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_job(row)
        return None

    async def get_recent_jobs(self, limit: int = 10) -> list[Job]:
        """Get recent jobs (completed, failed, running)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM jobs
            WHERE status IN ('completed', 'failed', 'running')
            ORDER BY COALESCE(completed_at, started_at, created_at) DESC
            LIMIT ?
        """, (limit,))

        jobs = [self._row_to_job(row) for row in cursor.fetchall()]
        conn.close()
        return jobs
