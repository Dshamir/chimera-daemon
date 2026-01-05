"""Discovery surfacing for CHIMERA.

Surfaces "unknown knowns" - patterns that:
1. Have high confidence
2. Emerge from behavioral evidence (not explicitly stated)
3. Span multiple sources

"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from chimera.correlation.patterns import Pattern, PatternDetector
from chimera.storage.catalog import CatalogDB
from chimera.utils.hashing import generate_id
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Discovery:
    """An unknown known - a surfaced discovery."""
    id: str
    discovery_type: str  # expertise, relationship, workflow, skill, preference
    title: str
    description: str
    confidence: float
    evidence: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)  # file_ids or entity_ids
    first_seen: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    status: Literal["active", "confirmed", "dismissed", "stale"] = "active"
    user_feedback: str | None = None
    graph_node_id: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "discovery_type": self.discovery_type,
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "sources": self.sources,
            "first_seen": self.first_seen.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "status": self.status,
            "user_feedback": self.user_feedback,
            "graph_node_id": self.graph_node_id,
        }


class DiscoverySurfacer:
    """Surfaces discoveries from patterns."""
    
    def __init__(
        self,
        catalog: CatalogDB | None = None,
        detector: PatternDetector | None = None,
        min_confidence: float = 0.7,
        min_sources: int = 2,
    ) -> None:
        self.catalog = catalog or CatalogDB()
        self.detector = detector or PatternDetector(self.catalog)
        self.min_confidence = min_confidence
        self.min_sources = min_sources
        self._discoveries: dict[str, Discovery] = {}
    
    def surface_all(self) -> dict[str, Discovery]:
        """Surface discoveries from all patterns."""
        logger.info("Surfacing discoveries...")
        
        # Detect patterns first
        patterns = self.detector.detect_all()
        
        # Convert patterns to discoveries
        for pattern in patterns.values():
            discovery = self._pattern_to_discovery(pattern)
            if discovery:
                self._discoveries[discovery.id] = discovery
        
        # Store discoveries
        self._store_discoveries()
        
        # Load any existing discoveries from DB
        self._load_existing_discoveries()
        
        logger.info(f"Surfaced {len(self._discoveries)} discoveries")
        
        return self._discoveries
    
    def _pattern_to_discovery(self, pattern: Pattern) -> Discovery | None:
        """Convert a pattern to a discovery if it meets criteria."""
        # Check confidence threshold
        if pattern.confidence < self.min_confidence:
            return None
        
        # Check source diversity
        source_count = len(pattern.source_files) + len(pattern.source_entities)
        if source_count < self.min_sources:
            return None
        
        # Map pattern type to discovery type
        discovery_type_map = {
            "expertise": "expertise",
            "relationship": "relationship",
            "workflow": "workflow",
            "heuristic": "skill",
        }
        
        discovery_type = discovery_type_map.get(pattern.pattern_type, pattern.pattern_type)
        
        discovery_id = generate_id("disc", f"{discovery_type}_{pattern.title}")
        
        return Discovery(
            id=discovery_id,
            discovery_type=discovery_type,
            title=pattern.title,
            description=pattern.description,
            confidence=pattern.confidence,
            evidence=pattern.evidence,
            sources=list(pattern.source_files) + list(pattern.source_entities),
            first_seen=pattern.first_seen or datetime.now(),
            last_updated=datetime.now(),
        )
    
    def _store_discoveries(self) -> None:
        """Store discoveries in the database."""
        conn = self.catalog.get_connection()
        cursor = conn.cursor()
        
        for discovery in self._discoveries.values():
            cursor.execute("""
                INSERT OR REPLACE INTO discoveries
                (id, discovery_type, title, description, confidence, 
                 evidence, sources, first_seen, last_updated, status,
                 user_feedback, graph_node_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                discovery.id,
                discovery.discovery_type,
                discovery.title,
                discovery.description,
                discovery.confidence,
                json.dumps(discovery.evidence),
                json.dumps(discovery.sources),
                discovery.first_seen.isoformat(),
                discovery.last_updated.isoformat(),
                discovery.status,
                discovery.user_feedback,
                discovery.graph_node_id,
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Stored {len(self._discoveries)} discoveries")
    
    def _load_existing_discoveries(self) -> None:
        """Load existing discoveries from database."""
        conn = self.catalog.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, discovery_type, title, description, confidence,
                   evidence, sources, first_seen, last_updated, status,
                   user_feedback, graph_node_id
            FROM discoveries
            WHERE status NOT IN ('dismissed')
        """)
        
        for row in cursor.fetchall():
            discovery_id = row[0]
            if discovery_id in self._discoveries:
                # Update with stored metadata
                existing = self._discoveries[discovery_id]
                existing.status = row[9]
                existing.user_feedback = row[10]
                existing.graph_node_id = row[11]
            else:
                # Load from DB (might be from previous run)
                self._discoveries[discovery_id] = Discovery(
                    id=row[0],
                    discovery_type=row[1],
                    title=row[2],
                    description=row[3],
                    confidence=row[4],
                    evidence=json.loads(row[5]) if row[5] else [],
                    sources=json.loads(row[6]) if row[6] else [],
                    first_seen=datetime.fromisoformat(row[7]) if row[7] else datetime.now(),
                    last_updated=datetime.fromisoformat(row[8]) if row[8] else datetime.now(),
                    status=row[9],
                    user_feedback=row[10],
                    graph_node_id=row[11],
                )
        
        conn.close()
    
    def confirm(self, discovery_id: str, feedback: str | None = None) -> bool:
        """Confirm a discovery as accurate."""
        if discovery_id not in self._discoveries:
            return False
        
        discovery = self._discoveries[discovery_id]
        discovery.status = "confirmed"
        discovery.user_feedback = feedback
        discovery.last_updated = datetime.now()
        
        self._update_discovery_status(discovery)
        
        logger.info(f"Discovery confirmed: {discovery.title}")
        return True
    
    def dismiss(self, discovery_id: str, feedback: str | None = None) -> bool:
        """Dismiss a discovery as inaccurate."""
        if discovery_id not in self._discoveries:
            return False
        
        discovery = self._discoveries[discovery_id]
        discovery.status = "dismissed"
        discovery.user_feedback = feedback
        discovery.last_updated = datetime.now()
        
        self._update_discovery_status(discovery)
        
        logger.info(f"Discovery dismissed: {discovery.title}")
        return True
    
    def _update_discovery_status(self, discovery: Discovery) -> None:
        """Update discovery status in database."""
        conn = self.catalog.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE discoveries
            SET status = ?, user_feedback = ?, last_updated = ?
            WHERE id = ?
        """, (
            discovery.status,
            discovery.user_feedback,
            discovery.last_updated.isoformat(),
            discovery.id,
        ))
        
        conn.commit()
        conn.close()
    
    def get_active_discoveries(self) -> list[Discovery]:
        """Get all active discoveries."""
        return [
            d for d in self._discoveries.values()
            if d.status == "active"
        ]
    
    def get_discoveries_by_type(self, discovery_type: str) -> list[Discovery]:
        """Get discoveries of a specific type."""
        return [
            d for d in self._discoveries.values()
            if d.discovery_type == discovery_type and d.status != "dismissed"
        ]
    
    def get_high_confidence_discoveries(
        self, 
        min_confidence: float | None = None,
    ) -> list[Discovery]:
        """Get discoveries above confidence threshold."""
        threshold = min_confidence or self.min_confidence
        return sorted(
            [d for d in self._discoveries.values() 
             if d.confidence >= threshold and d.status != "dismissed"],
            key=lambda d: d.confidence,
            reverse=True,
        )
    
    def get_stats(self) -> dict[str, Any]:
        """Get discovery statistics."""
        by_type = {}
        by_status = {}
        
        for d in self._discoveries.values():
            by_type[d.discovery_type] = by_type.get(d.discovery_type, 0) + 1
            by_status[d.status] = by_status.get(d.status, 0) + 1
        
        return {
            "total": len(self._discoveries),
            "by_type": by_type,
            "by_status": by_status,
            "avg_confidence": (
                sum(d.confidence for d in self._discoveries.values()) / 
                len(self._discoveries)
            ) if self._discoveries else 0,
        }
