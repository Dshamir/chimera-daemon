"""Entity consolidation for CHIMERA.

Merges variant spellings/references of the same entity:
- "Gabriel", "gabriel", "Gabe" → PERSON:gabriel
- "Anthropic", "anthropic", "ANTHROPIC" → ORG:anthropic

Builds co-occurrence matrix for relationship detection.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from chimera.storage.catalog import CatalogDB
from chimera.utils.hashing import generate_id
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


# Common name variations/nicknames
NAME_ALIASES = {
    "gabriel": ["gabe", "gabi"],
    "daniel": ["dan", "danny"],
    "michael": ["mike", "mick"],
    "robert": ["rob", "bob", "bobby"],
    "william": ["will", "bill", "billy"],
    "richard": ["rick", "dick"],
    "christopher": ["chris"],
    "matthew": ["matt"],
    "anthony": ["tony"],
    "joseph": ["joe", "joey"],
    "benjamin": ["ben"],
    "alexander": ["alex"],
    "nicholas": ["nick"],
    "jonathan": ["jon"],
    "stephen": ["steve"],
    "elizabeth": ["liz", "beth", "lizzy"],
    "jennifer": ["jen", "jenny"],
    "katherine": ["kate", "kathy", "katie"],
    "margaret": ["maggie", "meg"],
    "patricia": ["pat", "patty"],
}

# Build reverse lookup
ALIAS_TO_CANONICAL = {}
for canonical, aliases in NAME_ALIASES.items():
    for alias in aliases:
        ALIAS_TO_CANONICAL[alias] = canonical


@dataclass
class ConsolidatedEntity:
    """A consolidated entity with all variants merged."""
    id: str
    entity_type: str
    canonical_value: str
    variants: set[str] = field(default_factory=set)
    occurrence_count: int = 0
    file_ids: set[str] = field(default_factory=set)
    contexts: list[str] = field(default_factory=list)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "canonical_value": self.canonical_value,
            "variants": list(self.variants),
            "occurrence_count": self.occurrence_count,
            "file_ids": list(self.file_ids),
            "contexts": self.contexts[:10],  # Keep only 10 sample contexts
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


@dataclass
class CoOccurrence:
    """Co-occurrence of two entities."""
    entity1_id: str
    entity2_id: str
    count: int = 0
    file_ids: set[str] = field(default_factory=set)
    strength: float = 0.0  # Calculated based on count and diversity


class EntityConsolidator:
    """Consolidates entities from multiple files."""
    
    def __init__(self, catalog: CatalogDB | None = None) -> None:
        self.catalog = catalog or CatalogDB()
        self._consolidated: dict[str, ConsolidatedEntity] = {}
        self._co_occurrences: dict[tuple[str, str], CoOccurrence] = {}
    
    def normalize(self, value: str, entity_type: str) -> str:
        """Normalize entity value for comparison."""
        # Basic normalization
        normalized = value.lower().strip()
        
        # Remove common prefixes
        for prefix in ["the ", "a ", "an "]:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
        
        # For persons, try alias resolution
        if entity_type == "PERSON":
            # Extract first name if it's a full name
            parts = normalized.split()
            if parts:
                first_name = parts[0]
                if first_name in ALIAS_TO_CANONICAL:
                    parts[0] = ALIAS_TO_CANONICAL[first_name]
                    normalized = " ".join(parts)
        
        # Remove special characters for comparison
        normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
        
        return normalized
    
    def _get_canonical_key(self, entity_type: str, normalized: str) -> str:
        """Get canonical key for entity lookup."""
        return f"{entity_type}:{normalized}"
    
    def consolidate_all(self) -> dict[str, ConsolidatedEntity]:
        """Consolidate all entities from the catalog."""
        logger.info("Starting entity consolidation...")
        
        conn = self.catalog.get_connection()
        cursor = conn.cursor()
        
        # Get all entities with file info
        cursor.execute("""
            SELECT e.id, e.file_id, e.entity_type, e.value, e.normalized, 
                   e.confidence, e.context, f.indexed_at
            FROM entities e
            JOIN files f ON e.file_id = f.id
            ORDER BY f.indexed_at
        """)
        
        entity_count = 0
        for row in cursor.fetchall():
            entity_id, file_id, entity_type, value, normalized, confidence, context, indexed_at = row
            
            # Use provided normalized or compute our own
            if not normalized:
                normalized = self.normalize(value, entity_type)
            
            canonical_key = self._get_canonical_key(entity_type, normalized)
            
            # Get or create consolidated entity
            if canonical_key not in self._consolidated:
                self._consolidated[canonical_key] = ConsolidatedEntity(
                    id=generate_id("cent", canonical_key),
                    entity_type=entity_type,
                    canonical_value=normalized,
                )
            
            entity = self._consolidated[canonical_key]
            entity.variants.add(value)
            entity.occurrence_count += 1
            entity.file_ids.add(file_id)
            
            if context and len(entity.contexts) < 10:
                entity.contexts.append(context)
            
            # Track timestamps
            if indexed_at:
                ts = datetime.fromisoformat(indexed_at)
                if entity.first_seen is None or ts < entity.first_seen:
                    entity.first_seen = ts
                if entity.last_seen is None or ts > entity.last_seen:
                    entity.last_seen = ts
            
            entity_count += 1
        
        conn.close()
        
        logger.info(f"Consolidated {entity_count} entities into {len(self._consolidated)} unique entities")
        
        # Store consolidated entities in global_entities table
        self._store_consolidated()
        
        return self._consolidated
    
    def _store_consolidated(self) -> None:
        """Store consolidated entities in the database."""
        conn = self.catalog.get_connection()
        cursor = conn.cursor()
        
        for entity in self._consolidated.values():
            cursor.execute("""
                INSERT OR REPLACE INTO global_entities
                (id, entity_type, value, normalized, occurrence_count, 
                 file_ids, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entity.id,
                entity.entity_type,
                ", ".join(entity.variants),
                entity.canonical_value,
                entity.occurrence_count,
                json.dumps(list(entity.file_ids)),
                entity.first_seen.isoformat() if entity.first_seen else None,
                entity.last_seen.isoformat() if entity.last_seen else None,
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Stored {len(self._consolidated)} consolidated entities")
    
    def build_co_occurrence_matrix(
        self,
        max_entities: int = 50000,
        max_pairs_per_file: int = 500,
        max_total_pairs: int = 1000000,
    ) -> dict[tuple[str, str], CoOccurrence]:
        """Build co-occurrence matrix for entities appearing in same files.

        Args:
            max_entities: Maximum entities to consider (for performance)
            max_pairs_per_file: Maximum entity pairs to consider per file
            max_total_pairs: Maximum total pairs to track
        """
        logger.info("Building co-occurrence matrix...")

        # Limit entities if too many (prioritize by occurrence count)
        entities_to_process = self._consolidated
        if len(self._consolidated) > max_entities:
            logger.warning(
                f"Limiting entities from {len(self._consolidated)} to {max_entities} "
                f"(sorted by occurrence count)"
            )
            sorted_entities = sorted(
                self._consolidated.items(),
                key=lambda x: x[1].occurrence_count,
                reverse=True
            )[:max_entities]
            entities_to_process = dict(sorted_entities)

        # Group entities by file
        file_entities: dict[str, list[str]] = defaultdict(list)
        for key, entity in entities_to_process.items():
            for file_id in entity.file_ids:
                file_entities[file_id].append(key)

        # Count co-occurrences with limits
        files_processed = 0
        total_files = len(file_entities)

        for file_id, entity_keys in file_entities.items():
            files_processed += 1
            if files_processed % 10000 == 0:
                logger.debug(
                    f"Co-occurrence progress: {files_processed}/{total_files} files, "
                    f"{len(self._co_occurrences)} pairs"
                )

            # Limit pairs per file to avoid explosion
            pairs_this_file = 0
            for i, key1 in enumerate(entity_keys):
                if pairs_this_file >= max_pairs_per_file:
                    break
                for key2 in entity_keys[i+1:]:
                    if pairs_this_file >= max_pairs_per_file:
                        break

                    # Sort to ensure consistent ordering
                    pair = tuple(sorted([key1, key2]))

                    if pair not in self._co_occurrences:
                        if len(self._co_occurrences) >= max_total_pairs:
                            logger.warning(
                                f"Reached max pairs limit ({max_total_pairs}), stopping"
                            )
                            break
                        self._co_occurrences[pair] = CoOccurrence(
                            entity1_id=entities_to_process[pair[0]].id,
                            entity2_id=entities_to_process[pair[1]].id,
                        )

                    self._co_occurrences[pair].count += 1
                    self._co_occurrences[pair].file_ids.add(file_id)
                    pairs_this_file += 1

            if len(self._co_occurrences) >= max_total_pairs:
                break

        # Calculate strength scores
        for pair, co_occ in self._co_occurrences.items():
            # Strength based on count and file diversity
            count_score = min(1.0, co_occ.count / 10)
            diversity_score = min(1.0, len(co_occ.file_ids) / 5)
            co_occ.strength = 0.6 * count_score + 0.4 * diversity_score

        logger.info(f"Built co-occurrence matrix with {len(self._co_occurrences)} pairs")

        return self._co_occurrences
    
    def get_related_entities(
        self, 
        entity_key: str, 
        min_strength: float = 0.3,
        limit: int = 20,
    ) -> list[tuple[str, float]]:
        """Get entities most related to a given entity."""
        related = []
        
        for pair, co_occ in self._co_occurrences.items():
            if co_occ.strength < min_strength:
                continue
            
            if pair[0] == entity_key:
                related.append((pair[1], co_occ.strength))
            elif pair[1] == entity_key:
                related.append((pair[0], co_occ.strength))
        
        # Sort by strength
        related.sort(key=lambda x: x[1], reverse=True)
        
        return related[:limit]
    
    def get_entity_stats(self) -> dict[str, Any]:
        """Get entity consolidation statistics."""
        type_counts = defaultdict(int)
        for entity in self._consolidated.values():
            type_counts[entity.entity_type] += 1
        
        return {
            "total_consolidated": len(self._consolidated),
            "by_type": dict(type_counts),
            "co_occurrence_pairs": len(self._co_occurrences),
            "high_strength_pairs": sum(
                1 for co_occ in self._co_occurrences.values() 
                if co_occ.strength >= 0.5
            ),
        }
