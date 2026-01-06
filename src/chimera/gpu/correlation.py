"""GPU-accelerated correlation engine using cuML and cuDF.

Provides massive speedup for:
- Entity co-occurrence computation
- Pattern detection
- Clustering
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from datetime import datetime

from chimera.gpu import GPU_AVAILABLE, CUML_AVAILABLE

logger = logging.getLogger(__name__)


class GPUCorrelationEngine:
    """GPU-accelerated correlation using cuML."""
    
    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu and CUML_AVAILABLE
        
        if self.use_gpu:
            logger.info("GPUCorrelationEngine using cuML")
        else:
            logger.info("GPUCorrelationEngine using CPU fallback (numpy/scipy)")
    
    def compute_cooccurrence_matrix(
        self,
        entity_file_matrix: np.ndarray,
    ) -> np.ndarray:
        """Compute entity co-occurrence matrix.
        
        Args:
            entity_file_matrix: (n_entities, n_files) binary matrix
                                1 if entity appears in file, 0 otherwise
        
        Returns:
            (n_entities, n_entities) co-occurrence count matrix
        """
        if self.use_gpu:
            import cupy as cp
            
            # Move to GPU
            gpu_matrix = cp.asarray(entity_file_matrix.astype(np.float32))
            
            # Co-occurrence = matrix @ matrix.T
            cooccurrence = cp.dot(gpu_matrix, gpu_matrix.T)
            
            # Move back to CPU
            return cp.asnumpy(cooccurrence)
        else:
            # CPU fallback
            matrix = entity_file_matrix.astype(np.float32)
            return np.dot(matrix, matrix.T)
    
    def compute_pmi(
        self,
        cooccurrence: np.ndarray,
        entity_counts: np.ndarray,
        total_files: int,
    ) -> np.ndarray:
        """Compute Pointwise Mutual Information matrix.
        
        PMI(x,y) = log(P(x,y) / (P(x) * P(y)))
        
        High PMI = entities appear together more than expected by chance.
        """
        if self.use_gpu:
            import cupy as cp
            
            cooc = cp.asarray(cooccurrence.astype(np.float32))
            counts = cp.asarray(entity_counts.astype(np.float32))
            
            # P(x,y) = cooccurrence / total_files
            p_xy = cooc / total_files
            
            # P(x) * P(y) = outer product of marginal probabilities
            p_x = counts / total_files
            p_xy_independent = cp.outer(p_x, p_x)
            
            # PMI = log(P(x,y) / (P(x) * P(y)))
            # Add small epsilon to avoid log(0)
            eps = 1e-10
            pmi = cp.log((p_xy + eps) / (p_xy_independent + eps))
            
            # Clip extreme values
            pmi = cp.clip(pmi, -10, 10)
            
            return cp.asnumpy(pmi)
        else:
            # CPU fallback
            p_xy = cooccurrence / total_files
            p_x = entity_counts / total_files
            p_xy_independent = np.outer(p_x, p_x)
            
            eps = 1e-10
            pmi = np.log((p_xy + eps) / (p_xy_independent + eps))
            return np.clip(pmi, -10, 10)
    
    def cluster_entities(
        self,
        embeddings: np.ndarray,
        n_clusters: int = 20,
        algorithm: str = "kmeans",
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Cluster entities by embedding similarity.
        
        Returns:
            labels: Cluster assignment for each entity
            centers: Cluster centroids
        """
        if self.use_gpu:
            if algorithm == "kmeans":
                from cuml.cluster import KMeans
                model = KMeans(n_clusters=n_clusters, random_state=42)
            elif algorithm == "dbscan":
                from cuml.cluster import DBSCAN
                model = DBSCAN(eps=0.5, min_samples=5)
            else:
                raise ValueError(f"Unknown algorithm: {algorithm}")
            
            labels = model.fit_predict(embeddings.astype(np.float32))
            
            if hasattr(model, 'cluster_centers_'):
                centers = model.cluster_centers_
            else:
                centers = None
            
            return np.asarray(labels), np.asarray(centers) if centers is not None else None
        else:
            # CPU fallback using sklearn
            from sklearn.cluster import KMeans, DBSCAN
            
            if algorithm == "kmeans":
                model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            else:
                model = DBSCAN(eps=0.5, min_samples=5)
            
            labels = model.fit_predict(embeddings)
            centers = model.cluster_centers_ if hasattr(model, 'cluster_centers_') else None
            
            return labels, centers
    
    def find_patterns(
        self,
        pmi_matrix: np.ndarray,
        entity_names: List[str],
        min_pmi: float = 2.0,
        min_cooccurrence: int = 3,
        cooccurrence_matrix: Optional[np.ndarray] = None,
    ) -> List[Dict]:
        """Find significant patterns from PMI matrix.
        
        Returns list of patterns:
        {
            "entities": ["entity1", "entity2"],
            "pmi": 3.5,
            "cooccurrence": 15,
            "confidence": 0.85,
        }
        """
        patterns = []
        n = len(entity_names)
        
        # Find pairs with high PMI
        for i in range(n):
            for j in range(i + 1, n):
                pmi = pmi_matrix[i, j]
                
                if pmi >= min_pmi:
                    cooc = int(cooccurrence_matrix[i, j]) if cooccurrence_matrix is not None else 0
                    
                    if cooc >= min_cooccurrence:
                        # Confidence based on PMI and co-occurrence
                        confidence = min(1.0, (pmi / 5.0) * (cooc / 10.0))
                        
                        patterns.append({
                            "entities": [entity_names[i], entity_names[j]],
                            "pmi": float(pmi),
                            "cooccurrence": cooc,
                            "confidence": confidence,
                        })
        
        # Sort by confidence
        patterns.sort(key=lambda x: -x["confidence"])
        
        return patterns[:100]  # Top 100 patterns
    
    def reduce_dimensions(
        self,
        embeddings: np.ndarray,
        n_components: int = 2,
        algorithm: str = "umap",
    ) -> np.ndarray:
        """Reduce embedding dimensions for visualization."""
        if self.use_gpu and algorithm == "umap":
            try:
                from cuml.manifold import UMAP
                reducer = UMAP(n_components=n_components, random_state=42)
                return np.asarray(reducer.fit_transform(embeddings.astype(np.float32)))
            except ImportError:
                pass
        
        # CPU fallback
        if algorithm == "umap":
            try:
                from umap import UMAP
                reducer = UMAP(n_components=n_components, random_state=42)
                return reducer.fit_transform(embeddings)
            except ImportError:
                algorithm = "pca"
        
        if algorithm == "pca":
            from sklearn.decomposition import PCA
            reducer = PCA(n_components=n_components)
            return reducer.fit_transform(embeddings)
        
        raise ValueError(f"Unknown algorithm: {algorithm}")


