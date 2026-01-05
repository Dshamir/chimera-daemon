"""Tests for job queue."""

import pytest

from chimera.queue import Job, JobPriority, JobQueue, JobStatus, JobType


@pytest.mark.asyncio
async def test_job_creation():
    """Test creating a job."""
    job = Job(
        job_type=JobType.FILE_EXTRACTION,
        priority=JobPriority.P3_RECENT,
        payload={"path": "/test/file.pdf"},
    )
    
    assert job.id is not None
    assert job.status == JobStatus.PENDING
    assert job.job_type == JobType.FILE_EXTRACTION


@pytest.mark.asyncio
async def test_queue_enqueue_dequeue(temp_dir):
    """Test enqueueing and dequeueing jobs."""
    queue = JobQueue(db_path=temp_dir / "test_jobs.db")
    
    job = Job(
        job_type=JobType.FILE_EXTRACTION,
        payload={"path": "/test/file.pdf"},
    )
    
    # Enqueue
    job_id = await queue.enqueue(job)
    assert job_id == job.id
    
    # Check pending count
    count = await queue.get_pending_count()
    assert count == 1
    
    # Dequeue
    dequeued = await queue.dequeue()
    assert dequeued is not None
    assert dequeued.id == job.id


@pytest.mark.asyncio
async def test_queue_priority(temp_dir):
    """Test job priority ordering."""
    queue = JobQueue(db_path=temp_dir / "test_jobs.db")
    
    # Add low priority job first
    low_job = Job(
        job_type=JobType.CORRELATION,
        priority=JobPriority.P5_BACKGROUND,
    )
    await queue.enqueue(low_job)
    
    # Add high priority job second
    high_job = Job(
        job_type=JobType.FILE_EXTRACTION,
        priority=JobPriority.P1_USER,
    )
    await queue.enqueue(high_job)
    
    # Should get high priority first
    first = await queue.dequeue()
    assert first.priority == JobPriority.P1_USER
