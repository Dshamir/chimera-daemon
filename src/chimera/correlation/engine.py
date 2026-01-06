"""Correlation Engine - main orchestrator for CHIMERA intelligence.

Coordinates:
1. Entity consolidation
2. Co-occurrence analysis
3. Pattern detection
4. Discovery surfacing

Runs periodically to update discoveries based on new content.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from chimera.correlation.discovery import Discovery, DiscoverySurfacer
from chimera.correlation.entities import ConsolidatedEntity, EntityConsolidator
from chimera.correlation.patterns import Pattern, PatternDetector
from chimera.storage.catalog import CatalogDB
from chimera.utils.hashing import generate_id
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CorrelationResult:
    """Result of correlation run."""
    success: bool = True
    error: str | None = None
    
    # Stats
    entities_consolidated: int = 0
    co_occurrence_pairs: int = 0
    patterns_detected: int = 0
    discoveries_surfaced: int = 0
    
    # Timing
    consolidation_time: float = 0
    pattern_time: float = 0
    discovery_time: float = 0
    total_time: float = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "error": self.error,
            "stats": {
                "entities_consolidated": self.entities_consolidated,
                "co_occurrence_pairs": self.co_occurrence_pairs,
                "patterns_detected": self.patterns_detected,
                "discoveries_surfaced": self.discoveries_surfaced,
            },
            "timing": {
                "consolidation_time": self.consolidation_time,
                "pattern_time": self.pattern_time,
                "discovery_time": self.discovery_time,
                "total_time": self.total_time,
            },
        }


class CorrelationEngine:
    """Main correlation engine for CHIMERA."""
    
    def __init__(
        self,
        catalog: CatalogDB | None = None,
        min_discovery_confidence: float = 0.7,
        min_discovery_sources: int = 2,
    ) -> None:
        self.catalog = catalog or CatalogDB()
        self.min_discovery_confidence = min_discovery_confidence
        self.min_discovery_sources = min_discovery_sources
        
        # Components
        self.consolidator = EntityConsolidator(self.catalog)
        self.pattern_detector = PatternDetector(self.catalog, self.consolidator)
        self.discovery_surfacer = DiscoverySurfacer(
            self.catalog,
            self.pattern_detector,
            min_confidence=min_discovery_confidence,
            min_sources=min_discovery_sources,
        )
        
        # Last run state
        self._last_run: datetime | None = None
    
    async def run_correlation(self) -> CorrelationResult:
        """Run full correlation pipeline.

        Heavy CPU-intensive work runs in a thread pool executor to avoid
        blocking the event loop, keeping health checks responsive.
        """
        import asyncio
        import time
        from concurrent.futures import ThreadPoolExecutor

        start_time = time.time()
        result = CorrelationResult()
        loop = asyncio.get_running_loop()

        try:
            logger.info("Starting correlation analysis...")

            # Run CPU-intensive work in thread pool to avoid blocking event loop
            with ThreadPoolExecutor(max_workers=1) as executor:
                # Step 1: Entity consolidation (in thread)
                consolidation_start = time.time()
                entities = await loop.run_in_executor(
                    executor, self.consolidator.consolidate_all
                )
                co_occurrences = await loop.run_in_executor(
                    executor, self.consolidator.build_co_occurrence_matrix
                )
                result.consolidation_time = time.time() - consolidation_start
                result.entities_consolidated = len(entities)
                result.co_occurrence_pairs = len(co_occurrences)

                logger.info(
                    f"Consolidated {result.entities_consolidated} entities, "
                    f"{result.co_occurrence_pairs} co-occurrence pairs"
                )

                # Step 2: Pattern detection (in thread)
                pattern_start = time.time()
                patterns = await loop.run_in_executor(
                    executor, self.pattern_detector.detect_all
                )
                result.pattern_time = time.time() - pattern_start
                result.patterns_detected = len(patterns)

                logger.info(f"Detected {result.patterns_detected} patterns")

                # Step 3: Discovery surfacing (in thread)
                discovery_start = time.time()
                discoveries = await loop.run_in_executor(
                    executor, self.discovery_surfacer.surface_all
                )
                result.discovery_time = time.time() - discovery_start
                result.discoveries_surfaced = len(discoveries)

                logger.info(f"Surfaced {result.discoveries_surfaced} discoveries")

            # Log audit (quick operation, fine on main thread)
            self._log_correlation_run(result)

            self._last_run = datetime.now()
            result.total_time = time.time() - start_time

            logger.info(
                f"Correlation complete in {result.total_time:.2f}s. "
                f"Discoveries: {result.discoveries_surfaced}"
            )

            return result

        except Exception as e:
            logger.error(f"Correlation failed: {e}")
            result.success = False
            result.error = str(e)
            result.total_time = time.time() - start_time
            return result
    
    def _log_correlation_run(self, result: CorrelationResult) -> None:
        """Log correlation run to audit log."""
        self.catalog.log_audit(
            action="correlation_run",
            entity_type="correlation",
            entity_id=f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            details=json.dumps(result.to_dict()),
        )
    
    # ========== Query Methods ==========
    
    def get_consolidated_entities(
        self,
        entity_type: str | None = None,
        min_occurrences: int = 1,
        limit: int = 100,
    ) -> list[ConsolidatedEntity]:
        """Get consolidated entities with optional filtering."""
        entities = list(self.consolidator._consolidated.values())
        
        if entity_type:
            entities = [e for e in entities if e.entity_type == entity_type]
        
        entities = [e for e in entities if e.occurrence_count >= min_occurrences]
        
        # Sort by occurrence count
        entities.sort(key=lambda e: e.occurrence_count, reverse=True)
        
        return entities[:limit]
    
    def get_entity_relationships(
        self,
        entity_key: str,
        min_strength: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Get relationships for an entity."""
        related = self.consolidator.get_related_entities(entity_key, min_strength)
        
        results = []
        for related_key, strength in related:
            related_entity = self.consolidator._consolidated.get(related_key)
            if related_entity:
                results.append({
                    "entity_type": related_entity.entity_type,
                    "value": related_entity.canonical_value,
                    "strength": strength,
                    "occurrences": related_entity.occurrence_count,
                })
        
        return results
    
    def get_patterns(
        self,
        pattern_type: str | None = None,
        min_confidence: float = 0.0,
    ) -> list[Pattern]:
        """Get detected patterns."""
        patterns = list(self.pattern_detector._patterns.values())
        
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        
        patterns = [p for p in patterns if p.confidence >= min_confidence]
        
        # Sort by confidence
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        
        return patterns
    
    def get_discoveries(
        self,
        discovery_type: str | None = None,
        status: str | None = None,
        min_confidence: float | None = None,
    ) -> list[Discovery]:
        """Get surfaced discoveries."""
        discoveries = list(self.discovery_surfacer._discoveries.values())
        
        if discovery_type:
            discoveries = [d for d in discoveries if d.discovery_type == discovery_type]
        
        if status:
            discoveries = [d for d in discoveries if d.status == status]
        elif status is None:
            # Default: exclude dismissed
            discoveries = [d for d in discoveries if d.status != "dismissed"]
        
        if min_confidence is not None:
            discoveries = [d for d in discoveries if d.confidence >= min_confidence]
        
        # Sort by confidence
        discoveries.sort(key=lambda d: d.confidence, reverse=True)
        
        return discoveries
    
    def confirm_discovery(self, discovery_id: str, feedback: str | None = None) -> bool:
        """Confirm a discovery as accurate."""
        return self.discovery_surfacer.confirm(discovery_id, feedback)
    
    def dismiss_discovery(self, discovery_id: str, feedback: str | None = None) -> bool:
        """Dismiss a discovery as inaccurate."""
        return self.discovery_surfacer.dismiss(discovery_id, feedback)
    
    def get_stats(self) -> dict[str, Any]:
        """Get correlation engine statistics."""
        entity_stats = self.consolidator.get_entity_stats()
        discovery_stats = self.discovery_surfacer.get_stats()
        
        return {
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "entities": entity_stats,
            "patterns": {
                "total": len(self.pattern_detector._patterns),
                "by_type": {
                    ptype: len([p for p in self.pattern_detector._patterns.values() if p.pattern_type == ptype])
                    for ptype in ["expertise", "relationship", "workflow", "heuristic"]
                },
            },
            "discoveries": discovery_stats,
        }
    
    def export_discoveries_as_graph_nodes(self) -> list[dict[str, Any]]:
        """Export discoveries as SIF pointer graph nodes."""
        nodes = []
        
        for discovery in self.get_discoveries(status="active"):
            node = {
                "id": discovery.id,
                "type": f"discovery:{discovery.discovery_type}",
                "label": discovery.title,
                "properties": {
                    "description": discovery.description,
                    "confidence": discovery.confidence,
                    "evidence_count": len(discovery.evidence),
                    "source_count": len(discovery.sources),
                    "first_seen": discovery.first_seen.isoformat(),
                    "status": discovery.status,
                },
                "metadata": {
                    "source": "chimera",
                    "generated_at": datetime.now().isoformat(),
                },
            }
            nodes.append(node)
        
        return nodes


# Global engine instance
_engine: CorrelationEngine | None = None


def get_correlation_engine() -> CorrelationEngine:
    """Get the global correlation engine."""
    global _engine
    if _engine is None:
        _engine = CorrelationEngine()
    return _engine
