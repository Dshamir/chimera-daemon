"""ChromaDB vector storage for CHIMERA."""

from pathlib import Path
from typing import Any

from chimera.config import DEFAULT_CONFIG_DIR

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
            
            self._client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(self.persist_path),
            ))
        
        return self._client
    
    def get_collection(self, name: str) -> Any:
        """Get or create a collection."""
        if name not in self._collections:
            client = self._get_client()
            self._collections[name] = client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]
    
    async def add_documents(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add documents to a collection."""
        collection = self.get_collection(collection_name)
        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
    
    async def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query a collection."""
        collection = self.get_collection(collection_name)
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
        )
    
    async def delete(
        self,
        collection_name: str,
        ids: list[str],
    ) -> None:
        """Delete documents from a collection."""
        collection = self.get_collection(collection_name)
        collection.delete(ids=ids)
    
    def persist(self) -> None:
        """Persist database to disk."""
        if self._client:
            self._client.persist()
