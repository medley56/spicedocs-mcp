"""Tests for thread safety and concurrent database access."""

import asyncio

import pytest

from spicedocs_mcp.server import get_connection, init_database
import spicedocs_mcp.server as server_module


async def test_concurrent_searches(client):
    """Test that multiple concurrent search operations work correctly."""
    # Run 10 concurrent searches
    queries = ["ephemeris", "kernel", "SPICE", "time", "documentation"]
    
    async def search(query: str):
        result = await client.call_tool("search_archive", {"query": query, "limit": 5})
        return result.content[0].text
    
    # Execute all searches concurrently
    results = await asyncio.gather(*[search(q) for q in queries])
    
    # All searches should complete without errors (either find results or report "No results")
    for i, result in enumerate(results):
        has_error = "Error" in result and "No results" not in result
        assert not has_error, f"Search '{queries[i]}' returned unexpected error: {result}"


async def test_concurrent_get_page(client):
    """Test that multiple concurrent page retrievals work correctly."""
    # Pages to retrieve concurrently
    paths = [
        "index.html",
        "page_kernels.html",
        "page_time.html",
        "subdir/nested.html",
        "subdir/deep/deeper.html",
    ]
    
    async def get_page(path: str):
        result = await client.call_tool("get_page", {"path": path})
        return result.content[0].text
    
    # Execute all retrievals concurrently
    results = await asyncio.gather(*[get_page(p) for p in paths])
    
    # All retrievals should succeed
    for i, result in enumerate(results):
        assert "Error" not in result, f"get_page '{paths[i]}' failed: {result}"
        assert paths[i] in result, f"Path not found in result for {paths[i]}"


async def test_concurrent_list_pages(client):
    """Test that multiple concurrent list_pages operations work correctly."""
    # Different filter patterns to test concurrently
    patterns = [
        None,  # No filter
        "*.html",
        "page_*.html",
        "subdir/*",
    ]
    
    async def list_with_pattern(pattern):
        args = {"limit": 10}
        if pattern:
            args["filter_pattern"] = pattern
        result = await client.call_tool("list_pages", args)
        return result.content[0].text
    
    # Execute all list operations concurrently
    results = await asyncio.gather(*[list_with_pattern(p) for p in patterns])
    
    # All operations should complete without errors
    for i, result in enumerate(results):
        assert "Error" not in result, f"list_pages with pattern '{patterns[i]}' failed"


async def test_concurrent_mixed_operations(client):
    """Test concurrent execution of different MCP tools."""
    async def search_op():
        return await client.call_tool("search_archive", {"query": "kernel", "limit": 3})
    
    async def get_page_op():
        return await client.call_tool("get_page", {"path": "index.html"})
    
    async def list_pages_op():
        return await client.call_tool("list_pages", {"limit": 5})
    
    async def extract_links_op():
        return await client.call_tool("extract_links", {"path": "page_links.html"})
    
    async def get_stats_op():
        return await client.call_tool("get_archive_stats", {})
    
    # Run all operations multiple times concurrently
    tasks = []
    for _ in range(3):  # Run each operation 3 times
        tasks.extend([
            search_op(),
            get_page_op(),
            list_pages_op(),
            extract_links_op(),
            get_stats_op(),
        ])
    
    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks)
    
    # All operations should succeed (no unexpected errors)
    for i, result in enumerate(results):
        content = result.content[0].text
        has_error = "Error" in content and "No results" not in content
        assert not has_error, f"Task {i} returned unexpected error: {content}"


async def test_rapid_successive_searches(client):
    """Test rapid successive searches don't cause connection issues."""
    query = "kernel"
    
    # Perform 20 rapid searches
    for i in range(20):
        result = await client.call_tool("search_archive", {"query": query, "limit": 5})
        content = result.content[0].text
        # Should either find results or report no results (not error)
        has_error = "Error" in content and "No results" not in content
        assert not has_error, f"Search {i} returned unexpected error: {content}"


def test_get_connection_returns_unique_connections(test_archive, tmp_path, monkeypatch):
    """Test that get_connection() returns unique connections."""
    # Set cache directory to temp path for test isolation
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("SPICEDOCS_CACHE_DIR", str(cache_dir))

    server_module.archive_path = test_archive
    init_database(test_archive)
    
    try:
        # Get multiple connections
        conn1 = get_connection()
        conn2 = get_connection()
        conn3 = get_connection()
        
        try:
            # Each should be a valid but distinct connection
            assert conn1 is not conn2
            assert conn2 is not conn3
            assert conn1 is not conn3
            
            # All should be able to query the database independently
            cursor1 = conn1.execute("SELECT COUNT(*) FROM pages")
            cursor2 = conn2.execute("SELECT COUNT(*) FROM pages")
            cursor3 = conn3.execute("SELECT COUNT(*) FROM pages")
            
            count1 = cursor1.fetchone()[0]
            count2 = cursor2.fetchone()[0]
            count3 = cursor3.fetchone()[0]
            
            # All should return the same count
            assert count1 == count2 == count3 == 6
            
        finally:
            conn1.close()
            conn2.close()
            conn3.close()
    
    finally:
        server_module.db_path = None
        server_module.archive_path = None
        server_module.fts_available = False


def test_connection_context_manager(test_archive, tmp_path, monkeypatch):
    """Test that connections work properly with context managers."""
    # Set cache directory to temp path for test isolation
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("SPICEDOCS_CACHE_DIR", str(cache_dir))

    server_module.archive_path = test_archive
    init_database(test_archive)
    
    try:
        # Use connection with context manager
        with get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM pages")
            count = cursor.fetchone()[0]
            assert count == 6
        
        # Connection should be closed after context manager exits
        # A new connection should work fine
        with get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM pages")
            count = cursor.fetchone()[0]
            assert count == 6
    
    finally:
        server_module.db_path = None
        server_module.archive_path = None
        server_module.fts_available = False


def test_db_path_not_initialized_raises_error():
    """Test that get_connection raises error when db_path is not set."""
    # Ensure db_path is None
    original_db_path = server_module.db_path
    server_module.db_path = None
    
    try:
        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_connection()
    finally:
        server_module.db_path = original_db_path
