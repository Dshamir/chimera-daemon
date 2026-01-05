"""Extraction pipeline orchestrator.

Coordinates the full extraction process:
1. Extract content
2. Chunk
3. Extract entities
4. Generate embeddings
5. Store results
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from chimera.extractors.base import ExtractionResult
from chimera.extractors.chunker import Chunk, CodeChunker, TextChunker
from chimera.extractors.embeddings import EmbeddingGenerator, get_embedding_generator
from chimera.extractors.entities import EntityExtractor, get_entity_extractor
from chimera.extractors.registry import get_extractor
from chimera.storage.catalog import CatalogDB, ChunkRecord, EntityRecord, FileRecord
from chimera.storage.vectors import VectorDB
from chimera.utils.hashing import generate_id, hash_file
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    """Result of pipeline processing."""
    file_path: Path
    file_id: str
    success: bool = True
    error: str | None = None
    
    # Stats
    chunk_count: int = 0
    entity_count: int = 0
    embedding_count: int = 0
    word_count: int = 0
    
    # Timing
    extraction_time: float = 0
    chunking_time: float = 0
    embedding_time: float = 0
    total_time: float = 0


class ExtractionPipeline:
    """Orchestrates the full extraction process."""
    
    def __init__(
        self,
        catalog: CatalogDB | None = None,
        vectors: VectorDB | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
        entity_extractor: EntityExtractor | None = None,
    ) -> None:
        self.catalog = catalog or CatalogDB()
        self.vectors = vectors or VectorDB()
        self.embeddings = embedding_generator or get_embedding_generator()
        self.entities = entity_extractor or get_entity_extractor()
        
        self.text_chunker = TextChunker()
        self.code_chunker = CodeChunker()
    
    async def process_file(self, file_path: Path) -> PipelineResult:
        """Process a single file through the extraction pipeline."""
        import time
        start_time = time.time()
        
        file_id = generate_id("file", str(file_path))
        result = PipelineResult(file_path=file_path, file_id=file_id)
        
        try:
            # Step 1: Get extractor
            extractor = get_extractor(file_path)
            if not extractor:
                logger.warning(f"No extractor for: {file_path}")
                result.success = False
                result.error = f"No extractor for extension: {file_path.suffix}"
                return result
            
            # Step 2: Extract content
            extract_start = time.time()
            extraction = await extractor.extract(file_path)
            result.extraction_time = time.time() - extract_start
            
            if not extraction.success:
                result.success = False
                result.error = extraction.error
                self._update_file_status(file_id, file_path, "failed", extraction.error)
                return result
            
            result.word_count = extraction.word_count
            
            # Step 3: Create/update file record
            file_record = self._create_file_record(file_id, file_path, extraction)
            self.catalog.add_file(file_record)
            
            # Step 4: Chunk content
            chunk_start = time.time()
            chunks = self._chunk_content(extraction)
            result.chunking_time = time.time() - chunk_start
            result.chunk_count = len(chunks)
            
            if not chunks:
                logger.warning(f"No chunks generated for: {file_path}")
                self._update_file_status(file_id, file_path, "indexed")
                return result
            
            # Step 5: Extract entities from full content
            entities = self.entities.extract(extraction.content)
            result.entity_count = len(entities)
            
            # Store entities
            if entities:
                entity_records = [
                    EntityRecord(
                        id=generate_id("ent", f"{file_id}_{i}"),
                        file_id=file_id,
                        entity_type=e.label,
                        value=e.text,
                        normalized=self.entities.normalize(e),
                        confidence=e.confidence,
                        context=e.context,
                        position=e.start,
                    )
                    for i, e in enumerate(entities)
                ]
                self.catalog.add_entities(entity_records)
            
            # Step 6: Generate embeddings
            embed_start = time.time()
            chunk_texts = [c.content for c in chunks]
            embeddings = self.embeddings.embed_batch(chunk_texts)
            result.embedding_time = time.time() - embed_start
            result.embedding_count = len(embeddings)
            
            # Step 7: Store chunks and embeddings
            chunk_records = []
            chunk_ids = []
            chunk_metadatas = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = generate_id("chunk", f"{file_id}_{i}")
                chunk_ids.append(chunk_id)
                
                chunk_records.append(ChunkRecord(
                    id=chunk_id,
                    file_id=file_id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    chunk_type=chunk.chunk_type,
                    embedding_id=chunk_id,
                ))
                
                chunk_metadatas.append({
                    "file_id": file_id,
                    "file_path": str(file_path),
                    "chunk_index": chunk.index,
                    "chunk_type": chunk.chunk_type,
                })
            
            # Store in catalog
            self.catalog.add_chunks(chunk_records)
            
            # Store in vector DB
            self.vectors.add_documents(
                collection_name="documents",
                ids=chunk_ids,
                documents=chunk_texts,
                embeddings=embeddings,
                metadatas=chunk_metadatas,
            )
            
            # Update file status
            self._update_file_status(file_id, file_path, "indexed")
            
            result.total_time = time.time() - start_time
            logger.info(
                f"Processed: {file_path.name} "
                f"({result.chunk_count} chunks, {result.entity_count} entities, "
                f"{result.total_time:.2f}s)"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Pipeline failed for {file_path}: {e}")
            result.success = False
            result.error = str(e)
            result.total_time = time.time() - start_time
            self._update_file_status(file_id, file_path, "failed", str(e))
            return result
    
    def _create_file_record(self, file_id: str, file_path: Path, extraction: ExtractionResult) -> FileRecord:
        """Create a file record from extraction result."""
        stat = file_path.stat()
        
        return FileRecord(
            id=file_id,
            path=str(file_path),
            filename=file_path.name,
            extension=file_path.suffix.lstrip(".").lower(),
            mime_type=extraction.metadata.get("mime_type"),
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            indexed_at=datetime.now(),
            content_hash=hash_file(file_path),
            status="indexing",
            word_count=extraction.word_count,
            page_count=extraction.page_count,
            language=extraction.language,
        )
    
    def _chunk_content(self, extraction: ExtractionResult) -> list[Chunk]:
        """Chunk extracted content."""
        if extraction.code_elements:
            # Use code chunker for code files
            return self.code_chunker.chunk(
                extraction.content, 
                extraction.code_elements
            )
        else:
            # Use text chunker for documents
            return self.text_chunker.chunk(extraction.content)
    
    def _update_file_status(self, file_id: str, file_path: Path, status: str, error: str | None = None) -> None:
        """Update file status in catalog."""
        self.catalog.update_file_status(file_id, status, error)
        self.catalog.log_audit(
            action=f"file_{status}",
            entity_type="file",
            entity_id=file_id,
            details=str(file_path),
        )
    
    async def process_batch(self, file_paths: list[Path]) -> list[PipelineResult]:
        """Process multiple files."""
        results = []
        for file_path in file_paths:
            result = await self.process_file(file_path)
            results.append(result)
        return results


# Global pipeline instance
_pipeline: ExtractionPipeline | None = None


def get_pipeline() -> ExtractionPipeline:
    """Get the global extraction pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = ExtractionPipeline()
    return _pipeline
