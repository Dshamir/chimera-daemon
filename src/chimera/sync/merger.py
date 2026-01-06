"""Catalog Merger - Combines excavations from multiple machines.

Handles:
- Deduplication across machines
- Entity consolidation
- File path normalization
- Conflict resolution
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class MergeResult:
    """Result of a catalog merge operation."""
    
    timestamp: datetime = field(default_factory=datetime.now)
    machines_merged: List[str] = field(default_factory=list)
    files_added: int = 0
    files_deduplicated: int = 0
    chunks_added: int = 0
    entities_added: int = 0
    entities_consolidated: int = 0
    conflicts_resolved: int = 0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "machines_merged": self.machines_merged,
            "files_added": self.files_added,
            "files_deduplicated": self.files_deduplicated,
            "chunks_added": self.chunks_added,
            "entities_added": self.entities_added,
            "entities_consolidated": self.entities_consolidated,
            "conflicts_resolved": self.conflicts_resolved,
            "errors": self.errors,
        }


class CatalogMerger:
    """Merges excavation catalogs from multiple machines."""
    
    def __init__(self, master_catalog_path: Optional[Path] = None):
        from chimera.config import DEFAULT_CONFIG_DIR
        self.master_path = master_catalog_path or DEFAULT_CONFIG_DIR
        self.merge_log_path = self.master_path / "merge_log.jsonl"
        
        # Track seen content hashes for deduplication
        self._content_hashes: Set[str] = set()
        self._entity_map: Dict[str, str] = {}  # normalized -> canonical
    
    def _compute_content_hash(self, content: str) -> str:
        """Compute hash for content deduplication."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _normalize_entity(self, value: str) -> str:
        """Normalize entity for consolidation."""
        # Lowercase, strip whitespace, remove common variations
        normalized = value.lower().strip()
        
        # Remove common suffixes/prefixes
        for suffix in [" inc", " inc.", " llc", " ltd", " corp", " corporation"]:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        
        # Remove punctuation variations
        normalized = normalized.replace(".", "").replace(",", "")
        
        return normalized
    
    def _load_master_hashes(self):
        """Load existing content hashes from master catalog."""
        try:
            from chimera.storage.catalog import CatalogDB
            catalog = CatalogDB()
            
            # Get existing chunk hashes
            # This would need to be implemented in CatalogDB
            # For now, we'll track in memory during merge session
            pass
        except Exception as e:
            logger.warning(f"Could not load master hashes: {e}")
    
    async def merge_excavation(self, excavation_path: Path) -> MergeResult:
        """Merge a single excavation into master catalog."""
        result = MergeResult()
        
        # Load excavation metadata
        metadata_file = excavation_path / "metadata" / "excavation.json"
        if not metadata_file.exists():
            result.errors.append(f"No metadata found: {excavation_path}")
            return result
        
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        machine_id = metadata.get("machine_id", excavation_path.name)
        result.machines_merged.append(machine_id)
        
        logger.info(f"Merging excavation from {machine_id}")
        
        # Import to master catalog
        from chimera.storage.catalog import CatalogDB, FileRecord, ChunkRecord, EntityRecord
        from chimera.utils.hashing import generate_id
        
        catalog = CatalogDB()
        
        # Process chunks
        chunks_dir = excavation_path / "chunks"
        if chunks_dir.exists():
            for chunk_file in chunks_dir.glob("*.json"):
                try:
                    with open(chunk_file) as f:
                        data = json.load(f)
                    
                    file_path = data.get("file_path", "")
                    file_id = data.get("file_id")
                    
                    # Tag with source machine
                    source_tag = f"[{machine_id}]"
                    
                    # Create file record with machine tag
                    file_record = FileRecord(
                        id=f"{machine_id}_{file_id}",
                        path=f"{source_tag} {file_path}",
                        filename=data.get("file_name", Path(file_path).name),
                        extension=Path(file_path).suffix.lstrip(".").lower(),
                        status="synced",
                        indexed_at=datetime.now(),
                        metadata={"source_machine": machine_id},
                    )
                    
                    try:
                        catalog.add_file(file_record)
                        result.files_added += 1
                    except Exception:
                        result.files_deduplicated += 1
                    
                    # Process chunks with deduplication
                    for chunk in data.get("chunks", []):
                        content = chunk.get("content", "")
                        content_hash = self._compute_content_hash(content)
                        
                        if content_hash in self._content_hashes:
                            result.files_deduplicated += 1
                            continue
                        
                        self._content_hashes.add(content_hash)
                        
                        chunk_id = generate_id("chunk", f"{machine_id}_{file_id}_{chunk['index']}")
                        chunk_record = ChunkRecord(
                            id=chunk_id,
                            file_id=f"{machine_id}_{file_id}",
                            chunk_index=chunk["index"],
                            content=content,
                            chunk_type="paragraph",
                            metadata={"source_machine": machine_id, "content_hash": content_hash},
                        )
                        
                        try:
                            catalog.add_chunks([chunk_record])
                            result.chunks_added += 1
                        except Exception as e:
                            result.errors.append(f"Chunk error: {e}")
                
                except Exception as e:
                    result.errors.append(f"File error {chunk_file}: {e}")
        
        # Process entities with consolidation
        entities_dir = excavation_path / "entities"
        if entities_dir.exists():
            for entity_file in entities_dir.glob("*.json"):
                try:
                    with open(entity_file) as f:
                        data = json.load(f)
                    
                    file_id = f"{machine_id}_{data.get('file_id')}"
                    
                    for i, entity in enumerate(data.get("entities", [])):
                        value = entity.get("value", "")
                        entity_type = entity.get("type", "UNKNOWN")
                        
                        # Normalize for consolidation
                        normalized = self._normalize_entity(value)
                        
                        # Check if we've seen this entity before
                        if normalized in self._entity_map:
                            canonical = self._entity_map[normalized]
                            result.entities_consolidated += 1
                        else:
                            canonical = value
                            self._entity_map[normalized] = canonical
                        
                        entity_id = generate_id("ent", f"{machine_id}_{file_id}_{i}")
                        entity_record = EntityRecord(
                            id=entity_id,
                            file_id=file_id,
                            entity_type=entity_type,
                            value=value,
                            normalized=normalized,
                            confidence=0.8,
                            metadata={
                                "source_machine": machine_id,
                                "canonical": canonical,
                            },
                        )
                        
                        try:
                            catalog.add_entities([entity_record])
                            result.entities_added += 1
                        except Exception:
                            pass
                
                except Exception as e:
                    result.errors.append(f"Entity error {entity_file}: {e}")
        
        # Log merge
        self._log_merge(result)
        
        logger.info(
            f"Merge complete: {result.files_added} files, "
            f"{result.chunks_added} chunks, {result.entities_added} entities"
        )
        
        return result
    
    async def merge_all(self, excavations_dir: Path) -> MergeResult:
        """Merge all excavations in a directory."""
        combined_result = MergeResult()
        
        for exc_path in excavations_dir.iterdir():
            if exc_path.is_dir() and (exc_path / "metadata" / "excavation.json").exists():
                result = await self.merge_excavation(exc_path)
                
                # Combine results
                combined_result.machines_merged.extend(result.machines_merged)
                combined_result.files_added += result.files_added
                combined_result.files_deduplicated += result.files_deduplicated
                combined_result.chunks_added += result.chunks_added
                combined_result.entities_added += result.entities_added
                combined_result.entities_consolidated += result.entities_consolidated
                combined_result.errors.extend(result.errors)
        
        return combined_result
    
    def _log_merge(self, result: MergeResult):
        """Log merge operation."""
        with open(self.merge_log_path, "a") as f:
            f.write(json.dumps(result.to_dict()) + "\n")
    
    def get_merge_history(self, limit: int = 20) -> List[dict]:
        """Get recent merge history."""
        if not self.merge_log_path.exists():
            return []
        
        history = []
        with open(self.merge_log_path) as f:
            for line in f:
                try:
                    history.append(json.loads(line))
                except:
                    pass
        
        return history[-limit:]
