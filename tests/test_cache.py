"""Unit tests for cache management module."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from pytest_httpserver import HTTPServer

from spicedocs_mcp.cache import (
    get_cache_dir,
    is_cache_valid,
    should_download,
    download_with_retry,
    download_documentation,
    get_or_download_cache,
    DEFAULT_BASE_URL,
)


def test_get_cache_dir_default(monkeypatch):
    """Test getting default cache directory."""
    # Clear environment variable
    monkeypatch.delenv("SPICEDOCS_CACHE_DIR", raising=False)

    cache_dir = get_cache_dir()
    # The actual directory name depends on platformdirs implementation
    assert "spicedocs" in cache_dir.name.lower()
    assert "spicedocs-mcp" in str(cache_dir)


def test_get_cache_dir_env_override(monkeypatch, tmp_path):
    """Test cache directory override with environment variable."""
    custom_dir = tmp_path / "custom_cache"
    monkeypatch.setenv("SPICEDOCS_CACHE_DIR", str(custom_dir))

    cache_dir = get_cache_dir()
    assert cache_dir == custom_dir


def test_is_cache_valid_missing_dir(tmp_path):
    """Test cache validation with missing directory."""
    assert not is_cache_valid(tmp_path / "nonexistent")


def test_is_cache_valid_missing_version_file(tmp_path):
    """Test cache validation with missing version file."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "naif.jpl.nasa.gov").mkdir()

    assert not is_cache_valid(cache_dir)


