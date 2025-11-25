"""Cache management and documentation download for SpiceDocs MCP."""

import json
import logging
import os
import shutil
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from platformdirs import user_cache_dir

logger = logging.getLogger("spicedocs-mcp.cache")

DEFAULT_BASE_URL = "https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/"
CACHE_VERSION = "1.0"
MIN_FILE_COUNT = 500  # Sanity check: expect at least 500 HTML files


def get_cache_dir() -> Path:
    """
    Get platform-appropriate cache directory.

    Returns platform-specific cache directory:
    - Linux: ~/.cache/spicedocs-mcp
    - macOS: ~/Library/Caches/spicedocs-mcp
    - Windows: %LOCALAPPDATA%\\spicedocs\\spicedocs-mcp\\Cache

    Can be overridden with SPICEDOCS_CACHE_DIR environment variable.
    """
    cache_base = os.environ.get("SPICEDOCS_CACHE_DIR")
    if cache_base:
        return Path(cache_base)
    return Path(user_cache_dir("spicedocs-mcp", "spicedocs"))


def is_cache_valid(cache_dir: Path) -> bool:
    """
    Check if cache is complete and valid.

    Validation checks:
    1. .cache_version file exists
    2. JSON is valid and has "completed": true
    3. At least MIN_FILE_COUNT .html files exist
    4. naif.jpl.nasa.gov directory exists

    Args:
        cache_dir: Cache directory to validate

    Returns:
        True if cache is valid, False otherwise
    """
    version_file = cache_dir / ".cache_version"

    # Check version file exists
    if not version_file.exists():
        logger.debug(f"Cache version file not found: {version_file}")
        return False

    # Validate version file JSON
    try:
        with open(version_file, 'r') as f:
            version_data = json.load(f)

        if not version_data.get("completed", False):
            logger.debug("Cache download not completed")
            return False

    except (json.JSONDecodeError, IOError) as e:
        logger.debug(f"Failed to read cache version file: {e}")
        return False

    # Check documentation directory exists
    doc_dir = cache_dir / "naif.jpl.nasa.gov"
    if not doc_dir.exists():
        logger.debug(f"Documentation directory not found: {doc_dir}")
        return False

    # Count HTML files
    html_files = list(doc_dir.rglob("*.html"))
    file_count = len(html_files)

    if file_count < MIN_FILE_COUNT:
        logger.debug(f"Insufficient HTML files: {file_count} < {MIN_FILE_COUNT}")
        return False

    logger.debug(f"Cache is valid with {file_count} HTML files")
    return True


def should_download(url: str, base_url: str) -> bool:
    """
    Filter URLs to determine if they should be downloaded.

    Rules:
    - Must be same domain (naif.jpl.nasa.gov)
    - Must be under /pub/naif/toolkit_docs/C/ path
    - Must be .html file or directory index
    - No external links, mailto:, javascript:, etc.

    Args:
        url: URL to check
        base_url: Base URL for documentation

    Returns:
        True if URL should be downloaded, False otherwise
    """
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)

    # Must be same domain
    if parsed.netloc and parsed.netloc != base_parsed.netloc:
        return False

    # Must be under target path
    if not parsed.path.startswith("/pub/naif/toolkit_docs/C/"):
        return False

    # Must be HTML or directory index
    if not (parsed.path.endswith(".html") or parsed.path.endswith("/")):
        return False

    # Skip fragments and query parameters
    # (We'll download the base page without them)

    return True


