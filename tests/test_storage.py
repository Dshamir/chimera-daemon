"""Tests for storage modules."""

import pytest
from datetime import datetime

from chimera.storage.catalog import CatalogDB, FileRecord, ChunkRecord, EntityRecord


@pytest.fixture
def catalog(temp_dir):
    """Create test catalog."""
    return CatalogDB(db_path=temp_dir / "test_catalog.db")


def test_catalog_init(catalog):
    """Test catalog initialization."""
    assert catalog.db_path.exists()


def test_add_file(catalog):
    """Test adding a file to catalog."""
    file = FileRecord(
        id="file_001",
        path="/test/document.pdf",
        filename="document.pdf",
        extension="pdf",
        size_bytes=1024,
        status="pending",
    )
    
    file_id = catalog.add_file(file)
    assert file_id == "file_001"
    
    # Retrieve file
    retrieved = catalog.get_file("file_001")
    assert retrieved is not None
    assert retrieved.path == "/test/document.pdf"
    assert retrieved.filename == "document.pdf"


def test_get_file_by_path(catalog):
    """Test getting file by path."""
    file = FileRecord(
        id="file_002",
        path="/test/readme.md",
        filename="readme.md",
        extension="md",
    )
    catalog.add_file(file)
    
    retrieved = catalog.get_file_by_path("/test/readme.md")
    assert retrieved is not None
    assert retrieved.id == "file_002"


def test_update_file_status(catalog):
    """Test updating file status."""
    file = FileRecord(
        id="file_003",
        path="/test/data.json",
        filename="data.json",
        extension="json",
        status="pending",
    )
    catalog.add_file(file)
    
    catalog.update_file_status("file_003", "indexed")
    
    retrieved = catalog.get_file("file_003")
    assert retrieved.status == "indexed"
    assert retrieved.indexed_at is not None


def test_add_chunks(catalog):
    """Test adding chunks."""
    # First add a file
    file = FileRecord(
        id="file_004",
        path="/test/doc.txt",
        filename="doc.txt",
    )
    catalog.add_file(file)
    
    # Add chunks
    chunks = [
        ChunkRecord(
            id="chunk_001",
            file_id="file_004",
            chunk_index=0,
            content="First chunk content",
            chunk_type="paragraph",
        ),
        ChunkRecord(
            id="chunk_002",
            file_id="file_004",
            chunk_index=1,
            content="Second chunk content",
            chunk_type="paragraph",
        ),
    ]
    
    count = catalog.add_chunks(chunks)
    assert count == 2
    
    # Retrieve chunks
    retrieved = catalog.get_chunks_for_file("file_004")
    assert len(retrieved) == 2
    assert retrieved[0].content == "First chunk content"


def test_add_entities(catalog):
    """Test adding entities."""
    file = FileRecord(
        id="file_005",
        path="/test/report.pdf",
        filename="report.pdf",
    )
    catalog.add_file(file)
    
    entities = [
        EntityRecord(
            id="ent_001",
            file_id="file_005",
            entity_type="PERSON",
            value="John Doe",
            normalized="john doe",
        ),
        EntityRecord(
            id="ent_002",
            file_id="file_005",
            entity_type="ORG",
            value="Acme Corp",
            normalized="acme corp",
        ),
    ]
    
    count = catalog.add_entities(entities)
    assert count == 2
    
    retrieved = catalog.get_entities_for_file("file_005")
    assert len(retrieved) == 2


def test_catalog_stats(catalog):
    """Test catalog statistics."""
    # Add some files
    for i in range(5):
        file = FileRecord(
            id=f"file_{i:03d}",
            path=f"/test/file{i}.txt",
            filename=f"file{i}.txt",
            extension="txt",
            status="indexed" if i < 3 else "pending",
        )
        catalog.add_file(file)
    
    stats = catalog.get_stats()
    
    assert stats["total_files"] == 5
    assert "files_by_status" in stats
    assert stats["files_by_status"].get("indexed", 0) == 3
    assert stats["files_by_status"].get("pending", 0) == 2
