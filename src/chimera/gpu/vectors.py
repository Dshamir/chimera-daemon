"""GPU-accelerated vector operations using FAISS.

Provides fast similarity search for millions of vectors.
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple

from chimera.gpu import GPU_AVAILABLE, FAISS_GPU_AVAILABLE

logger = logging.getLogger(__name__)


class GPUVectorIndex:
    """FAISS-based vector index with GPU acceleration."""
    
    def __init__(
        self,
        dimension: int = 384,  # Default for all-MiniLM-L6-v2
        index_type: str = "IVF",  # IVF, Flat, HNSW
        nlist: int = 100,  # Number of clusters for IVF
        use_gpu: bool = True,
    ):
        self.dimension = dimension
        self.index_type = index_type
        self.nlist = nlist
        self.use_gpu = use_gpu and FAISS_GPU_AVAILABLE
        
        self.index = None
        self.id_map: List[str] = []  # Map index position to document ID
        self.gpu_resources = None
        
        self._init_index()
    
    def _init_index(self):
        """Initialize FAISS index."""
        try:
            import faiss
        except ImportError:
            raise ImportError("FAISS not installed. Run: pip install faiss-cpu or faiss-gpu")
        
        if self.index_type == "Flat":
            # Exact search - slow but accurate
            self.index = faiss.IndexFlatL2(self.dimension)
        
        elif self.index_type == "IVF":
            # Inverted file index - fast approximate search
            quantizer = faiss.IndexFlatL2(self.dimension)
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, self.nlist)
        
        elif self.index_type == "HNSW":
            # Hierarchical Navigable Small World - very fast
            self.index = faiss.IndexHNSWFlat(self.dimension, 32)  # 32 neighbors
        
        else:
            raise ValueError(f"Unknown index type: {self.index_type}")
        
        # Move to GPU if available
        if self.use_gpu:
            try:
                self.gpu_resources = faiss.StandardGpuResources()
                self.index = faiss.index_cpu_to_gpu(self.gpu_resources, 0, self.index)
                logger.info("FAISS index moved to GPU")
            except Exception as e:
                logger.warning(f"Failed to move index to GPU: {e}")
                self.use_gpu = False
    
    def train(self, vectors: np.ndarray):
        """Train the index (required for IVF)."""
        if self.index_type == "IVF" and not self.index.is_trained:
            logger.info(f"Training IVF index on {len(vectors)} vectors...")
            self.index.train(vectors.astype(np.float32))
    
    def add(self, vectors: np.ndarray, ids: List[str]):
        """Add vectors to index."""
        if len(vectors) != len(ids):
            raise ValueError("Number of vectors must match number of IDs")
        
        vectors = np.array(vectors).astype(np.float32)
        
        # Train if needed
        if self.index_type == "IVF" and not self.index.is_trained:
            self.train(vectors)
        
        # Add to index
        self.index.add(vectors)
        self.id_map.extend(ids)
        
        logger.debug(f"Added {len(vectors)} vectors to index")
    
    def search(
        self,
        query_vectors: np.ndarray,
        k: int = 10,
        nprobe: int = 10,  # For IVF: number of clusters to search
    ) -> Tuple[np.ndarray, np.ndarray, List[List[str]]]:
        """Search for similar vectors.
        
        Returns:
            distances: (n_queries, k) array of distances
            indices: (n_queries, k) array of indices
            ids: List of lists of document IDs
        """
        query_vectors = np.array(query_vectors).astype(np.float32)
        
        if len(query_vectors.shape) == 1:
            query_vectors = query_vectors.reshape(1, -1)
        
        # Set search parameters
        if self.index_type == "IVF":
            self.index.nprobe = nprobe
        
        # Search
        distances, indices = self.index.search(query_vectors, k)
        
        # Map indices to IDs
        ids = []
        for idx_row in indices:
            row_ids = []
            for idx in idx_row:
                if 0 <= idx < len(self.id_map):
                    row_ids.append(self.id_map[idx])
                else:
                    row_ids.append(None)
            ids.append(row_ids)
        
        return distances, indices, ids
    
    def save(self, path: Path):
        """Save index to disk."""
        import faiss
        import json
        
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        # Move to CPU for saving
        if self.use_gpu:
            cpu_index = faiss.index_gpu_to_cpu(self.index)
        else:
            cpu_index = self.index
        
        faiss.write_index(cpu_index, str(path / "index.faiss"))
        
        with open(path / "id_map.json", "w") as f:
            json.dump(self.id_map, f)
        
        with open(path / "config.json", "w") as f:
            json.dump({
                "dimension": self.dimension,
                "index_type": self.index_type,
                "nlist": self.nlist,
            }, f)
        
        logger.info(f"Saved index to {path}")
    
    @classmethod
    def load(cls, path: Path, use_gpu: bool = True) -> "GPUVectorIndex":
        """Load index from disk."""
        import faiss
        import json
        
        path = Path(path)
        
        with open(path / "config.json") as f:
            config = json.load(f)
        
        instance = cls(
            dimension=config["dimension"],
            index_type=config["index_type"],
            nlist=config.get("nlist", 100),
            use_gpu=False,  # Load to CPU first
        )
        
        instance.index = faiss.read_index(str(path / "index.faiss"))
        
        with open(path / "id_map.json") as f:
            instance.id_map = json.load(f)
        
        # Move to GPU if requested
        if use_gpu and FAISS_GPU_AVAILABLE:
            try:
                instance.gpu_resources = faiss.StandardGpuResources()
                instance.index = faiss.index_cpu_to_gpu(
                    instance.gpu_resources, 0, instance.index
                )
                instance.use_gpu = True
                logger.info("Loaded index to GPU")
            except Exception as e:
                logger.warning(f"Failed to move loaded index to GPU: {e}")
        
        logger.info(f"Loaded index from {path} ({len(instance.id_map)} vectors)")
        return instance
    
    def __len__(self) -> int:
        return len(self.id_map)


class HybridVectorStore:
    """Hybrid vector store using GPU when available, CPU fallback."""
    
    def __init__(self, data_dir: Path, dimension: int = 384):
        self.data_dir = Path(data_dir)
        self.dimension = dimension
        
        # Try GPU first, fall back to ChromaDB
        if FAISS_GPU_AVAILABLE:
            self.backend = "faiss_gpu"
            self.index = GPUVectorIndex(dimension=dimension, use_gpu=True)
        else:
            self.backend = "chromadb"
            self.index = None  # Will use ChromaDB from storage.vectors
        
        logger.info(f"HybridVectorStore using backend: {self.backend}")
    
    def add(self, vectors: np.ndarray, ids: List[str], metadatas: List[dict] = None):
        """Add vectors."""
        if self.backend == "faiss_gpu":
            self.index.add(vectors, ids)
            # Store metadata separately if needed
        else:
            from chimera.storage.vectors import VectorDB
            vdb = VectorDB()
            # ChromaDB handles this differently
            for i, (vec, doc_id) in enumerate(zip(vectors, ids)):
                vdb.add(
                    "documents",
                    embeddings=[vec.tolist()],
                    documents=[""],  # Would need actual document
                    metadatas=[metadatas[i] if metadatas else {}],
                    ids=[doc_id],
                )
    
    def search(self, query_vector: np.ndarray, k: int = 10) -> List[dict]:
        """Search for similar vectors."""
        if self.backend == "faiss_gpu":
            distances, indices, ids = self.index.search(query_vector, k)
            return [
                {"id": id, "distance": dist}
                for id, dist in zip(ids[0], distances[0])
                if id is not None
            ]
        else:
            from chimera.storage.vectors import VectorDB
            vdb = VectorDB()
            results = vdb.query("documents", query_vector.tolist(), n_results=k)
            return [
                {"id": id, "distance": dist}
                for id, dist in zip(results["ids"][0], results["distances"][0])
            ]
