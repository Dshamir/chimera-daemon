"""Claude integration for CHIMERA.

Provides context building for Claude conversations.
"""

from dataclasses import dataclass, field
from typing import Any

from chimera.correlation.engine import CorrelationEngine, get_correlation_engine
from chimera.storage.catalog import CatalogDB
from chimera.storage.vectors import VectorDB
from chimera.extractors.embeddings import get_embedding_generator
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ContextChunk:
    """A context chunk for Claude."""
    content: str
    source: str
    similarity: float
    chunk_type: str


@dataclass
class ClaudeContext:
    """Context prepared for Claude."""
    query: str
    chunks: list[ContextChunk] = field(default_factory=list)
    discoveries: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    
    def to_xml(self) -> str:
        """Convert to XML format for Claude."""
        xml = f"""<chimera_context>
<query>{self.query}</query>

<relevant_content>
"""
        for i, chunk in enumerate(self.chunks, 1):
            xml += f"""<chunk index="{i}" similarity="{chunk.similarity:.2f}" source="{chunk.source}" type="{chunk.chunk_type}">
{chunk.content}
</chunk>

"""
        xml += "</relevant_content>\n"
        
        if self.discoveries:
            xml += "\n<discoveries>\n"
            for d in self.discoveries:
                xml += f"""<discovery type="{d.get('discovery_type')}" confidence="{d.get('confidence', 0):.2f}">
{d.get('title')}: {d.get('description', '')}
</discovery>

"""
            xml += "</discoveries>\n"
        
        if self.entities:
            xml += "\n<key_entities>\n"
            for e in self.entities:
                xml += f"  <entity type=\"{e.get('entity_type')}\">{e.get('canonical_value')}</entity>\n"
            xml += "</key_entities>\n"
        
        xml += "</chimera_context>"
        return xml
    
    def to_markdown(self) -> str:
        """Convert to Markdown format."""
        md = f"## CHIMERA Context: {self.query}\n\n"
        
        md += "### Relevant Content\n\n"
        for i, chunk in enumerate(self.chunks, 1):
            md += f"**[{i}]** _{chunk.source}_ (similarity: {chunk.similarity:.2f})\n\n"
            md += f"> {chunk.content[:500]}...\n\n" if len(chunk.content) > 500 else f"> {chunk.content}\n\n"
        
        if self.discoveries:
            md += "### Discoveries\n\n"
            for d in self.discoveries:
                md += f"- **{d.get('title')}** ({d.get('confidence', 0):.0%}): {d.get('description', '')}\n"
        
        if self.entities:
            md += "\n### Key Entities\n\n"
            for e in self.entities:
                md += f"- [{e.get('entity_type')}] {e.get('canonical_value')}\n"
        
        return md


class ClaudeContextBuilder:
    """Builds context for Claude conversations."""
    
    def __init__(
        self,
        catalog: CatalogDB | None = None,
        vectors: VectorDB | None = None,
        correlation: CorrelationEngine | None = None,
    ) -> None:
        self.catalog = catalog or CatalogDB()
        self.vectors = vectors or VectorDB()
        self.correlation = correlation or get_correlation_engine()
        self.embedder = get_embedding_generator()
    
    def build_context(
        self,
        query: str,
        max_chunks: int = 5,
        max_discoveries: int = 3,
        max_entities: int = 10,
        min_similarity: float = 0.5,
    ) -> ClaudeContext:
        """Build context for a query."""
        context = ClaudeContext(query=query)
        
        # Get relevant chunks via semantic search
        try:
            query_embedding = self.embedder.embed(query)
            results = self.vectors.query(
                collection_name="documents",
                query_embedding=query_embedding,
                n_results=max_chunks,
            )
            
            if results and results.get("ids") and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    similarity = 1 - distance
                    
                    if similarity < min_similarity:
                        continue
                    
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    document = results["documents"][0][i] if results.get("documents") else ""
                    
                    context.chunks.append(ContextChunk(
                        content=document,
                        source=metadata.get("file_path", "unknown"),
                        similarity=similarity,
                        chunk_type=metadata.get("chunk_type", "unknown"),
                    ))
        except Exception as e:
            logger.error(f"Chunk retrieval failed: {e}")
        
        # Get relevant discoveries
        try:
            discoveries = self.correlation.get_discoveries(min_confidence=0.7)
            context.discoveries = [
                d.to_dict() for d in discoveries[:max_discoveries]
            ]
        except Exception as e:
            logger.error(f"Discovery retrieval failed: {e}")
        
        # Get relevant entities
        try:
            entities = self.correlation.get_consolidated_entities(
                min_occurrences=3,
                limit=max_entities,
            )
            context.entities = [
                e.to_dict() for e in entities
            ]
        except Exception as e:
            logger.error(f"Entity retrieval failed: {e}")
        
        return context
    
    def get_system_prompt_addition(self) -> str:
        """Get a system prompt addition with CHIMERA context."""
        try:
            discoveries = self.correlation.get_discoveries(min_confidence=0.8)
            entities = self.correlation.get_consolidated_entities(
                min_occurrences=5,
                limit=20,
            )
            
            if not discoveries and not entities:
                return ""
            
            prompt = """\n\n<chimera_knowledge>
The following information has been automatically discovered from the user's local files and AI conversation history:

"""
            if discoveries:
                prompt += "Key discoveries:\n"
                for d in discoveries[:5]:
                    prompt += f"- {d.title} ({d.confidence:.0%} confidence)\n"
            
            if entities:
                prompt += "\nFrequently mentioned:\n"
                by_type = {}
                for e in entities:
                    et = e.entity_type
                    if et not in by_type:
                        by_type[et] = []
                    by_type[et].append(e.canonical_value)
                
                for et, values in by_type.items():
                    prompt += f"- {et}: {', '.join(values[:5])}\n"
            
            prompt += "</chimera_knowledge>"
            return prompt
            
        except Exception as e:
            logger.error(f"System prompt generation failed: {e}")
            return ""