def download_with_retry(client: httpx.Client, url: str, max_retries: int = 3) -> httpx.Response:
    """
    Download URL with retry logic for transient failures.

    Handles:
    - Connection errors (retry with exponential backoff)
    - Timeout errors (retry)
    - 5xx server errors (retry)
    - 404 errors (raise without retry)
    - Other errors (raise)

    Args:
        client: HTTP client to use
        url: URL to download
        max_retries: Maximum number of retry attempts

    Returns:
        HTTP response

    Raises:
        httpx.HTTPStatusError: For non-retryable errors
        httpx.HTTPError: For network/timeout errors after max retries
    """
    for attempt in range(max_retries):
        try:
            response = client.get(url, timeout=30.0)
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            # Don't retry 404s
            if e.response.status_code == 404:
                logger.warning(f"File not found (404): {url}")
                raise

            # Retry 5xx errors
            elif e.response.status_code >= 500:
                if attempt < max_retries - 1:
                    sleep_time = 2 ** attempt
                    logger.warning(f"Server error {e.response.status_code}, retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
                else:
                    logger.error(f"Server error after {max_retries} attempts: {url}")
                    raise
            else:
                # Other HTTP errors (403, etc.)
                raise

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                logger.warning(f"Network error, retrying in {sleep_time}s: {e}")
                time.sleep(sleep_time)
                continue
            else:
                logger.error(f"Network error after {max_retries} attempts: {url}")
                raise


def download_documentation(base_url: str, cache_dir: Path) -> None:
    """
    Download NAIF documentation recursively using BFS crawler.

    Process:
    1. Download to temporary directory for atomic completion
    2. Crawl documentation tree starting from base_url
    3. Filter URLs to stay within documentation path
    4. Save HTML files preserving directory structure
    5. Create .cache_version marker on completion
    6. Atomically rename temp directory to final location

    Args:
        base_url: Root URL of documentation tree
        cache_dir: Directory to cache documentation

    Raises:
        Exception: On download failures, network errors, etc.
    """
    logger.info(f"Downloading documentation from {base_url}")
    logger.info(f"Cache directory: {cache_dir}")

    # Create temporary download directory
    temp_dir = cache_dir.parent / ".spicedocs-download-tmp"
    if temp_dir.exists():
        logger.warning(f"Removing incomplete download: {temp_dir}")
        shutil.rmtree(temp_dir)

    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Check disk space (require 100MB) - using shutil.disk_usage for cross-platform support
        disk_usage = shutil.disk_usage(temp_dir)
        available_mb = disk_usage.free / (1024 * 1024)
        if available_mb < 100:
            raise OSError(f"Insufficient disk space: {available_mb:.1f} MB available, 100 MB required")

        # Initialize HTTP client
        headers = {
            "User-Agent": "SpiceDocs-MCP/0.1.0 (https://github.com/medley56/spicedocs-mcp)"
        }
        client = httpx.Client(headers=headers, follow_redirects=True)

        # BFS crawl
        visited: Set[str] = set()
        queue = deque([base_url])
        file_count = 0

        while queue:
            url = queue.popleft()

            # Normalize URL (remove fragments and trailing slash for comparison)
            normalized_url = url.split('#')[0].rstrip('/')
            if normalized_url in visited:
                continue

            visited.add(normalized_url)

            # Skip if not in scope
            if not should_download(url, base_url):
                continue

            try:
                # Download page
                response = download_with_retry(client, url)
                file_count += 1

                # Determine save path
                parsed = urlparse(url)

                # Always save under naif.jpl.nasa.gov, even if downloading from localhost (for testing)
                # This ensures consistent directory structure
                rel_path = parsed.path.lstrip('/')

                # Handle directory indices
                if rel_path.endswith('/'):
                    rel_path += 'index.html'

                # Use consistent host name (naif.jpl.nasa.gov) instead of actual host
                save_path = temp_dir / "naif.jpl.nasa.gov" / rel_path
                save_path.parent.mkdir(parents=True, exist_ok=True)

                # Save HTML
                save_path.write_bytes(response.content)

                # Progress logging
                if file_count % 50 == 0:
                    logger.info(f"Downloaded {file_count} files...")

                # Parse HTML to find links
                try:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        href = link['href']

                        # Convert relative URLs to absolute
                        absolute_url = urljoin(url, href)

                        # Remove fragments
                        absolute_url = absolute_url.split('#')[0]

                        if should_download(absolute_url, base_url):
                            queue.append(absolute_url)

                except Exception as e:
                    logger.warning(f"Failed to parse links from {url}: {e}")

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    # Log and continue for 404s
                    continue
                else:
                    # Re-raise other HTTP errors
                    raise
            except Exception as e:
                logger.error(f"Failed to download {url}: {e}")
                raise

        logger.info(f"Downloaded {file_count} files successfully")

        # Create cache version file
        version_data = {
            "version": CACHE_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "base_url": base_url,
            "file_count": file_count,
            "completed": True
        }

        version_file = temp_dir / ".cache_version"
        with open(version_file, 'w') as f:
            json.dump(version_data, f, indent=2)

        # Atomic rename to final location
        if cache_dir.exists():
            shutil.rmtree(cache_dir)

        temp_dir.rename(cache_dir)
        logger.info(f"Documentation cached successfully at {cache_dir}")

    except Exception:
        # Clean up temp directory on failure
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise


def get_or_download_cache() -> Path:
    """
    Get cache directory, downloading documentation if necessary.

    Returns path to documentation root (naif.jpl.nasa.gov directory).
    Downloads documentation from NAIF website if cache is invalid.

    Returns:
        Path to documentation root directory

    Raises:
        Exception: If download fails or cache cannot be created
    """
    cache_dir = get_cache_dir()

    if not is_cache_valid(cache_dir):
        logger.info("Documentation cache not found or invalid")

        # Ensure cache directory is writable
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            test_file = cache_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except PermissionError as e:
            raise PermissionError(f"No write permission for cache directory: {cache_dir}") from e

        # Download documentation
        base_url = os.environ.get("SPICEDOCS_BASE_URL", DEFAULT_BASE_URL)

        # Skip download if environment variable set (for testing)
        if os.environ.get("SPICEDOCS_SKIP_DOWNLOAD", "false").lower() == "true":
            raise RuntimeError("Cache invalid and download skipped (SPICEDOCS_SKIP_DOWNLOAD=true)")

        download_documentation(base_url, cache_dir)
    else:
        logger.debug("Using existing documentation cache")

    return cache_dir / "naif.jpl.nasa.gov"
