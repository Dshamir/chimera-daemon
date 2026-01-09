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


@router.post("/shutdown")
async def shutdown() -> dict:
    """Shutdown the daemon gracefully."""
    try:
        daemon = get_daemon()
        daemon._shutdown_event.set()
        return {
            "status": "shutting_down",
            "message": "Daemon shutdown initiated",
        }
    except RuntimeError:
        return {
            "error": "Daemon not running",
            "status": "failed",
        }


@router.post("/excavate")
async def excavate(request: dict | None = None) -> dict:
    """Trigger full excavation (files + FAE + correlate)."""
    try:
        daemon = get_daemon()

        scope = request or {"files": True, "fae": True, "correlate": True}
        paths = request.get("paths") if request else None

        # Queue batch extraction job
        job = Job(
            job_type=JobType.BATCH_EXTRACTION,
            priority=JobPriority.P1_USER,
            payload={"scope": scope, "paths": paths},
        )

        if daemon.queue:
            job_id = await daemon.queue.enqueue(job)
            return {
                "status": "queued",
                "job_id": job_id,
                "scope": scope,
                "paths": paths,
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
        daemon = get_daemon()
        daemon.start_operation("correlation", {"source": "sync_api"})

        success = False
        error = None
        try:
            engine = get_correlation_engine()
            result = await engine.run_correlation()

            if result.success:
                success = True
                daemon.correlations_run += 1
                daemon.discoveries_surfaced = result.discoveries_surfaced
                daemon.patterns_detected = result.patterns_detected
                daemon._last_correlation_time = result.total_time  # For ETA
            else:
                error = result.error

            return {
                "status": "completed" if result.success else "failed",
                "result": result.to_dict(),
            }
        except Exception as e:
            error = str(e)
            raise
        finally:
            daemon.end_operation(success=success, error=error)
    except RuntimeError:
        # Daemon not running, run without tracking
        try:
            engine = get_correlation_engine()
            result = await engine.run_correlation()
            return {
                "status": "completed" if result.success else "failed",
                "result": result.to_dict(),
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
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


@router.get("/jobs/current")
async def get_current_job() -> dict:
    """Get the currently running job."""
    try:
        daemon = get_daemon()

        if daemon.queue:
            job = await daemon.queue.get_current_job()
            if job:
                elapsed = None
                if job.started_at:
                    from datetime import datetime
                    elapsed = (datetime.now() - job.started_at).total_seconds()

                return {
                    "running": True,
                    "job": {
                        "id": job.id,
                        "type": job.job_type.value,
                        "status": job.status.value,
                        "payload": job.payload,
                        "started_at": job.started_at.isoformat() if job.started_at else None,
                        "elapsed_seconds": elapsed,
                    },
                }
            return {"running": False, "job": None}

        return {"error": "Queue not available"}

    except RuntimeError:
        return {"error": "Daemon not running"}


@router.get("/jobs/recent")
async def get_recent_jobs(limit: int = 10) -> dict:
    """Get recent job history."""
    try:
        daemon = get_daemon()

        if daemon.queue:
            jobs = await daemon.queue.get_recent_jobs(limit)
            return {
                "jobs": [
                    {
                        "id": j.id,
                        "type": j.job_type.value,
                        "status": j.status.value,
                        "payload": j.payload,
                        "created_at": j.created_at.isoformat(),
                        "started_at": j.started_at.isoformat() if j.started_at else None,
                        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                        "error": j.error,
                    }
                    for j in jobs
                ]
            }

        return {"error": "Queue not available"}

    except RuntimeError:
        return {"error": "Daemon not running"}


@router.get("/telemetry")
async def get_telemetry() -> dict:
    """Get comprehensive telemetry data for dashboard.

    Optimized to use a single database connection for all queries.
    """
    import os
    from pathlib import Path

    try:
        daemon = get_daemon()

        # Use daemon's catalog if available, otherwise create one instance
        # This avoids multiple expensive CatalogDB initializations
        from chimera.storage.catalog import CatalogDB
        catalog = daemon.pipeline.catalog if daemon.pipeline else CatalogDB()

        # Get all stats in one connection
        conn = catalog.get_connection()
        cursor = conn.cursor()

        # === Catalog Stats (combined queries) ===
        catalog_stats = {}

        # File counts by status
        cursor.execute("SELECT status, COUNT(*) FROM files GROUP BY status")
        catalog_stats["files_by_status"] = dict(cursor.fetchall())

        # File counts by extension
        cursor.execute("""
            SELECT extension, COUNT(*) FROM files
            WHERE extension IS NOT NULL
            GROUP BY extension ORDER BY COUNT(*) DESC LIMIT 10
        """)
        catalog_stats["files_by_extension"] = dict(cursor.fetchall())

        # Total counts
        cursor.execute("SELECT COUNT(*) FROM files")
        catalog_stats["total_files"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM chunks")
        catalog_stats["total_chunks"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM entities")
        catalog_stats["total_entities"] = cursor.fetchone()[0]

        # Entity counts by type
        cursor.execute("""
            SELECT entity_type, COUNT(*) FROM entities
            GROUP BY entity_type ORDER BY COUNT(*) DESC LIMIT 10
        """)
        catalog_stats["entities_by_type"] = dict(cursor.fetchall())

        cursor.execute("SELECT COUNT(*) FROM discoveries WHERE status = 'active'")
        catalog_stats["active_discoveries"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM conversations")
        catalog_stats["total_conversations"] = cursor.fetchone()[0]

        # === Discovery Stats ===
        cursor.execute("""
            SELECT discovery_type, COUNT(*) FROM discoveries
            GROUP BY discovery_type ORDER BY COUNT(*) DESC
        """)
        discoveries_by_type = dict(cursor.fetchall())

        cursor.execute("""
            SELECT id, discovery_type, title, confidence, status
            FROM discoveries WHERE status = 'active'
            ORDER BY confidence DESC LIMIT 5
        """)
        top_discoveries = [
            {"id": row[0], "type": row[1], "title": row[2], "confidence": row[3], "status": row[4]}
            for row in cursor.fetchall()
        ]

        # === Multimedia Stats ===
        multimedia = {
            "images_indexed": 0, "images_with_gps": 0, "images_with_ai": 0,
            "audio_files": 0, "audio_transcribed": 0, "unique_locations": 0,
        }
        try:
            cursor.execute("SELECT COUNT(*) FROM image_metadata")
            multimedia["images_indexed"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM image_metadata WHERE latitude IS NOT NULL")
            multimedia["images_with_gps"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM image_metadata WHERE ai_description IS NOT NULL")
            multimedia["images_with_ai"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM audio_metadata")
            multimedia["audio_files"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM audio_metadata WHERE transcription_status = 'completed'")
            multimedia["audio_transcribed"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(DISTINCT location_name) FROM gps_locations WHERE location_name IS NOT NULL")
            multimedia["unique_locations"] = cursor.fetchone()[0]
        except Exception:
            pass  # Tables may not exist yet

        conn.close()

        # === System Stats (psutil) ===
        system = {"cpu_percent": 0, "memory_used_gb": 0, "memory_total_gb": 16, "memory_percent": 0}
        try:
            import psutil
            system["cpu_percent"] = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            system["memory_used_gb"] = mem.used / (1024**3)
            system["memory_total_gb"] = mem.total / (1024**3)
            system["memory_percent"] = mem.percent
            try:
                io = psutil.disk_io_counters()
                system["disk_read_bytes"] = io.read_bytes
                system["disk_write_bytes"] = io.write_bytes
            except Exception:
                pass
        except ImportError:
            pass

        # === GPU Stats (nvidia-smi) ===
        gpu = {"available": False}
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(', ')
                if len(parts) >= 4:
                    gpu = {
                        "available": True,
                        "device": parts[0].strip(),
                        "memory_total_gb": float(parts[1].strip()) / 1024,
                        "memory_used_gb": float(parts[2].strip()) / 1024,
                        "utilization_percent": float(parts[3].strip()),
                    }
        except Exception:
            pass

        # === Current Operation ===
        current_job = daemon.get_current_operation()
        if not current_job and daemon.queue:
            job = await daemon.queue.get_current_job()
            if job:
                from datetime import datetime
                elapsed = (datetime.now() - job.started_at).total_seconds() if job.started_at else None
                current_job = {
                    "id": job.id, "type": job.job_type.value,
                    "payload": job.payload, "elapsed_seconds": elapsed, "eta_seconds": None,
                }

        # === Patterns Count ===
        patterns_detected = daemon.patterns_detected
        if patterns_detected == 0 and daemon.correlation_engine:
            try:
                patterns_detected = len(daemon.correlation_engine.pattern_detector._patterns)
            except Exception:
                pass

        # === Storage Sizes ===
        config_dir = Path(os.path.expanduser("~/.chimera"))
        catalog_size = (config_dir / "catalog.db").stat().st_size / (1024**2) if (config_dir / "catalog.db").exists() else 0
        jobs_db_size = (config_dir / "jobs.db").stat().st_size / (1024**2) if (config_dir / "jobs.db").exists() else 0
        vectors_size = sum(
            f.stat().st_size for f in (config_dir / "vectors").rglob("*") if f.is_file()
        ) / (1024**3) if (config_dir / "vectors").exists() else 0

        # Build status dict (avoiding extra get_status call)
        status = {
            "version": daemon.version if hasattr(daemon, 'version') else "0.1.0",
            "running": daemon.running,
            "uptime_seconds": daemon.uptime_seconds,
            "started_at": daemon.started_at.isoformat() if daemon.started_at else None,
            "dev_mode": daemon.dev_mode,
            "stats": {
                "files_detected": daemon.files_detected,
                "files_indexed": daemon.files_indexed,
                "jobs_processed": daemon.jobs_processed,
                "jobs_failed": daemon.jobs_failed,
                "correlations_run": daemon.correlations_run,
                "patterns_detected": daemon.patterns_detected,
                "discoveries_surfaced": daemon.discoveries_surfaced,
            },
            "catalog": catalog_stats,
            "vectors": {},
            "correlation": {},
            "config": {
                "sources": len(daemon.config.sources),
                "fae_enabled": daemon.config.fae.enabled,
                "api_port": daemon.config.api.port,
            },
        }

        return {
            "status": status,
            "system": system,
            "gpu": gpu,
            "current_job": current_job,
            "storage": {"catalog_mb": catalog_size, "jobs_db_mb": jobs_db_size, "vectors_gb": vectors_size},
            "entities_by_type": catalog_stats.get("entities_by_type", {}),
            "patterns_detected": patterns_detected,
            "discoveries_by_type": discoveries_by_type,
            "top_discoveries": top_discoveries,
            "multimedia": multimedia,
        }

    except RuntimeError:
        return {"error": "Daemon not running"}
