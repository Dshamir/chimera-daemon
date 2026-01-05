"""Control endpoints for CHIMERA API."""

from fastapi import APIRouter

from chimera.correlation.engine import get_correlation_engine
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


@router.post("/correlate/run")
async def run_correlation_now() -> dict:
    """Run correlation immediately (synchronous)."""
    try:
        engine = get_correlation_engine()
        result = await engine.run_correlation()
        
        return {
            "status": "completed" if result.success else "failed",
            "result": result.to_dict(),
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
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
    """Provide feedback on a discovery (confirm, dismiss)."""
    action = request.get("action")  # confirm, dismiss
    notes = request.get("notes")
    
    if action not in ("confirm", "dismiss"):
        return {"error": "action must be 'confirm' or 'dismiss'"}
    
    try:
        engine = get_correlation_engine()
        
        if action == "confirm":
            success = engine.confirm_discovery(discovery_id, notes)
        else:
            success = engine.dismiss_discovery(discovery_id, notes)
        
        return {
            "id": discovery_id,
            "action": action,
            "success": success,
            "notes": notes,
        }
    except Exception as e:
        return {
            "id": discovery_id,
            "action": action,
            "success": False,
            "error": str(e),
        }


@router.get("/correlation/stats")
async def correlation_stats() -> dict:
    """Get correlation engine statistics."""
    try:
        engine = get_correlation_engine()
        return engine.get_stats()
    except Exception as e:
        return {"error": str(e)}