class CorrelationResult:
    """Result of correlation analysis."""
    
    def __init__(self):
        self.timestamp = datetime.now()
        self.patterns: List[Dict] = []
        self.clusters: Dict[int, List[str]] = {}
        self.stats: Dict = {}
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "patterns": self.patterns,
            "clusters": self.clusters,
            "stats": self.stats,
        }


async def run_gpu_correlation(
    entities: List[Dict],
    embeddings: np.ndarray,
    file_associations: Dict[str, List[str]],  # entity -> list of file_ids
) -> CorrelationResult:
    """Run full GPU-accelerated correlation analysis."""
    
    engine = GPUCorrelationEngine()
    result = CorrelationResult()
    
    n_entities = len(entities)
    entity_names = [e.get("value", str(i)) for i, e in enumerate(entities)]
    
    # Build entity-file matrix
    all_files = list(set(f for files in file_associations.values() for f in files))
    file_to_idx = {f: i for i, f in enumerate(all_files)}
    
    entity_file_matrix = np.zeros((n_entities, len(all_files)), dtype=np.float32)
    entity_counts = np.zeros(n_entities, dtype=np.float32)
    
    for i, entity in enumerate(entities):
        entity_key = entity.get("value", "")
        files = file_associations.get(entity_key, [])
        for f in files:
            if f in file_to_idx:
                entity_file_matrix[i, file_to_idx[f]] = 1
        entity_counts[i] = len(files)
    
    # Compute co-occurrence
    logger.info("Computing co-occurrence matrix...")
    cooccurrence = engine.compute_cooccurrence_matrix(entity_file_matrix)
    
    # Compute PMI
    logger.info("Computing PMI matrix...")
    pmi = engine.compute_pmi(cooccurrence, entity_counts, len(all_files))
    
    # Find patterns
    logger.info("Finding patterns...")
    result.patterns = engine.find_patterns(
        pmi, entity_names,
        min_pmi=1.5,
        min_cooccurrence=2,
        cooccurrence_matrix=cooccurrence,
    )
    
    # Cluster entities
    if embeddings is not None and len(embeddings) >= 20:
        logger.info("Clustering entities...")
        n_clusters = min(20, len(embeddings) // 5)
        labels, centers = engine.cluster_entities(embeddings, n_clusters=n_clusters)
        
        for i, label in enumerate(labels):
            label = int(label)
            if label not in result.clusters:
                result.clusters[label] = []
            result.clusters[label].append(entity_names[i])
    
    result.stats = {
        "entities_processed": n_entities,
        "files_analyzed": len(all_files),
        "patterns_found": len(result.patterns),
        "clusters_formed": len(result.clusters),
        "gpu_used": engine.use_gpu,
    }
    
    logger.info(f"Correlation complete: {result.stats}")
    return result
