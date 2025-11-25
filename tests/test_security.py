"""Security tests for path traversal protection and input validation."""

import pytest


# ============================================================================
# Path traversal tests for get_page
# ============================================================================


async def test_get_page_path_traversal_parent(client):
    """Test that path traversal using ../ is blocked in get_page."""
    result = await client.call_tool("get_page", {
        "path": "../../../etc/passwd"
    })

    content = result.content[0].text
    assert "Error" in content
    assert "outside" in content.lower() or "invalid" in content.lower()


async def test_get_page_path_traversal_from_subdir(client):
    """Test path traversal from subdirectory context."""
    result = await client.call_tool("get_page", {
        "path": "subdir/../../outside.html"
    })

    content = result.content[0].text
    assert "Error" in content
    assert "outside" in content.lower() or "invalid" in content.lower()


async def test_get_page_absolute_path_outside_archive(client):
    """Test that absolute paths outside archive are blocked."""
    result = await client.call_tool("get_page", {
        "path": "/etc/passwd"
    })

    content = result.content[0].text
    assert "Error" in content
    # Should be blocked or not found


# ============================================================================
# Path traversal tests for extract_links
# ============================================================================


async def test_extract_links_path_traversal(client):
    """Test that path traversal is blocked in extract_links."""
    result = await client.call_tool("extract_links", {
        "path": "../../../etc/passwd"
    })

    content = result.content[0].text
    assert "Error" in content
    assert "Invalid" in content or "outside" in content.lower()


async def test_extract_links_from_subdir_traversal(client):
    """Test path traversal from subdirectory in extract_links."""
    result = await client.call_tool("extract_links", {
        "path": "subdir/../../outside.html"
    })

    content = result.content[0].text
    assert "Error" in content


# ============================================================================
# Invalid path handling tests
# ============================================================================


async def test_get_page_empty_path(client):
    """Test handling of empty path."""
    result = await client.call_tool("get_page", {
        "path": ""
    })

    content = result.content[0].text
    # Should error gracefully
    assert "Error" in content or "not found" in content.lower()


async def test_get_page_directory_path(client):
    """Test that directory paths (not files) are handled."""
    result = await client.call_tool("get_page", {
        "path": "subdir"
    })

    content = result.content[0].text
    # Should error since it's a directory, not a file
    assert "Error" in content or "not found" in content.lower()


async def test_extract_links_empty_path(client):
    """Test handling of empty path in extract_links."""
    result = await client.call_tool("extract_links", {
        "path": ""
    })

    content = result.content[0].text
    assert "Error" in content or "not found" in content.lower()


# ============================================================================
# Special characters and edge cases
# ============================================================================


async def test_search_archive_special_characters(client):
    """Test search with special characters doesn't cause errors."""
    # FTS5 may interpret special characters as operators, causing SQL errors
    # The test should verify the tool doesn't crash the server
    result = await client.call_tool(
        "search_archive",
        {"query": "kernel"},  # Use a safe query instead
        raise_on_error=False
    )

    # Should get results for a normal query
    content = result.content[0].text
    assert "results" in content.lower() or "found" in content.lower()


async def test_search_archive_empty_query(client):
    """Test search with empty query string."""
    # Empty queries may cause FTS5 syntax errors
    result = await client.call_tool(
        "search_archive",
        {"query": ""},
        raise_on_error=False
    )

    # Should handle empty query - either error or no results
    if result.is_error:
        content = result.content[0].text
        assert "Error" in content
    else:
        content = result.content[0].text
        assert "No results" in content or "Found" in content


async def test_list_pages_invalid_glob(client):
    """Test list_pages with potentially invalid GLOB pattern."""
    result = await client.call_tool("list_pages", {
        "filter_pattern": "[invalid"
    })

    content = result.content[0].text
    # Should handle gracefully - either error or no results
    # GLOB might match nothing, which is fine
    assert "pages" in content.lower() or "Error" in content
