"""MCP (Model Context Protocol) server for CHIMERA.

Provides CHIMERA capabilities as an MCP server for Claude Desktop and other MCP clients.
"""

import json
from typing import Any

from chimera.correlation.engine import get_correlation_engine
from chimera.storage.catalog import CatalogDB
from chimera.storage.vectors import VectorDB
from chimera.extractors.embeddings import get_embedding_generator
from chimera.utils.logging import get_logger

logger = get_logger(__name__)


class ChimeraMCPServer:
    """MCP server implementation for CHIMERA.
    
    Exposes CHIMERA capabilities via MCP protocol:
    - search: Semantic search across indexed content
    - discoveries: Get surfaced discoveries
    - entities: Get consolidated entities
    - correlate: Trigger correlation analysis
    """
    
    def __init__(self) -> None:
        self.catalog = CatalogDB()
        self.vectors = VectorDB()
        self.embedder = get_embedding_generator()
    
    def get_tools(self) -> list[dict[str, Any]]:
        """Get available MCP tools."""
        return [
            {
                "name": "chimera_search",
                "description": "Search the user's local knowledge base using semantic search. Returns relevant content from indexed files.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 5)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "chimera_discoveries",
                "description": "Get automatically discovered patterns and insights from the user's files and AI conversations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Filter by discovery type (expertise, relationship, workflow, skill)",
                        },
                        "min_confidence": {
                            "type": "number",
                            "description": "Minimum confidence threshold (default: 0.7)",
                            "default": 0.7,
                        },
                    },
                },
            },
            {
                "name": "chimera_entities",
                "description": "Get consolidated entities (people, organizations, technologies) from indexed content.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Filter by entity type (PERSON, ORG, TECH, etc)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 20)",
                            "default": 20,
                        },
                    },
                },
            },
            {
                "name": "chimera_file",
                "description": "Get details about a specific indexed file.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "The file ID to retrieve",
                        },
                    },
                    "required": ["file_id"],
                },
            },
        ]
    
    async def handle_tool_call(
        self, 
        tool_name: str, 
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle an MCP tool call."""
        if tool_name == "chimera_search":
            return await self._handle_search(arguments)
        elif tool_name == "chimera_discoveries":
            return await self._handle_discoveries(arguments)
        elif tool_name == "chimera_entities":
            return await self._handle_entities(arguments)
        elif tool_name == "chimera_file":
            return await self._handle_file(arguments)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    async def _handle_search(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle chimera_search tool."""
        query = args.get("query", "")
        limit = args.get("limit", 5)
        
        if not query:
            return {"error": "Query is required"}
        
        try:
            query_embedding = self.embedder.embed(query)
            results = self.vectors.query(
                collection_name="documents",
                query_embedding=query_embedding,
                n_results=limit,
            )
            
            formatted = []
            if results and results.get("ids") and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    document = results["documents"][0][i] if results.get("documents") else ""
                    
                    formatted.append({
                        "similarity": round(1 - distance, 3),
                        "source": metadata.get("file_path", "unknown"),
                        "content": document[:1000],
                    })
            
            return {
                "query": query,
                "results": formatted,
                "count": len(formatted),
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_discoveries(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle chimera_discoveries tool."""
        discovery_type = args.get("type")
        min_confidence = args.get("min_confidence", 0.7)
        
        try:
            engine = get_correlation_engine()
            discoveries = engine.get_discoveries(
                discovery_type=discovery_type,
                min_confidence=min_confidence,
            )
            
            return {
                "discoveries": [d.to_dict() for d in discoveries],
                "count": len(discoveries),
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_entities(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle chimera_entities tool."""
        entity_type = args.get("type")
        limit = args.get("limit", 20)
        
        try:
            engine = get_correlation_engine()
            entities = engine.get_consolidated_entities(
                entity_type=entity_type,
                min_occurrences=2,
                limit=limit,
            )
            
            return {
                "entities": [e.to_dict() for e in entities],
                "count": len(entities),
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_file(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle chimera_file tool."""
        file_id = args.get("file_id")
        
        if not file_id:
            return {"error": "file_id is required"}
        
        try:
            file_record = self.catalog.get_file(file_id)
            
            if not file_record:
                return {"error": f"File not found: {file_id}"}
            
            chunks = self.catalog.get_chunks_for_file(file_id)
            entities = self.catalog.get_entities_for_file(file_id)
            
            return {
                "id": file_id,
                "path": file_record.path,
                "filename": file_record.filename,
                "status": file_record.status,
                "word_count": file_record.word_count,
                "chunk_count": len(chunks),
                "entity_count": len(entities),
                "entities": [
                    {"type": e.entity_type, "value": e.value}
                    for e in entities[:20]
                ],
            }
        except Exception as e:
            return {"error": str(e)}
    
    def to_mcp_manifest(self) -> dict[str, Any]:
        """Generate MCP manifest."""
        return {
            "name": "chimera",
            "version": "0.1.0",
            "description": "CHIMERA - Cognitive History Integration & Memory Extraction",
            "tools": self.get_tools(),
        }
