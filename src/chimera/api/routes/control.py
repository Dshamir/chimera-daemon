"""Control endpoints for CHIMERA API."""

from fastapi import APIRouter

from chimera.daemon import get_daemon
from chimera.queue import Job, JobPriority, JobType

router = APIRouter()


@router.get("/status")
async def get_status() -> dict:
    """Get daemon status and statistics."""
    try:
        daemon = get_daemon()
        return daemon.get_status()
    except RuntimeError:
        return {
            "error": "Daemon not running",
            "running": False,
        }


@router.post("/excavate")
async def excavate(request: dict | None = None) -> dict:
    """Trigger full excavation (files + FAE + correlate)."""
    try:
        daemon = get_daemon()
        
        scope = request or {"files": True, "fae": True, "correlate": True}
        
        # Queue excavation job
        job = Job(
            job_type=JobType.FILE_EXTRACTION,
            priority=JobPriority.P1_USER,
            payload={"scope": scope, "type": "excavate"},
        )
        
        if daemon.queue:
            job_id = await daemon.queue.enqueue(job)
            return {
                "status": "queued",
                "job_id": job_id,
                "scope": scope,
            }
        
        return {"error": "Queue not available"}
        
    except RuntimeError:
        return {
            "error": "Daemon not running",
            "status": "failed",
        }


@router.post("/fae")
async def fae_process(request: dict) -> dict:
    """Process AI conversation exports (FAE)."""
    try:
        daemon = get_daemon()
        
        path = request.get("path")
        provider = request.get("provider", "auto")
        correlate = request.get("correlate", True)
        
        if not path:
            return {"error": "path is required"}
        
        # Queue FAE job
        job = Job(
            job_type=JobType.FAE_PROCESSING,
            priority=JobPriority.P2_FAE,
            payload={
                "path": path,
                "provider": provider,
                "correlate": correlate,
            },
        )
        
        if daemon.queue:
            job_id = await daemon.queue.enqueue(job)
            return {
                "status": "queued",
                "job_id": job_id,
                "path": path,
                "provider": provider,
            }
        
        return {"error": "Queue not available"}
        
    except RuntimeError:
        return {
            "error": "Daemon not running",
            "status": "failed",
        }


@router.post("/correlate")
async def run_correlation() -> dict:
    """Trigger correlation analysis."""
    try:
        daemon = get_daemon()
        
        job = Job(
            job_type=JobType.CORRELATION,
            priority=JobPriority.P1_USER,
            payload={},
        )
        
        if daemon.queue:
            job_id = await daemon.queue.enqueue(job)
            return {
                "status": "queued",
                "job_id": job_id,
            }
        
        return {"error": "Queue not available"}
        
    except RuntimeError:
        return {
            "error": "Daemon not running",
            "status": "failed",
        }


@router.get("/jobs")
async def get_jobs() -> dict:
    """Get job queue statistics."""
    try:
        daemon = get_daemon()
        
        if daemon.queue:
            stats = await daemon.queue.get_stats()
            pending = await daemon.queue.get_pending_count()
            return {
                "pending": pending,
                "stats": stats,
            }
        
        return {"error": "Queue not available"}
        
    except RuntimeError:
        return {
            "error": "Daemon not running",
        }


@router.post("/discoveries/{discovery_id}/feedback")
async def discovery_feedback(discovery_id: str, request: dict) -> dict:
    """Provide feedback on a discovery (confirm, dismiss, correct)."""
    # TODO: Implement feedback (Sprint 3)
    action = request.get("action")  # confirm, dismiss, correct
    notes = request.get("notes")
    
    return {
        "id": discovery_id,
        "action": action,
        "notes": notes,
        "message": "Feedback not yet implemented (Sprint 3)",
    }
