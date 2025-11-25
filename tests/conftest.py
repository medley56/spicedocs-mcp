"""Pytest configuration and shared fixtures for SpiceDocs MCP server tests."""

import pytest
from pathlib import Path
from tests.fixtures.test_data import build_minimal_archive
import spicedocs_mcp.server as server_module
from spicedocs_mcp.server import mcp, init_database


@pytest.fixture
def test_archive(tmp_path):
    """
    Create a minimal test documentation archive.

    Returns:
        Path: Path to the test archive directory
    """
    archive_dir = tmp_path / "test_archive"
    archive_dir.mkdir()

    # Build minimal archive with test HTML files
    build_minimal_archive(archive_dir)

    return archive_dir


@pytest.fixture
def initialized_server(test_archive):
    """
    Initialize server with test archive and set up global state.

    This fixture:
    - Sets global archive_path and db_conn
    - Initializes SQLite database with test data
    - Yields the FastMCP server instance
    - Cleans up global state after test

    Args:
        test_archive: Path to test archive (from test_archive fixture)

    Yields:
        FastMCP: The initialized MCP server instance
    """
    # Set global state required by current server implementation
    server_module.archive_path = test_archive
    server_module.db_conn = init_database(test_archive)

    yield mcp

    # Cleanup global state
    if server_module.db_conn:
        server_module.db_conn.close()
    server_module.db_conn = None
    server_module.archive_path = None
    server_module.fts_available = False


@pytest.fixture
async def client(initialized_server):
    """
    Create FastMCP test client connected to initialized server.

    This uses FastMCP's in-memory testing approach for fast, deterministic tests.

    Args:
        initialized_server: Initialized MCP server instance

    Yields:
        Client: FastMCP client instance for making tool calls
    """
    from fastmcp import Client

    async with Client(initialized_server) as client:
        yield client
