"""Tests for server initialization, database setup, and lifecycle management."""

import sqlite3
from pathlib import Path
from spicedocs_mcp.server import init_database
import spicedocs_mcp.server as server_module


def test_database_initialization(test_archive):
    """Test that database is created and initialized correctly."""
    db_path = test_archive / ".archive_index.db"

    # Database shouldn't exist yet
    assert not db_path.exists()

    # Initialize database
    conn = init_database(test_archive)

    try:
        # Database file should now exist
        assert db_path.exists()

        # Check that pages table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pages'"
        )
        assert cursor.fetchone() is not None

        # Check that pages were indexed
        cursor = conn.execute("SELECT COUNT(*) FROM pages")
        page_count = cursor.fetchone()[0]
        assert page_count == 6  # Should have 6 test HTML files

    finally:
        conn.close()


def test_fts5_detection(test_archive):
    """Test that FTS5 availability is detected correctly."""
    conn = init_database(test_archive)

    try:
        # Check if FTS5 was detected (depends on SQLite version)
        fts_available = server_module.fts_available

        if fts_available:
            # If FTS5 is available, the virtual table should exist
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pages_fts'"
            )
            assert cursor.fetchone() is not None
        else:
            # If FTS5 is not available, we should still have the base table
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pages'"
            )
            assert cursor.fetchone() is not None

    finally:
        conn.close()
        server_module.fts_available = False


def test_index_building(test_archive):
    """Test that index contains correct data for test files."""
    conn = init_database(test_archive)

    try:
        # Query all indexed pages
        cursor = conn.execute("SELECT path, title, content FROM pages ORDER BY path")
        pages = cursor.fetchall()

        # Should have all 6 test pages
        assert len(pages) == 6

        # Check that specific pages are indexed correctly
        paths = {page[0] for page in pages}
        expected_paths = {
            "index.html",
            "page_kernels.html",
            "page_time.html",
            "page_links.html",
            "subdir/nested.html",
            "subdir/deep/deeper.html",
        }
        assert paths == expected_paths

        # Check that content was extracted (look for a specific page)
        cursor = conn.execute(
            "SELECT title, content FROM pages WHERE path = 'page_kernels.html'"
        )
        title, content = cursor.fetchone()

        assert "Kernels" in title
        assert "SPK" in content or "kernel" in content.lower()

    finally:
        conn.close()


def test_database_persistence(test_archive):
    """Test that database persists and doesn't rebuild unnecessarily."""
    # Initialize database first time
    conn1 = init_database(test_archive)
    cursor = conn1.execute("SELECT COUNT(*) FROM pages")
    initial_count = cursor.fetchone()[0]
    conn1.close()

    # Close and reinitialize
    conn2 = init_database(test_archive)

    try:
        # Should still have same number of pages (no rebuild)
        cursor = conn2.execute("SELECT COUNT(*) FROM pages")
        second_count = cursor.fetchone()[0]
        assert second_count == initial_count

    finally:
        conn2.close()
