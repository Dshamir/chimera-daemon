"""ChromaDB vector storage for CHIMERA.

Handles embedding storage and semantic search.
"""

from pathlib import Path
from typing import Any

from chimera.config import DEFAULT_CONFIG_DIR
from chimera.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_VECTORS_PATH = DEFAULT_CONFIG_DIR / "vectors"


class VectorDB:
    """ChromaDB vector database for semantic search."""
    
    def __init__(self, persist_path: Path | None = None) -> None:
        self.persist_path = persist_path or DEFAULT_VECTORS_PATH
        self._client = None
        self._collections: dict[str, Any] = {}
    
    def _get_client(self) -> Any:
        """Get or create ChromaDB client."""
        if self._client is None:
            import chromadb
            from chromadb.config import Settings
            
            self.persist_path.mkdir(parents=True, exist_ok=True)
            
            self._client = chromadb.PersistentClient(
                path=str(self.persist_path),
                settings=Settings(
                    anonymized_telemetry=False,
                ),
            )
            logger.debug(f"ChromaDB client initialized: {self.persist_path}")
        
        return self._client
    
    def get_collection(self, name: str) -> Any:
        """Get or create a collection."""
        if name not in self._collections:
            client = self._get_client()
            self._collections[name] = client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.debug(f"Collection ready: {name}")
        return self._collections[name]
    
    def add_documents(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> int:
        """Add documents to a collection."""
        collection = self.get_collection(collection_name)
        
        # ChromaDB expects metadatas if provided
        if metadatas is None:
            metadatas = [{} for _ in ids]
        
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        
        logger.debug(f"Added {len(ids)} documents to {collection_name}")
        return len(ids)
    
    def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query a collection by embedding."""
        collection = self.get_collection(collection_name)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        
        return results
    
    def query_text(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query a collection by text (uses collection's embedding function)."""
        collection = self.get_collection(collection_name)
        
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        
        return results
    
    def delete(
        self,
        collection_name: str,
        ids: list[str],
    ) -> None:
        """Delete documents from a collection."""
        collection = self.get_collection(collection_name)
        collection.delete(ids=ids)
        logger.debug(f"Deleted {len(ids)} documents from {collection_name}")
    
    def delete_by_metadata(
        self,
        collection_name: str,
        where: dict[str, Any],
    ) -> None:
        """Delete documents matching metadata filter."""
        collection = self.get_collection(collection_name)
        collection.delete(where=where)
    
    def count(self, collection_name: str) -> int:
        """Get document count in collection."""
        collection = self.get_collection(collection_name)
        return collection.count()
    
    def get_stats(self) -> dict[str, Any]:
        """Get vector database statistics."""
        client = self._get_client()
        collections = client.list_collections()
        
        stats = {
            "collections": {},
            "total_documents": 0,
        }
        
        for coll in collections:
            count = coll.count()
            stats["collections"][coll.name] = count
            stats["total_documents"] += count
        
        return stats
