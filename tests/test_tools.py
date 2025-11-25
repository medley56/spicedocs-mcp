"""Integration tests for all 5 MCP tools."""

import pytest


# ============================================================================
# search_archive tool tests
# ============================================================================


async def test_search_archive_basic(client):
    """Test basic search with results."""
    result = await client.call_tool("search_archive", {
        "query": "ephemeris",
        "limit": 5
    })

    assert len(result.content) > 0
    content = result.content[0].text

    # Should find results
    assert "Found" in content
    assert "ephemeris" in content.lower()
    assert "page_time.html" in content or "Time Systems" in content


async def test_search_archive_no_results(client):
    """Test search with no matching results."""
    result = await client.call_tool("search_archive", {
        "query": "nonexistent_keyword_xyz_12345"
    })

    content = result.content[0].text
    assert "No results found" in content


async def test_search_archive_limit(client):
    """Test that limit parameter is respected."""
    result = await client.call_tool("search_archive", {
        "query": "SPICE",
        "limit": 2
    })

    content = result.content[0].text

    # Check that we got results but limited
    if "Found" in content:
        # Count the number of result entries (each has a number prefix like "1.")
        result_count = sum(1 for line in content.split('\n') if line.strip().startswith(('1.', '2.', '3.')))
        assert result_count <= 2


async def test_search_archive_multiple_keywords(client):
    """Test search with multiple keywords."""
    result = await client.call_tool("search_archive", {
        "query": "kernel SPK"
    })

    content = result.content[0].text
    # Should find page about kernels
    assert "Found" in content or "results" in content.lower()


# ============================================================================
# get_page tool tests
# ============================================================================


async def test_get_page_valid(client):
    """Test retrieving a valid page."""
    result = await client.call_tool("get_page", {
        "path": "index.html"
    })

    content = result.content[0].text

    assert "SPICE Documentation Index" in content
    assert "Welcome to the SPICE toolkit documentation" in content
    assert "index.html" in content


async def test_get_page_nested(client):
    """Test retrieving a page in a subdirectory."""
    result = await client.call_tool("get_page", {
        "path": "subdir/nested.html"
    })

    content = result.content[0].text

    assert "Nested Page" in content
    assert "subdir/nested.html" in content


async def test_get_page_deep_nested(client):
    """Test retrieving a deeply nested page."""
    result = await client.call_tool("get_page", {
        "path": "subdir/deep/deeper.html"
    })

    content = result.content[0].text

    assert "Deeply Nested Page" in content
    assert "subdir/deep/deeper.html" in content


async def test_get_page_not_found(client):
    """Test retrieving a non-existent page."""
    result = await client.call_tool("get_page", {
        "path": "does_not_exist.html"
    })

    content = result.content[0].text
    assert "Error" in content
    assert "not found" in content.lower()


async def test_get_page_with_raw_html(client):
    """Test retrieving page with raw HTML included."""
    result = await client.call_tool("get_page", {
        "path": "index.html",
        "include_raw": True
    })

    content = result.content[0].text

    # Should have both parsed content and raw HTML
    assert "SPICE Documentation Index" in content
    assert "Raw HTML" in content
    assert "<!DOCTYPE html>" in content or "<html>" in content


# ============================================================================
# list_pages tool tests
# ============================================================================


async def test_list_pages_all(client):
    """Test listing all pages without filter."""
    result = await client.call_tool("list_pages", {})

    content = result.content[0].text

    # Should list all 6 test pages
    assert "6 pages" in content or "contains 6" in content.lower()
    assert "index.html" in content
    assert "page_kernels.html" in content


async def test_list_pages_with_glob_filter(client):
    """Test listing pages with GLOB pattern filter."""
    result = await client.call_tool("list_pages", {
        "filter_pattern": "page_*.html"
    })

    content = result.content[0].text

    # Should only list pages matching pattern
    assert "page_kernels.html" in content
    assert "page_time.html" in content
    assert "page_links.html" in content
    # Should NOT include index or subdir pages
    assert "3 pages" in content or "contains 3" in content.lower()


