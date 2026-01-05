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
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": __version__,
        }
    
    return app


# Default app for development
app = create_api_app()
