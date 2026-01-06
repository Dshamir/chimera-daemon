"""Pattern detection for CHIMERA.

Detects:
- Expertise patterns (domain vocabulary density)
- Relationship patterns (PERSON + PROJECT co-occurrence)
- Workflow patterns (document naming, time patterns)
- Heuristic patterns (recurring approaches)
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from math import log10
from typing import Any, Literal

from chimera.correlation.entities import EntityConsolidator, ConsolidatedEntity
from chimera.storage.catalog import CatalogDB
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


# Domain vocabulary for expertise detection
DOMAIN_VOCABULARY = {
    "machine_learning": [
        "neural network", "deep learning", "transformer", "attention",
        "embedding", "gradient", "backpropagation", "loss function",
        "training", "inference", "model", "weights", "bias",
        "overfitting", "regularization", "dropout", "batch normalization",
    ],
    "web_development": [
        "react", "vue", "angular", "javascript", "typescript",
        "html", "css", "dom", "api", "rest", "graphql",
        "frontend", "backend", "fullstack", "responsive",
    ],
    "devops": [
        "docker", "kubernetes", "ci/cd", "pipeline", "deployment",
        "container", "orchestration", "helm", "terraform",
        "aws", "gcp", "azure", "cloud", "infrastructure",
    ],
    "data_engineering": [
        "etl", "pipeline", "data lake", "warehouse", "spark",
        "kafka", "airflow", "dbt", "sql", "nosql",
        "schema", "partition", "batch", "streaming",
    ],
    "medical_devices": [
        "fda", "510k", "regulatory", "clinical", "validation",
        "verification", "ivd", "diagnostic", "qms", "iso 13485",
        "medical device", "patient", "healthcare", "hipaa",
    ],
    "control_systems": [
        "pid", "controller", "feedback", "setpoint", "gain",
        "proportional", "integral", "derivative", "tuning",
        "stability", "transfer function", "bode", "nyquist",
    ],
}


@dataclass
class Pattern:
    """A detected pattern."""
    id: str
    pattern_type: str  # expertise, relationship, workflow, heuristic
    title: str
    description: str
    confidence: float
    evidence: list[dict[str, Any]] = field(default_factory=list)
    source_files: set[str] = field(default_factory=set)
    source_entities: set[str] = field(default_factory=set)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "pattern_type": self.pattern_type,
            "title": self.title,
            "description": self.description,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source_files": list(self.source_files),
            "source_entities": list(self.source_entities),
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class PatternDetector:
    """Detects patterns from consolidated entities and content."""
    
    def __init__(
        self,
        catalog: CatalogDB | None = None,
        consolidator: EntityConsolidator | None = None,
    ) -> None:
        self.catalog = catalog or CatalogDB()
        self.consolidator = consolidator or EntityConsolidator(self.catalog)
        self._patterns: dict[str, Pattern] = {}
    
    def detect_all(self) -> dict[str, Pattern]:
        """Run all pattern detection."""
        logger.info("Starting pattern detection...")
        
        # Ensure entities are consolidated
        if not self.consolidator._consolidated:
            self.consolidator.consolidate_all()
            self.consolidator.build_co_occurrence_matrix()
        
        # Detect patterns
        self._detect_expertise_patterns()
        self._detect_relationship_patterns()
        self._detect_workflow_patterns()
        self._detect_tech_stack_patterns()
        
        logger.info(f"Detected {len(self._patterns)} patterns")
        
        return self._patterns
    
    def _detect_expertise_patterns(self) -> None:
        """Detect expertise based on domain vocabulary density."""
        logger.info("Detecting expertise patterns...")
        
        conn = self.catalog.get_connection()
        cursor = conn.cursor()
        
        # Get all indexed content
        cursor.execute("""
            SELECT c.content, c.file_id
            FROM chunks c
            JOIN files f ON c.file_id = f.id
            WHERE f.status = 'indexed'
        """)
        
        # Count domain term occurrences
        domain_scores: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "file_ids": set(),
            "terms_found": set(),
        })
        
        total_chunks = 0
        for content, file_id in cursor.fetchall():
            content_lower = content.lower()
            total_chunks += 1
            
            for domain, terms in DOMAIN_VOCABULARY.items():
                for term in terms:
                    if term in content_lower:
                        domain_scores[domain]["count"] += 1
                        domain_scores[domain]["file_ids"].add(file_id)
                        domain_scores[domain]["terms_found"].add(term)
        
        conn.close()
        
        # Create expertise patterns
        for domain, data in domain_scores.items():
            if data["count"] < 5:  # Minimum threshold
                continue
            
            # Calculate confidence based on count and diversity
            count_score = min(1.0, log10(data["count"] + 1) / 2)
            diversity_score = min(1.0, len(data["file_ids"]) / 10)
            term_coverage = len(data["terms_found"]) / len(DOMAIN_VOCABULARY[domain])
            
            confidence = 0.4 * count_score + 0.3 * diversity_score + 0.3 * term_coverage
            
            if confidence >= 0.3:  # Lower threshold for detection
                pattern_id = f"exp_{domain}"
                self._patterns[pattern_id] = Pattern(
                    id=pattern_id,
                    pattern_type="expertise",
                    title=f"Expertise: {domain.replace('_', ' ').title()}",
                    description=f"Strong expertise in {domain.replace('_', ' ')} detected across {len(data['file_ids'])} files",
                    confidence=confidence,
                    evidence=[{
                        "term_count": data["count"],
                        "file_count": len(data["file_ids"]),
                        "terms": list(data["terms_found"])[:10],
                    }],
                    source_files=data["file_ids"],
                )
    
    def _detect_relationship_patterns(self) -> None:
        """Detect relationships between persons and projects/orgs."""
        logger.info("Detecting relationship patterns...")
        
        co_occurrences = self.consolidator._co_occurrences
        consolidated = self.consolidator._consolidated
        
        for pair, co_occ in co_occurrences.items():
            if co_occ.strength < 0.4:
                continue
            
            entity1 = consolidated.get(pair[0])
            entity2 = consolidated.get(pair[1])
            
            if not entity1 or not entity2:
                continue
            
            # Look for PERSON + ORG/PROJECT relationships
            relationship_type = None
            person = None
            other = None
            
            if entity1.entity_type == "PERSON" and entity2.entity_type in ("ORG", "PROJECT"):
                person = entity1
                other = entity2
                relationship_type = "works_with" if entity2.entity_type == "ORG" else "works_on"
            elif entity2.entity_type == "PERSON" and entity1.entity_type in ("ORG", "PROJECT"):
                person = entity2
                other = entity1
                relationship_type = "works_with" if entity1.entity_type == "ORG" else "works_on"
            
            if relationship_type:
                pattern_id = f"rel_{person.id}_{other.id}"
                self._patterns[pattern_id] = Pattern(
                    id=pattern_id,
                    pattern_type="relationship",
                    title=f"{person.canonical_value.title()} {relationship_type.replace('_', ' ')} {other.canonical_value.title()}",
                    description=f"Strong association detected between {person.canonical_value} and {other.canonical_value}",
                    confidence=co_occ.strength,
                    evidence=[{
                        "co_occurrence_count": co_occ.count,
                        "shared_files": len(co_occ.file_ids),
                    }],
                    source_files=co_occ.file_ids,
                    source_entities={person.id, other.id},
                )
    
    def _detect_workflow_patterns(self) -> None:
        """Detect workflow patterns from file naming and timing."""
        logger.info("Detecting workflow patterns...")
        
        conn = self.catalog.get_connection()
        cursor = conn.cursor()

        # Analyze file naming patterns
        cursor.execute("""
            SELECT id, filename, extension, created_at, path
            FROM files
            WHERE status = 'indexed'
        """)

        naming_patterns: dict[str, dict] = defaultdict(lambda: {"count": 0, "examples": [], "file_ids": set()})

        for file_id, filename, extension, created_at, path in cursor.fetchall():
            # Check for common naming patterns
            patterns_found = []

            # Date in filename
            if re.search(r'\d{4}[-_]?\d{2}[-_]?\d{2}', filename):
                patterns_found.append("date_prefix")

            # Version numbers
            if re.search(r'v\d+|_v\d+|version', filename.lower()):
                patterns_found.append("versioned")

            # Draft/final indicators
            if re.search(r'draft|final|wip', filename.lower()):
                patterns_found.append("status_suffix")

            # Project prefixes
            if re.search(r'^[A-Z]{2,5}[-_]', filename):
                patterns_found.append("project_prefix")

            for pattern in patterns_found:
                naming_patterns[pattern]["count"] += 1
                naming_patterns[pattern]["file_ids"].add(file_id)
                if len(naming_patterns[pattern]["examples"]) < 5:
                    naming_patterns[pattern]["examples"].append(filename)

        conn.close()

        # Create workflow patterns
        for pattern_name, data in naming_patterns.items():
            if data["count"] < 3:
                continue

            confidence = min(1.0, data["count"] / 20)

            if confidence >= 0.3:
                pattern_id = f"wf_{pattern_name}"
                self._patterns[pattern_id] = Pattern(
                    id=pattern_id,
                    pattern_type="workflow",
                    title=f"Workflow: {pattern_name.replace('_', ' ').title()} Files",
                    description=f"Consistent use of {pattern_name.replace('_', ' ')} naming convention",
                    confidence=confidence,
                    evidence=[{
                        "file_count": data["count"],
                        "examples": data["examples"],
                    }],
                    source_files=data["file_ids"],
                )
    
    def _detect_tech_stack_patterns(self) -> None:
        """Detect technology stack patterns from TECH entities."""
        logger.info("Detecting tech stack patterns...")
        
        consolidated = self.consolidator._consolidated
        
        # Group tech entities by category
        tech_categories: dict[str, list[ConsolidatedEntity]] = defaultdict(list)
        
        tech_categories_map = {
            "python": "languages", "javascript": "languages", "typescript": "languages",
            "react": "frameworks", "vue": "frameworks", "angular": "frameworks",
            "fastapi": "frameworks", "django": "frameworks", "flask": "frameworks",
            "docker": "infrastructure", "kubernetes": "infrastructure",
            "aws": "cloud", "gcp": "cloud", "azure": "cloud",
            "postgresql": "databases", "sqlite": "databases", "mongodb": "databases",
            "git": "tools", "github": "tools",
        }
        
        for key, entity in consolidated.items():
            if entity.entity_type != "TECH":
                continue
            
            category = tech_categories_map.get(entity.canonical_value, "other")
            tech_categories[category].append(entity)
        
        # Create tech stack pattern
        if tech_categories:
            stack_evidence = {}
            total_files = set()
            
            for category, entities in tech_categories.items():
                stack_evidence[category] = [
                    {"name": e.canonical_value, "occurrences": e.occurrence_count}
                    for e in sorted(entities, key=lambda x: x.occurrence_count, reverse=True)[:5]
                ]
                for e in entities:
                    total_files.update(e.file_ids)
            
            confidence = min(1.0, len(total_files) / 20)
            
            if confidence >= 0.3 and len(tech_categories) >= 2:
                self._patterns["tech_stack"] = Pattern(
                    id="tech_stack",
                    pattern_type="heuristic",
                    title="Technology Stack Profile",
                    description=f"Consistent technology stack across {len(total_files)} files",
                    confidence=confidence,
                    evidence=[stack_evidence],
                    source_files=total_files,
                )
    
    def get_patterns_by_type(self, pattern_type: str) -> list[Pattern]:
        """Get patterns of a specific type."""
        return [
            p for p in self._patterns.values() 
            if p.pattern_type == pattern_type
        ]
    
    def get_high_confidence_patterns(self, min_confidence: float = 0.7) -> list[Pattern]:
        """Get patterns above confidence threshold."""
        return [
            p for p in self._patterns.values() 
            if p.confidence >= min_confidence
        ]
