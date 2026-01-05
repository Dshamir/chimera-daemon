"""Discovery surfacing for unknown knowns."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from chimera.correlation.engine import Pattern


@dataclass
class Discovery:
    """A surfaced discovery (unknown known)."""
    id: str
    discovery_type: str
    title: str
    description: str
    confidence: float
    evidence: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    first_seen: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    status: str = "active"  # active, confirmed, dismissed
    user_feedback: str | None = None


class DiscoverySurfacer:
    """Surface high-confidence patterns as discoveries."""
    
    def __init__(self, min_confidence: float = 0.7) -> None:
        self.min_confidence = min_confidence
        self.discoveries: list[Discovery] = []
    
    def is_unknown_known(self, pattern: Pattern) -> bool:
        """Check if pattern qualifies as an 'unknown known'.
        
        Unknown knowns are:
        - High confidence patterns
        - NOT explicitly stated by user
        - Emerge from behavioral evidence
        """
        # High confidence check
        if pattern.confidence < self.min_confidence:
            return False
        
        # Evidence count check (need multiple sources)
        if len(pattern.sources) < 2:
            return False
        
        # TODO: Check if explicitly stated in user's documents
        # For now, assume all high-confidence multi-source patterns qualify
        
        return True
    
    def pattern_to_discovery(self, pattern: Pattern) -> Discovery:
        """Convert a pattern to a discovery."""
        return Discovery(
            id=f"disc_{pattern.pattern_type}_{pattern.id}",
            discovery_type=pattern.pattern_type,
            title=pattern.title,
            description=pattern.description,
            confidence=pattern.confidence,
            evidence=pattern.evidence,
            sources=pattern.sources,
            first_seen=pattern.first_seen,
            last_updated=pattern.last_updated,
        )
    
    async def surface_discoveries(self, patterns: list[Pattern]) -> list[Discovery]:
        """Surface discoveries from patterns."""
        discoveries = []
        
        for pattern in patterns:
            if self.is_unknown_known(pattern):
                discovery = self.pattern_to_discovery(pattern)
                discoveries.append(discovery)
        
        # Deduplicate
        discoveries = self._deduplicate(discoveries)
        
        self.discoveries = discoveries
        return discoveries
    
    def _deduplicate(self, discoveries: list[Discovery]) -> list[Discovery]:
        """Remove duplicate discoveries."""
        seen: set[str] = set()
        unique: list[Discovery] = []
        
        for d in discoveries:
            key = f"{d.discovery_type}:{d.title.lower()}"
            if key not in seen:
                seen.add(key)
                unique.append(d)
        
        return unique
    
    async def confirm(self, discovery_id: str, notes: str | None = None) -> bool:
        """Confirm a discovery."""
        for d in self.discoveries:
            if d.id == discovery_id:
                d.status = "confirmed"
                d.user_feedback = notes
                return True
        return False
    
    async def dismiss(self, discovery_id: str, reason: str | None = None) -> bool:
        """Dismiss a discovery."""
        for d in self.discoveries:
            if d.id == discovery_id:
                d.status = "dismissed"
                d.user_feedback = reason
                return True
        return False
