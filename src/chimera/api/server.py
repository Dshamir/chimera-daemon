"""FastAPI server for CHIMERA."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chimera import __version__
from chimera.api.routes import control, graph, query


def create_api_app(
    lifespan: Callable[[FastAPI], AsyncGenerator[None, None]] | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="CHIMERA API",
        description="Cognitive History Integration & Memory Extraction Runtime Agent",
        version=__version__,
        lifespan=lifespan,
    )
    
    # CORS - localhost only by default
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(query.router, prefix="/api/v1", tags=["query"])
    app.include_router(control.router, prefix="/api/v1", tags=["control"])
    app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
    
    @app.get("/")
    async def root() -> dict:
        """Root endpoint."""
        return {
            "name": "CHIMERA",
            "version": __version__,
            "description": "Cognitive History Integration & Memory Extraction Runtime Agent",
            "docs": "/docs",
        }
    
    @app.get("/api/v1/health")
    async def health() -> dict:
        """Health check endpoint with basic verification."""
        try:
            from chimera.daemon import get_daemon

            daemon = get_daemon()
            return {
                "status": "healthy" if daemon.running else "degraded",
                "version": __version__,
                "uptime_seconds": daemon.uptime_seconds,
                "startup_complete": getattr(daemon, "_startup_complete", False),
            }
        except RuntimeError:
            return {
                "status": "unhealthy",
                "version": __version__,
                "error": "Daemon not initialized",
            }

    @app.get("/api/v1/readiness")
    async def readiness() -> dict:
        """Full readiness check - verifies all systems operational.

        Use this endpoint to wait for system to be fully ready before
        accepting commands. More comprehensive than /health.
        """
        from chimera.daemon import get_daemon

        checks = {}
        all_ready = True

        # 1. Daemon running
        try:
            daemon = get_daemon()
            checks["daemon"] = daemon.running
            if not daemon.running:
                all_ready = False
        except RuntimeError:
            checks["daemon"] = False
            all_ready = False

        # 2. Startup sequence completed
        try:
            daemon = get_daemon()
            startup_complete = getattr(daemon, "_startup_complete", False)
            checks["startup_complete"] = startup_complete
            if not startup_complete:
                all_ready = False
        except RuntimeError:
            checks["startup_complete"] = False
            all_ready = False

        # 3. Database accessible
        try:
            from chimera.storage.catalog import CatalogDB

            catalog = CatalogDB()
            conn = catalog.get_connection()
            conn.execute("SELECT 1")
            conn.close()
            checks["catalog_db"] = True
        except Exception as e:
            checks["catalog_db"] = False
            checks["catalog_db_error"] = str(e)
            all_ready = False

        # 4. Job queue accessible
        try:
            daemon = get_daemon()
            if daemon.queue:
                await daemon.queue.get_pending_count()
                checks["job_queue"] = True
            else:
                checks["job_queue"] = False
                all_ready = False
        except RuntimeError:
            checks["job_queue"] = False
            all_ready = False
        except Exception as e:
            checks["job_queue"] = False
            checks["job_queue_error"] = str(e)
            all_ready = False

        # 5. Watcher running
        try:
            daemon = get_daemon()
            checks["watcher"] = daemon.watcher.is_running if daemon.watcher else False
        except RuntimeError:
            checks["watcher"] = False

        return {
            "ready": all_ready,
            "checks": checks,
            "version": __version__,
        }

    return app


# Default app for development
app = create_api_app()
