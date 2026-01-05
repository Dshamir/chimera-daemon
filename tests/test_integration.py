"""Tests for integration modules."""

import pytest
from pathlib import Path

from chimera.integration.claude import ClaudeContextBuilder, ClaudeContext, ContextChunk
from chimera.integration.mcp import ChimeraMCPServer


def test_context_chunk():
    """Test ContextChunk dataclass."""
    chunk = ContextChunk(
        content="Test content",
        source="/path/to/file.md",
        similarity=0.85,
        chunk_type="paragraph",
    )
    
    assert chunk.content == "Test content"
    assert chunk.similarity == 0.85


def test_claude_context_to_xml():
    """Test ClaudeContext XML generation."""
    context = ClaudeContext(
        query="What is CHIMERA?",
        chunks=[
            ContextChunk(
                content="CHIMERA is a cognitive archaeology daemon.",
                source="/docs/readme.md",
                similarity=0.92,
                chunk_type="paragraph",
            ),
        ],
        discoveries=[
            {
                "discovery_type": "expertise",
                "confidence": 0.85,
                "title": "Python Expert",
                "description": "Strong Python expertise detected",
            },
        ],
    )
    
    xml = context.to_xml()
    
    assert "<chimera_context>" in xml
    assert "<query>What is CHIMERA?</query>" in xml
    assert "<chunk index=\"1\"" in xml
    assert "CHIMERA is a cognitive archaeology daemon." in xml
    assert "<discovery type=\"expertise\"" in xml
    assert "</chimera_context>" in xml


def test_claude_context_to_markdown():
    """Test ClaudeContext Markdown generation."""
    context = ClaudeContext(
        query="Test query",
        chunks=[
            ContextChunk(
                content="Some content here",
                source="/path/file.md",
                similarity=0.75,
                chunk_type="paragraph",
            ),
        ],
    )
    
    md = context.to_markdown()
    
    assert "## CHIMERA Context: Test query" in md
    assert "### Relevant Content" in md
    assert "Some content here" in md


def test_mcp_server_tools():
    """Test MCP server tool definitions."""
    server = ChimeraMCPServer()
    tools = server.get_tools()
    
    assert len(tools) == 4
    
    tool_names = [t["name"] for t in tools]
    assert "chimera_search" in tool_names
    assert "chimera_discoveries" in tool_names
    assert "chimera_entities" in tool_names
    assert "chimera_file" in tool_names
    
    # Check search tool schema
    search_tool = next(t for t in tools if t["name"] == "chimera_search")
    assert "query" in search_tool["inputSchema"]["properties"]
    assert "query" in search_tool["inputSchema"]["required"]


def test_mcp_server_manifest():
    """Test MCP manifest generation."""
    server = ChimeraMCPServer()
    manifest = server.to_mcp_manifest()
    
    assert manifest["name"] == "chimera"
    assert manifest["version"] == "0.1.0"
    assert len(manifest["tools"]) == 4


@pytest.mark.asyncio
async def test_mcp_unknown_tool():
    """Test MCP handling of unknown tool."""
    server = ChimeraMCPServer()
    result = await server.handle_tool_call("unknown_tool", {})
    
    assert "error" in result
    assert "Unknown tool" in result["error"]


@pytest.mark.asyncio
async def test_mcp_search_empty_query():
    """Test MCP search with empty query."""
    server = ChimeraMCPServer()
    result = await server.handle_tool_call("chimera_search", {"query": ""})
    
    assert "error" in result
    assert "Query is required" in result["error"]


@pytest.mark.asyncio
async def test_mcp_file_missing_id():
    """Test MCP file retrieval with missing ID."""
    server = ChimeraMCPServer()
    result = await server.handle_tool_call("chimera_file", {})
    
    assert "error" in result
    assert "file_id is required" in result["error"]
