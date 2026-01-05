"""Entity extraction using spaCy.

Extracts named entities: PERSON, ORG, DATE, TECH, PROJECT, etc.
"""

from dataclasses import dataclass
from typing import Any

from chimera.utils.logging import get_logger

logger = get_logger(__name__)

# Custom entity patterns for tech domain
TECH_PATTERNS = [
    "Python", "JavaScript", "TypeScript", "React", "FastAPI", "Django",
    "PostgreSQL", "SQLite", "ChromaDB", "Docker", "Kubernetes",
    "AWS", "GCP", "Azure", "Linux", "Windows", "macOS",
    "Git", "GitHub", "API", "REST", "GraphQL", "OAuth",
    "TensorFlow", "PyTorch", "spaCy", "NLTK", "LLM", "GPT",
    "Claude", "Anthropic", "OpenAI", "Gemini",
]


@dataclass
class Entity:
    """An extracted entity."""
    text: str
    label: str  # PERSON, ORG, DATE, TECH, etc.
    start: int
    end: int
    confidence: float = 1.0
    context: str | None = None


class EntityExtractor:
    """Extract named entities from text."""
    
    def __init__(self, model_name: str = "en_core_web_sm") -> None:
        self.model_name = model_name
        self._nlp = None
    
    def _load_model(self) -> Any:
        """Lazy load spaCy model."""
        if self._nlp is None:
            try:
                import spacy
                
                logger.info(f"Loading spaCy model: {self.model_name}")
                try:
                    self._nlp = spacy.load(self.model_name)
                except OSError:
                    logger.warning(f"Model {self.model_name} not found. Downloading...")
                    spacy.cli.download(self.model_name)
                    self._nlp = spacy.load(self.model_name)
                
                logger.info("spaCy model loaded.")
            except ImportError:
                logger.error("spaCy not installed. Run: pip install spacy")
                raise
        
        return self._nlp
    
    def extract(self, text: str, include_context: bool = True) -> list[Entity]:
        """Extract entities from text."""
        if not text.strip():
            return []
        
        nlp = self._load_model()
        
        # Truncate very long texts
        if len(text) > 100000:
            text = text[:100000]
        
        doc = nlp(text)
        entities = []
        
        for ent in doc.ents:
            # Map spaCy labels to our labels
            label = self._map_label(ent.label_)
            
            # Get context (surrounding text)
            context = None
            if include_context:
                start = max(0, ent.start_char - 50)
                end = min(len(text), ent.end_char + 50)
                context = text[start:end]
            
            entities.append(Entity(
                text=ent.text,
                label=label,
                start=ent.start_char,
                end=ent.end_char,
                context=context,
            ))
        
        # Add tech entities not caught by spaCy
        tech_entities = self._extract_tech_entities(text)
        entities.extend(tech_entities)
        
        # Deduplicate
        entities = self._deduplicate(entities)
        
        return entities
    
    def _map_label(self, spacy_label: str) -> str:
        """Map spaCy labels to our entity types."""
        mapping = {
            "PERSON": "PERSON",
            "ORG": "ORG",
            "GPE": "LOCATION",
            "LOC": "LOCATION",
            "DATE": "DATE",
            "TIME": "TIME",
            "MONEY": "MONEY",
            "PRODUCT": "PRODUCT",
            "WORK_OF_ART": "PROJECT",
            "LAW": "LEGAL",
            "EVENT": "EVENT",
        }
        return mapping.get(spacy_label, spacy_label)
    
    def _extract_tech_entities(self, text: str) -> list[Entity]:
        """Extract tech-specific entities using patterns."""
        entities = []
        text_lower = text.lower()
        
        for tech in TECH_PATTERNS:
            tech_lower = tech.lower()
            start = 0
            
            while True:
                idx = text_lower.find(tech_lower, start)
                if idx == -1:
                    break
                
                # Check word boundary
                if (idx == 0 or not text[idx-1].isalnum()) and \
                   (idx + len(tech) >= len(text) or not text[idx + len(tech)].isalnum()):
                    
                    entities.append(Entity(
                        text=text[idx:idx + len(tech)],
                        label="TECH",
                        start=idx,
                        end=idx + len(tech),
                        confidence=0.9,
                    ))
                
                start = idx + 1
        
        return entities
    
    def _deduplicate(self, entities: list[Entity]) -> list[Entity]:
        """Remove duplicate entities."""
        seen = set()
        unique = []
        
        for ent in entities:
            key = (ent.text.lower(), ent.label, ent.start)
            if key not in seen:
                seen.add(key)
                unique.append(ent)
        
        return unique
    
    def normalize(self, entity: Entity) -> str:
        """Normalize entity text for comparison."""
        text = entity.text.lower().strip()
        
        # Remove common prefixes/suffixes
        for prefix in ["the ", "a ", "an "]:
            if text.startswith(prefix):
                text = text[len(prefix):]
        
        return text


# Global instance
_extractor: EntityExtractor | None = None


def get_entity_extractor() -> EntityExtractor:
    """Get the global entity extractor."""
    global _extractor
    if _extractor is None:
        _extractor = EntityExtractor()
    return _extractor


def extract_entities(text: str) -> list[Entity]:
    """Quick helper to extract entities from text."""
    return get_entity_extractor().extract(text)
