"""Graph sync endpoints for CHIMERA API.

Handles SIF pointer graph integration.
"""

import json
from datetime import datetime

from fastapi import APIRouter

from chimera.correlation.engine import get_correlation_engine
from chimera.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/graph/export")
async def export_graph() -> dict:
    """Export discoveries as SIF pointer graph nodes."""
    try:
        engine = get_correlation_engine()
        nodes = engine.export_discoveries_as_graph_nodes()
        
        return {
            "nodes": nodes,
            "count": len(nodes),
            "exported_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Graph export failed: {e}")
        return {
            "nodes": [],
            "count": 0,
            "error": str(e),
        }


@router.post("/graph/sync")
async def sync_graph(request: dict) -> dict:
    """Sync discoveries to SIF knowledge base on GitHub.
    
    This endpoint prepares the data for sync. Actual GitHub push
    should be done via CLI or external tool with proper auth.
    """
    repo = request.get("repo", "Dshamir/sif-knowledge-base")
    path = request.get("path", "chimera/discoveries.yaml")
    dry_run = request.get("dry_run", False)
    
    try:
        engine = get_correlation_engine()
        nodes = engine.export_discoveries_as_graph_nodes()
        
        if dry_run:
            return {
                "dry_run": True,
                "nodes": nodes,
                "count": len(nodes),
                "target": f"{repo}/{path}",
            }
        
        # For actual sync, return the prepared data
        # The CLI or external tool handles the actual GitHub push
        
        import yaml
        content = yaml.dump({
            "source": "chimera",
            "exported_at": datetime.now().isoformat(),
            "discoveries": nodes,
        }, default_flow_style=False)
        
        return {
            "success": True,
            "count": len(nodes),
            "target": f"{repo}/{path}",
            "content": content,
            "message": "Data prepared for sync. Use CLI with GitHub auth to push.",
        }
        
    except Exception as e:
        logger.error(f"Graph sync failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.get("/graph/status")
async def graph_status() -> dict:
    """Get graph sync status."""
    try:
        engine = get_correlation_engine()
        nodes = engine.export_discoveries_as_graph_nodes()
        
        # Count by type
        by_type = {}
        for node in nodes:
            node_type = node.get("type", "unknown")
            by_type[node_type] = by_type.get(node_type, 0) + 1
        
        return {
            "total_nodes": len(nodes),
            "by_type": by_type,
            "ready_to_sync": len(nodes) > 0,
        }
    except Exception as e:
        return {
            "total_nodes": 0,
            "error": str(e),
        }