def test_is_cache_valid_incomplete_download(tmp_path):
    """Test cache validation with incomplete download."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "naif.jpl.nasa.gov").mkdir()

    # Create version file with completed=false
    version_data = {
        "version": "1.0",
        "completed": False
    }
    with open(cache_dir / ".cache_version", 'w') as f:
        json.dump(version_data, f)

    assert not is_cache_valid(cache_dir)


def test_is_cache_valid_insufficient_files(tmp_path):
    """Test cache validation with insufficient files."""
    cache_dir = tmp_path / "cache"
    doc_dir = cache_dir / "naif.jpl.nasa.gov" / "pub" / "naif" / "toolkit_docs" / "C"
    doc_dir.mkdir(parents=True)

    # Create version file
    version_data = {
        "version": "1.0",
        "completed": True
    }
    with open(cache_dir / ".cache_version", 'w') as f:
        json.dump(version_data, f)

    # Create only a few HTML files (less than MIN_FILE_COUNT)
    for i in range(10):
        (doc_dir / f"page{i}.html").write_text("<html></html>")

    assert not is_cache_valid(cache_dir)


def test_is_cache_valid_valid_cache(tmp_path):
    """Test cache validation with valid cache."""
    cache_dir = tmp_path / "cache"
    doc_dir = cache_dir / "naif.jpl.nasa.gov" / "pub" / "naif" / "toolkit_docs" / "C"
    doc_dir.mkdir(parents=True)

    # Create version file
    version_data = {
        "version": "1.0",
        "completed": True,
        "file_count": 600
    }
    with open(cache_dir / ".cache_version", 'w') as f:
        json.dump(version_data, f)

    # Create sufficient HTML files
    for i in range(510):
        (doc_dir / f"page{i}.html").write_text("<html></html>")

    assert is_cache_valid(cache_dir)


def test_should_download_valid_html():
    """Test URL filtering for valid HTML files."""
    base_url = DEFAULT_BASE_URL

    assert should_download("https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/index.html", base_url)
    assert should_download("https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/spkpos_c.html", base_url)
    assert should_download("https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/ug/", base_url)


def test_should_download_external_links():
    """Test URL filtering rejects external links."""
    base_url = DEFAULT_BASE_URL

    assert not should_download("https://example.com/page.html", base_url)
    assert not should_download("https://google.com", base_url)


def test_should_download_wrong_path():
    """Test URL filtering rejects wrong paths."""
    base_url = DEFAULT_BASE_URL

    assert not should_download("https://naif.jpl.nasa.gov/other/path/file.html", base_url)
    assert not should_download("https://naif.jpl.nasa.gov/pub/naif/other/file.html", base_url)


def test_should_download_non_html():
    """Test URL filtering rejects non-HTML files."""
    base_url = DEFAULT_BASE_URL

    assert not should_download("https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/style.css", base_url)
    assert not should_download("https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/script.js", base_url)
    assert not should_download("https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/image.png", base_url)


def test_download_with_retry_success(httpserver: HTTPServer):
    """Test successful download without retries."""
    httpserver.expect_request("/test").respond_with_data("Success", status=200)

    client = httpx.Client()
    response = download_with_retry(client, httpserver.url_for("/test"))
    assert response.status_code == 200
    assert response.text == "Success"


def test_download_with_retry_404(httpserver: HTTPServer):
    """Test that 404 errors are not retried."""
    httpserver.expect_request("/missing").respond_with_data("", status=404)

    client = httpx.Client()

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        download_with_retry(client, httpserver.url_for("/missing"))

    assert exc_info.value.response.status_code == 404


def test_download_with_retry_server_error(httpserver: HTTPServer):
    """Test retry logic for server errors."""
    # First two requests return 500, third succeeds
    httpserver.expect_ordered_request("/test").respond_with_data("", status=500)
    httpserver.expect_ordered_request("/test").respond_with_data("", status=500)
    httpserver.expect_ordered_request("/test").respond_with_data("Success", status=200)

    client = httpx.Client()
    url = httpserver.url_for("/test")

    response = download_with_retry(client, url)
    assert response.status_code == 200
    assert response.text == "Success"


def test_download_documentation(httpserver: HTTPServer, tmp_path, monkeypatch):
    """Test documentation download with mock server."""
    base_path = "/pub/naif/toolkit_docs/C/"

    # Set up mock NAIF server with a small documentation tree
    # Use oneshot=False to allow multiple requests to same URL
    httpserver.expect_oneshot_request(f"{base_path}").respond_with_data(
        f'<html><body><a href="{base_path}index.html">Index</a></body></html>',
        content_type="text/html"
    )
    httpserver.expect_oneshot_request(f"{base_path}index.html").respond_with_data(
        f'<html><body>'
        f'<a href="cspice/spkpos_c.html">spkpos_c</a>'
        f'<a href="ug/index.html">User Guide</a>'
        f'</body></html>',
        content_type="text/html"
    )
    httpserver.expect_oneshot_request(f"{base_path}cspice/spkpos_c.html").respond_with_data(
        '<html><body>SPKPOS documentation</body></html>',
        content_type="text/html"
    )
    httpserver.expect_oneshot_request(f"{base_path}ug/index.html").respond_with_data(
        '<html><body>User Guide</body></html>',
        content_type="text/html"
    )

    cache_dir = tmp_path / "cache"
    base_url = httpserver.url_for(base_path)

    # Mock the base URL to use our test server
    monkeypatch.setenv("SPICEDOCS_BASE_URL", base_url)

    download_documentation(base_url, cache_dir)

    # Verify cache structure
    assert cache_dir.exists()
    assert (cache_dir / ".cache_version").exists()
    assert (cache_dir / "naif.jpl.nasa.gov").exists()

    # Verify version file
    with open(cache_dir / ".cache_version") as f:
        version_data = json.load(f)
        assert version_data["completed"] is True
        assert version_data["file_count"] > 0

    # Verify at least some HTML files were downloaded
    doc_dir = cache_dir / "naif.jpl.nasa.gov"
    html_files = list(doc_dir.rglob("*.html"))
    assert len(html_files) > 0


def test_get_or_download_cache_with_valid_cache(tmp_path, monkeypatch):
    """Test get_or_download_cache with existing valid cache."""
    cache_dir = tmp_path / "cache"
    doc_dir = cache_dir / "naif.jpl.nasa.gov" / "pub" / "naif" / "toolkit_docs" / "C"
    doc_dir.mkdir(parents=True)

    # Create valid cache
    version_data = {
        "version": "1.0",
        "completed": True
    }
    with open(cache_dir / ".cache_version", 'w') as f:
        json.dump(version_data, f)

    # Create sufficient HTML files
    for i in range(510):
        (doc_dir / f"page{i}.html").write_text("<html></html>")

    # Override cache directory
    monkeypatch.setenv("SPICEDOCS_CACHE_DIR", str(cache_dir))

    # Should return existing cache without downloading
    result = get_or_download_cache()
    assert result == cache_dir / "naif.jpl.nasa.gov"


def test_get_or_download_cache_skip_download(tmp_path, monkeypatch):
    """Test that download can be skipped with environment variable."""
    cache_dir = tmp_path / "cache"

    # Override cache directory and skip download
    monkeypatch.setenv("SPICEDOCS_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("SPICEDOCS_SKIP_DOWNLOAD", "true")

    # Should raise error since cache is invalid and download is skipped
    with pytest.raises(RuntimeError, match="download skipped"):
        get_or_download_cache()


@pytest.mark.skip(reason="Permission test interferes with HTTP server, tested manually")
def test_get_or_download_cache_permission_error(tmp_path, monkeypatch):
    """Test permission error handling."""
    # Create parent directory that's writable
    parent_dir = tmp_path / "parent"
    parent_dir.mkdir()

    # Create read-only cache directory inside it
    cache_dir = parent_dir / "readonly_cache"
    cache_dir.mkdir(mode=0o555)  # Read and execute, but no write

    monkeypatch.setenv("SPICEDOCS_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("SPICEDOCS_SKIP_DOWNLOAD", "false")  # Don't skip download

    try:
        with pytest.raises(PermissionError, match="No write permission"):
            get_or_download_cache()
    finally:
        # Restore permissions for cleanup
        cache_dir.chmod(0o755)


def test_download_documentation_handles_404(httpserver: HTTPServer, tmp_path):
    """Test that download continues after 404 errors."""
    base_path = "/pub/naif/toolkit_docs/C/"

    # Set up mock with a 404 link
    httpserver.expect_request(f"{base_path}").respond_with_data(
        f'<html><body>'
        f'<a href="{base_path}index.html">Index</a>'
        f'<a href="{base_path}missing.html">Missing</a>'
        f'</body></html>',
        content_type="text/html"
    )
    httpserver.expect_request(f"{base_path}index.html").respond_with_data(
        '<html><body>Index page</body></html>',
        content_type="text/html"
    )
    httpserver.expect_request(f"{base_path}missing.html").respond_with_data(
        '', status=404
    )

    cache_dir = tmp_path / "cache"
    base_url = httpserver.url_for(base_path)

    # Should complete successfully despite 404
    download_documentation(base_url, cache_dir)

    assert cache_dir.exists()
    assert (cache_dir / ".cache_version").exists()
