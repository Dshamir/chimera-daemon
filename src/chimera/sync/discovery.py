"""Cross-Machine Discovery Engine.

Finds patterns and insights that span multiple excavated machines.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CrossMachinePattern:
    """A pattern detected across multiple machines."""
    
    id: str
    name: str
    description: str
    machines: List[str]
    entities: List[str]
    file_count: int
    confidence: float
    pattern_type: str  # "topic", "project", "collaboration", "temporal"
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "machines": self.machines,
            "entities": self.entities,
            "file_count": self.file_count,
            "confidence": self.confidence,
            "pattern_type": self.pattern_type,
            "metadata": self.metadata,
        }


@dataclass
class CrossMachineInsight:
    """An insight derived from cross-machine analysis."""
    
    id: str
    title: str
    description: str
    insight_type: str  # "expertise", "collaboration", "timeline", "gap"
    confidence: float
    supporting_patterns: List[str]
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "insight_type": self.insight_type,
            "confidence": self.confidence,
            "supporting_patterns": self.supporting_patterns,
            "recommendations": self.recommendations,
        }


class CrossMachineDiscovery:
    """Discovers patterns across multiple excavated machines."""
    
    def __init__(self):
        self.patterns: List[CrossMachinePattern] = []
        self.insights: List[CrossMachineInsight] = []
        
        # Index structures
        self._entity_machines: Dict[str, Set[str]] = defaultdict(set)
        self._machine_entities: Dict[str, Set[str]] = defaultdict(set)
        self._entity_files: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    
    async def analyze(self) -> Tuple[List[CrossMachinePattern], List[CrossMachineInsight]]:
        """Run full cross-machine analysis."""
        from chimera.storage.catalog import CatalogDB
        
        catalog = CatalogDB()
        
        # Build indices from catalog
        await self._build_indices(catalog)
        
        # Find patterns
        self.patterns = []
        self.patterns.extend(await self._find_shared_topics())
        self.patterns.extend(await self._find_collaboration_patterns())
        self.patterns.extend(await self._find_expertise_clusters())
        
        # Generate insights
        self.insights = await self._generate_insights()
        
        return self.patterns, self.insights
    
    async def _build_indices(self, catalog):
        """Build index structures for analysis."""
        logger.info("Building cross-machine indices...")
        
        # Get all entities with their source machines
        try:
            conn = catalog._get_connection()
            cursor = conn.execute("""
                SELECT 
                    e.normalized,
                    e.value,
                    e.entity_type,
                    f.path,
                    f.metadata
                FROM entities e
                JOIN files f ON e.file_id = f.id
            """)
            
            for row in cursor:
                normalized, value, entity_type, file_path, file_metadata = row
                
                # Extract machine from metadata or path
                machine = "unknown"
                if file_metadata:
                    import json
                    try:
                        meta = json.loads(file_metadata) if isinstance(file_metadata, str) else file_metadata
                        machine = meta.get("source_machine", "local")
                    except:
                        pass
                
                # Extract from path tag if present
                if file_path and file_path.startswith("["):
                    machine = file_path.split("]")[0][1:]
                
                # Update indices
                self._entity_machines[normalized].add(machine)
                self._machine_entities[machine].add(normalized)
                self._entity_files[normalized][machine] += 1
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Error building indices: {e}")
    
    async def _find_shared_topics(self) -> List[CrossMachinePattern]:
        """Find topics that appear across multiple machines."""
        patterns = []
        
        for entity, machines in self._entity_machines.items():
            if len(machines) > 1:
                # Entity appears on multiple machines
                total_files = sum(self._entity_files[entity].values())
                
                # Higher confidence if appears on more machines and more files
                confidence = min(1.0, (len(machines) / 3) * (total_files / 10))
                
                if confidence > 0.3:  # Threshold
                    pattern = CrossMachinePattern(
                        id=f"topic_{hash(entity) % 10000:04d}",
                        name=f"Shared Topic: {entity[:50]}",
                        description=f"'{entity}' appears across {len(machines)} machines in {total_files} files",
                        machines=list(machines),
                        entities=[entity],
                        file_count=total_files,
                        confidence=confidence,
                        pattern_type="topic",
                        metadata={
                            "files_per_machine": dict(self._entity_files[entity]),
                        },
                    )
                    patterns.append(pattern)
        
        # Sort by confidence
        patterns.sort(key=lambda x: -x.confidence)
        return patterns[:50]  # Top 50
    
    async def _find_collaboration_patterns(self) -> List[CrossMachinePattern]:
        """Find patterns suggesting collaboration between machines/users."""
        patterns = []
        
        # Find entity pairs that co-occur across machines
        machines = list(self._machine_entities.keys())
        
        for i, m1 in enumerate(machines):
            for m2 in machines[i+1:]:
                # Find shared entities
                shared = self._machine_entities[m1] & self._machine_entities[m2]
                
                if len(shared) >= 5:  # Significant overlap
                    # Check for project-like patterns (related entities)
                    confidence = min(1.0, len(shared) / 20)
                    
                    pattern = CrossMachinePattern(
                        id=f"collab_{hash(f'{m1}_{m2}') % 10000:04d}",
                        name=f"Collaboration: {m1} ↔ {m2}",
                        description=f"{len(shared)} shared entities between {m1} and {m2}",
                        machines=[m1, m2],
                        entities=list(shared)[:10],  # Top 10
                        file_count=sum(
                            self._entity_files[e][m1] + self._entity_files[e][m2]
                            for e in shared
                        ),
                        confidence=confidence,
                        pattern_type="collaboration",
                        metadata={
                            "shared_entity_count": len(shared),
                            "unique_to_m1": len(self._machine_entities[m1] - shared),
                            "unique_to_m2": len(self._machine_entities[m2] - shared),
                        },
                    )
                    patterns.append(pattern)
        
        return patterns
    
    async def _find_expertise_clusters(self) -> List[CrossMachinePattern]:
        """Find expertise clusters per machine."""
        patterns = []
        
        # Entities unique to one machine suggest expertise
        for machine, entities in self._machine_entities.items():
            # Find entities unique to this machine
            unique_entities = set()
            for entity in entities:
                if len(self._entity_machines[entity]) == 1:
                    unique_entities.add(entity)
            
            if len(unique_entities) >= 10:
                # Group by apparent topic (simple heuristic)
                total_files = sum(
                    self._entity_files[e][machine]
                    for e in unique_entities
                )
                
                confidence = min(1.0, len(unique_entities) / 50)
                
                pattern = CrossMachinePattern(
                    id=f"expertise_{hash(machine) % 10000:04d}",
                    name=f"Expertise Cluster: {machine}",
                    description=f"{len(unique_entities)} unique entities on {machine}",
                    machines=[machine],
                    entities=list(unique_entities)[:20],
                    file_count=total_files,
                    confidence=confidence,
                    pattern_type="expertise",
                    metadata={
                        "unique_entity_count": len(unique_entities),
                        "total_entities": len(entities),
                        "uniqueness_ratio": len(unique_entities) / len(entities) if entities else 0,
                    },
                )
                patterns.append(pattern)
        
        return patterns
    
    async def _generate_insights(self) -> List[CrossMachineInsight]:
        """Generate high-level insights from patterns."""
        insights = []
        
        # Insight: Overall knowledge distribution
        machines = list(self._machine_entities.keys())
        if len(machines) > 1:
            total_entities = len(set().union(*self._machine_entities.values()))
            
            # Find most central machine (most shared entities)
            centrality = {}
            for m in machines:
                shared_count = sum(
                    1 for e in self._machine_entities[m]
                    if len(self._entity_machines[e]) > 1
                )
                centrality[m] = shared_count
            
            most_central = max(centrality.items(), key=lambda x: x[1])
            
            insights.append(CrossMachineInsight(
                id="insight_distribution",
                title="Knowledge Distribution",
                description=f"Analyzed {total_entities} unique entities across {len(machines)} machines. "
                           f"{most_central[0]} is the most central hub with {most_central[1]} shared entities.",
                insight_type="expertise",
                confidence=0.8,
                supporting_patterns=[p.id for p in self.patterns[:3]],
                recommendations=[
                    f"Consider {most_central[0]} as the primary knowledge repository",
                    "Sync frequently-accessed shared entities to all machines",
                ],
            ))
        
        # Insight: Collaboration opportunities
        collab_patterns = [p for p in self.patterns if p.pattern_type == "collaboration"]
        if collab_patterns:
            strongest = collab_patterns[0]
            insights.append(CrossMachineInsight(
                id="insight_collaboration",
                title="Collaboration Detected",
                description=f"Strong collaboration pattern between {' and '.join(strongest.machines)} "
                           f"with {strongest.metadata.get('shared_entity_count', 0)} shared topics.",
                insight_type="collaboration",
                confidence=strongest.confidence,
                supporting_patterns=[strongest.id],
                recommendations=[
                    "Create shared workspace for collaborative topics",
                    "Set up real-time sync for shared projects",
                ],
            ))
        
        # Insight: Expertise silos
        expertise_patterns = [p for p in self.patterns if p.pattern_type == "expertise"]
        if expertise_patterns:
            high_uniqueness = [
                p for p in expertise_patterns
                if p.metadata.get("uniqueness_ratio", 0) > 0.5
            ]
            
            if high_uniqueness:
                insights.append(CrossMachineInsight(
                    id="insight_silos",
                    title="Knowledge Silos Detected",
                    description=f"{len(high_uniqueness)} machines have highly unique knowledge "
                               f"that isn't shared with others.",
                    insight_type="gap",
                    confidence=0.7,
                    supporting_patterns=[p.id for p in high_uniqueness[:3]],
                    recommendations=[
                        "Review unique expertise areas for potential knowledge sharing",
                        "Consider cross-training or documentation for siloed topics",
                    ],
                ))
        
        return insights
    
    def get_summary(self) -> dict:
        """Get summary of cross-machine analysis."""
        return {
            "machines_analyzed": len(self._machine_entities),
            "total_entities": len(self._entity_machines),
            "patterns_found": len(self.patterns),
            "insights_generated": len(self.insights),
            "patterns_by_type": {
                ptype: len([p for p in self.patterns if p.pattern_type == ptype])
                for ptype in ["topic", "collaboration", "expertise"]
            },
        }