async def test_list_pages_with_subdir_filter(client):
    """Test listing pages in subdirectory."""
    result = await client.call_tool("list_pages", {
        "filter_pattern": "subdir/*"
    })

    content = result.content[0].text

    # Should only list pages in subdir (not deep nested ones with this pattern)
    assert "subdir/nested.html" in content


async def test_list_pages_with_limit(client):
    """Test that limit parameter is respected."""
    result = await client.call_tool("list_pages", {
        "limit": 2
    })

    content = result.content[0].text

    # Should return at most 2 pages
    lines = content.split('\n')
    page_mentions = sum(1 for line in lines if '.html' in line and 'Path:' in line)
    assert page_mentions <= 2


# ============================================================================
# extract_links tool tests
# ============================================================================


async def test_extract_links_internal_only(client):
    """Test extracting only internal links from a page."""
    result = await client.call_tool("extract_links", {
        "path": "page_links.html",
        "internal_only": True
    })

    content = result.content[0].text

    # Should have internal links
    assert "index.html" in content
    assert "page_kernels.html" in content

    # Should NOT have external links
    assert "example.com" not in content
    assert "naif.jpl.nasa.gov" not in content


async def test_extract_links_all(client):
    """Test extracting all links including external."""
    result = await client.call_tool("extract_links", {
        "path": "page_links.html",
        "internal_only": False
    })

    content = result.content[0].text

    # Should have both internal and external links
    assert "index.html" in content
    assert "example.com" in content or "naif.jpl.nasa.gov" in content


async def test_extract_links_relative_paths(client):
    """Test that relative links from nested pages are extracted."""
    result = await client.call_tool("extract_links", {
        "path": "subdir/nested.html",
        "internal_only": True
    })

    content = result.content[0].text

    # Should have relative links
    assert "../index.html" in content or "index.html" in content


async def test_extract_links_deeply_nested(client):
    """Test link extraction from deeply nested page."""
    result = await client.call_tool("extract_links", {
        "path": "subdir/deep/deeper.html",
        "internal_only": True
    })

    content = result.content[0].text

    # Should resolve relative paths
    assert "../../index.html" in content or "index.html" in content


async def test_extract_links_page_not_found(client):
    """Test link extraction from non-existent page."""
    result = await client.call_tool("extract_links", {
        "path": "does_not_exist.html"
    })

    content = result.content[0].text
    assert "Error" in content
    assert "not found" in content.lower()


# ============================================================================
# get_archive_stats tool tests
# ============================================================================


async def test_get_archive_stats(client):
    """Test basic archive statistics."""
    result = await client.call_tool("get_archive_stats", {})

    content = result.content[0].text

    # Should report stats
    assert "Archive Statistics" in content
    assert "6" in content  # Should have 6 pages
    assert "Indexed Pages" in content
    assert "Search Type" in content


async def test_get_archive_stats_fts_reporting(client):
    """Test that FTS5 availability is reported correctly."""
    result = await client.call_tool("get_archive_stats", {})

    content = result.content[0].text

    # Should report search type (either FTS5 or Basic)
    assert "Full-text search (FTS5)" in content or "Basic search" in content


async def test_get_archive_stats_file_counting(client):
    """Test that file counts are accurate."""
    result = await client.call_tool("get_archive_stats", {})

    content = result.content[0].text

    # Verify total files count
    assert "Total Files:" in content
    # Should be 6 HTML files + possibly database file
    assert any(count in content for count in ["6", "7"])  # 6 HTML or 7 with .db


async def test_get_archive_stats_size_reporting(client):
    """Test that archive size is reported."""
    result = await client.call_tool("get_archive_stats", {})

    content = result.content[0].text

    # Should report total size
    assert "Total Size:" in content
    assert "MB" in content or "KB" in content
