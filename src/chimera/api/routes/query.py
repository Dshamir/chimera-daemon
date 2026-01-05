"""Query endpoints for CHIMERA API."""

from fastapi import APIRouter, Query

from chimera.correlation.engine import get_correlation_engine
from chimera.storage.catalog import CatalogDB
from chimera.storage.vectors import VectorDB
from chimera.extractors.embeddings import get_embedding_generator

router = APIRouter()


@router.get("/query")
async def semantic_query(
    q: str = Query(..., description="Natural language query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    min_confidence: float = Query(0.5, ge=0, le=1, description="Minimum similarity"),
) -> dict:
    """Semantic search across all indexed content."""
    try:
        # Get embedding for query
        embedder = get_embedding_generator()
        query_embedding = embedder.embed(q)
        
        # Search vector DB
        vectors = VectorDB()
        results = vectors.query(
            collection_name="documents",
            query_embedding=query_embedding,
            n_results=limit,
        )
        
        # Format results
        formatted = []
        if results and results.get("ids") and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results.get("distances") else 0
                similarity = 1 - distance  # Convert distance to similarity
                
                if similarity < min_confidence:
                    continue
                
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                document = results["documents"][0][i] if results.get("documents") else ""
                
                formatted.append({
                    "id": doc_id,
                    "similarity": round(similarity, 3),
                    "file_path": metadata.get("file_path", ""),
                    "chunk_type": metadata.get("chunk_type", ""),
                    "content": document[:500] + "..." if len(document) > 500 else document,
                })
        
        return {
            "query": q,
            "results": formatted,
            "total": len(formatted),
        }
    except Exception as e:
        return {
            "query": q,
            "results": [],
            "total": 0,
            "error": str(e),
        }


@router.post("/search")
async def advanced_search(request: dict) -> dict:
    """Advanced search with filters."""
    query = request.get("query", "")
    filters = request.get("filters", {})
    limit = request.get("limit", 20)
    
    try:
        # Build ChromaDB where clause from filters
        where = None
        if filters:
            where = {}
            if "file_type" in filters:
                where["chunk_type"] = filters["file_type"]
        
        vectors = VectorDB()
        results = vectors.query_text(
            collection_name="documents",
            query_text=query,
            n_results=limit,
            where=where,
        )
        
        formatted = []
        if results and results.get("ids") and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                document = results["documents"][0][i] if results.get("documents") else ""
                
                formatted.append({
                    "id": doc_id,
                    "file_path": metadata.get("file_path", ""),
                    "content_preview": document[:300],
                })
        
        return {
            "results": formatted,
            "total": len(formatted),
            "filters": filters,
        }
    except Exception as e:
        return {
            "results": [],
            "total": 0,
            "error": str(e),
        }


@router.get("/file/{file_id}")
async def get_file(file_id: str) -> dict:
    """Get file details with extracted content."""
    try:
        catalog = CatalogDB()
        file_record = catalog.get_file(file_id)
        
        if not file_record:
            return {"error": "File not found", "id": file_id}
        
        chunks = catalog.get_chunks_for_file(file_id)
        entities = catalog.get_entities_for_file(file_id)
        
        return {
            "id": file_id,
            "path": file_record.path,
            "filename": file_record.filename,
            "extension": file_record.extension,
            "status": file_record.status,
            "indexed_at": file_record.indexed_at.isoformat() if file_record.indexed_at else None,
            "word_count": file_record.word_count,
            "chunk_count": len(chunks),
            "entity_count": len(entities),
            "chunks": [
                {"index": c.chunk_index, "type": c.chunk_type, "content": c.content[:200]}
                for c in chunks[:10]  # First 10 chunks
            ],
            "entities": [
                {"type": e.entity_type, "value": e.value}
                for e in entities[:20]  # First 20 entities
            ],
        }
    except Exception as e:
        return {"error": str(e), "id": file_id}


@router.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict:
    """Get conversation details (FAE)."""
    try:
        catalog = CatalogDB()
        conn = catalog.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, provider, title, created_at, updated_at, message_count, summary
            FROM conversations
            WHERE id = ?
        """, (conversation_id,))
        
        row = cursor.fetchone()
        if not row:
            return {"error": "Conversation not found", "id": conversation_id}
        
        # Get messages
        cursor.execute("""
            SELECT role, content, timestamp
            FROM messages
            WHERE conversation_id = ?
            ORDER BY sequence
            LIMIT 50
        """, (conversation_id,))
        
        messages = [
            {"role": r[0], "content": r[1][:500], "timestamp": r[2]}
            for r in cursor.fetchall()
        ]
        
        conn.close()
        
        return {
            "id": row[0],
            "provider": row[1],
            "title": row[2],
            "created_at": row[3],
            "updated_at": row[4],
            "message_count": row[5],
            "summary": row[6],
            "messages": messages,
        }
    except Exception as e:
        return {"error": str(e), "id": conversation_id}


@router.get("/discoveries")
async def list_discoveries(
    discovery_type: str | None = Query(None, description="Filter by type"),
    min_confidence: float = Query(0.7, ge=0, le=1),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """List surfaced discoveries."""
    try:
        engine = get_correlation_engine()
        discoveries = engine.get_discoveries(
            discovery_type=discovery_type,
            status=status,
            min_confidence=min_confidence,
        )[:limit]
        
        return {
            "discoveries": [d.to_dict() for d in discoveries],
            "total": len(discoveries),
            "filters": {
                "type": discovery_type,
                "min_confidence": min_confidence,
                "status": status,
            },
        }
    except Exception as e:
        return {
            "discoveries": [],
            "total": 0,
            "error": str(e),
        }


@router.get("/discoveries/{discovery_id}")
async def get_discovery(discovery_id: str) -> dict:
    """Get discovery details with evidence."""
    try:
        engine = get_correlation_engine()
        discoveries = engine.get_discoveries()
        
        for d in discoveries:
            if d.id == discovery_id:
                return d.to_dict()
        
        return {"error": "Discovery not found", "id": discovery_id}
    except Exception as e:
        return {"error": str(e), "id": discovery_id}


@router.get("/entities")
async def list_entities(
    entity_type: str | None = Query(None, description="Filter by type"),
    min_occurrences: int = Query(2, ge=1),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """List consolidated entities."""
    try:
        engine = get_correlation_engine()
        entities = engine.get_consolidated_entities(
            entity_type=entity_type,
            min_occurrences=min_occurrences,
            limit=limit,
        )
        
        return {
            "entities": [e.to_dict() for e in entities],
            "total": len(entities),
        }
    except Exception as e:
        return {
            "entities": [],
            "total": 0,
            "error": str(e),
        }


@router.get("/patterns")
async def list_patterns(
    pattern_type: str | None = Query(None, description="Filter by type"),
    min_confidence: float = Query(0.5, ge=0, le=1),
) -> dict:
    """List detected patterns."""
    try:
        engine = get_correlation_engine()
        patterns = engine.get_patterns(
            pattern_type=pattern_type,
            min_confidence=min_confidence,
        )
        
        return {
            "patterns": [p.to_dict() for p in patterns],
            "total": len(patterns),
        }
    except Exception as e:
        return {
            "patterns": [],
            "total": 0,
            "error": str(e),
        }
