"""Tests for server initialization, database setup, and lifecycle management."""

from spicedocs_mcp.server import init_database, get_connection
import spicedocs_mcp.server as server_module


def test_database_initialization(test_archive, tmp_path, monkeypatch):
    """Test that database is created and initialized correctly."""
    # Set cache directory to temp path for test isolation
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("SPICEDOCS_CACHE_DIR", str(cache_dir))

    db_path = cache_dir / ".archive_index.db"

    # Database shouldn't exist yet
    assert not db_path.exists()

    # Initialize database (sets db_path and fts_available globals)
    server_module.archive_path = test_archive
    init_database(test_archive)

    try:
        # Database file should now exist
        assert db_path.exists()

        # Get a connection using the thread-safe method
        with get_connection() as conn:
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
        # Cleanup global state
        server_module.db_path = None
        server_module.archive_path = None
        server_module.fts_available = False


def test_fts5_detection(test_archive, tmp_path, monkeypatch):
    """Test that FTS5 availability is detected correctly."""
    # Set cache directory to temp path for test isolation
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("SPICEDOCS_CACHE_DIR", str(cache_dir))

    server_module.archive_path = test_archive
    init_database(test_archive)

    try:
        # Check if FTS5 was detected (depends on SQLite version)
        fts_available = server_module.fts_available

        with get_connection() as conn:
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
        server_module.db_path = None
        server_module.archive_path = None
        server_module.fts_available = False


def test_index_building(test_archive, tmp_path, monkeypatch):
    """Test that index contains correct data for test files."""
    # Set cache directory to temp path for test isolation
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("SPICEDOCS_CACHE_DIR", str(cache_dir))

    server_module.archive_path = test_archive
    init_database(test_archive)

    try:
        with get_connection() as conn:
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
        server_module.db_path = None
        server_module.archive_path = None
        server_module.fts_available = False


def test_database_persistence(test_archive, tmp_path, monkeypatch):
    """Test that database persists and doesn't rebuild unnecessarily."""
    # Set cache directory to temp path for test isolation
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("SPICEDOCS_CACHE_DIR", str(cache_dir))

    # Initialize database first time
    server_module.archive_path = test_archive
    init_database(test_archive)

    with get_connection() as conn1:
        cursor = conn1.execute("SELECT COUNT(*) FROM pages")
        initial_count = cursor.fetchone()[0]

    # Reinitialize (should not rebuild since pages exist)
    init_database(test_archive)

    try:
        with get_connection() as conn2:
            # Should still have same number of pages (no rebuild)
            cursor = conn2.execute("SELECT COUNT(*) FROM pages")
            second_count = cursor.fetchone()[0]
            assert second_count == initial_count

    finally:
        server_module.db_path = None
        server_module.archive_path = None
        server_module.fts_available = False
