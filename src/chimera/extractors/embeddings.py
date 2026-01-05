"""Embedding generation for CHIMERA.

Uses sentence-transformers for local embedding generation.
Default model: all-MiniLM-L6-v2 (384 dimensions)
"""

from typing import Any

from chimera.utils.logging import get_logger

logger = get_logger(__name__)


class EmbeddingGenerator:
    """Generate embeddings for text content."""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None
        self._dimension: int | None = None
    
    def _load_model(self) -> Any:
        """Lazy load the embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                
                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
                logger.info(f"Embedding model loaded. Dimension: {self._dimension}")
            except ImportError:
                logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
                raise
        
        return self._model
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        if self._dimension is None:
            self._load_model()
        return self._dimension or 384
    
    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        model = self._load_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []
        
        model = self._load_model()
        embeddings = model.encode(
            texts, 
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 100,
        )
        
        return [e.tolist() for e in embeddings]
    
    def embed_with_cache(
        self, 
        texts: list[str], 
        cache: dict[str, list[float]] | None = None,
    ) -> tuple[list[list[float]], dict[str, list[float]]]:
        """Generate embeddings with caching."""
        if cache is None:
            cache = {}
        
        results = []
        texts_to_embed = []
        text_indices = []
        
        for i, text in enumerate(texts):
            # Use text hash as cache key
            cache_key = str(hash(text))
            if cache_key in cache:
                results.append(cache[cache_key])
            else:
                texts_to_embed.append(text)
                text_indices.append(i)
                results.append(None)  # Placeholder
        
        # Embed uncached texts
        if texts_to_embed:
            new_embeddings = self.embed_batch(texts_to_embed)
            
            for idx, (text, embedding) in zip(text_indices, zip(texts_to_embed, new_embeddings)):
                cache_key = str(hash(text))
                cache[cache_key] = embedding
                results[idx] = embedding
        
        return results, cache


# Global embedding generator instance
_generator: EmbeddingGenerator | None = None


def get_embedding_generator(model_name: str | None = None) -> EmbeddingGenerator:
    """Get the global embedding generator."""
    global _generator
    
    if _generator is None or (model_name and model_name != _generator.model_name):
        _generator = EmbeddingGenerator(model_name or "sentence-transformers/all-MiniLM-L6-v2")
    
    return _generator


def embed_text(text: str) -> list[float]:
    """Quick helper to embed a single text."""
    return get_embedding_generator().embed(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Quick helper to embed multiple texts."""
    return get_embedding_generator().embed_batch(texts)
