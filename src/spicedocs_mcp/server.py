#!/usr/bin/env python3
"""
NAIF SPICE Documentation MCP Server

A modern Model Context Protocol server for searching and browsing NAIF SPICE documentation.
Built with FastMCP for improved simplicity and maintainability.
"""

import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

from .cache import get_or_download_cache, get_cache_dir

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("spicedocs-mcp")

# Initialize FastMCP server
mcp = FastMCP("spicedocs")
mcp.description = "Search and browse NAIF SPICE documentation"

# Global variables for database connection
archive_path: Optional[Path] = None
db_conn: Optional[sqlite3.Connection] = None
fts_available: bool = False


def init_database(archive_dir: Path) -> sqlite3.Connection:
    """Initialize SQLite database for the archive."""
    global fts_available

    # Store database in cache directory if using cached documentation,
    # otherwise store it in the archive directory (for backward compatibility)
    cache_dir = get_cache_dir()
    naif_path = cache_dir / "naif.jpl.nasa.gov"

    if archive_dir == naif_path:
        # Using cached documentation - store DB in cache directory
        db_path = cache_dir / ".archive_index.db"
    else:
        # Using local archive - store DB in archive directory (backward compatible)
        db_path = archive_dir / ".archive_index.db"

    conn = sqlite3.connect(str(db_path))
    
    # Create main table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            title TEXT,
            content TEXT,
            url TEXT,
            last_modified REAL
        )
    """)
    
    # Try to create FTS5 virtual table for full-text search
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
                title, content, url, content=pages, content_rowid=id
            )
        """)
        fts_available = True
        logger.info("FTS5 search enabled")
    except sqlite3.OperationalError as e:
        logger.warning(f"FTS5 not available, using basic search: {e}")
        fts_available = False
    
    # Check if index needs rebuilding
    cursor = conn.execute("SELECT COUNT(*) FROM pages")
    if cursor.fetchone()[0] == 0:
        logger.info("Building search index...")
        rebuild_index(archive_dir, conn)
        logger.info("Search index built successfully")
    
    return conn


def rebuild_index(archive_dir: Path, conn: sqlite3.Connection):
    """Rebuild the search index by scanning all HTML files."""
    for html_file in archive_dir.rglob("*.html"):
        try:
            index_file(html_file, archive_dir, conn)
        except Exception as e:
            logger.warning(f"Failed to index {html_file}: {e}")
    conn.commit()


def index_file(file_path: Path, base_dir: Path, conn: sqlite3.Connection):
    """Index a single HTML file."""
    relative_path = file_path.relative_to(base_dir)
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    soup = BeautifulSoup(content, 'html.parser')
    
    # Extract title
    title_tag = soup.find('title')
    title = title_tag.get_text().strip() if title_tag else file_path.stem
    
    # Extract text content
    for script in soup(["script", "style"]):
        script.decompose()
    text_content = ' '.join(soup.get_text().split())
    
    # Try to extract original URL
    url = str(relative_path)
    canonical = soup.find('link', rel='canonical')
    if canonical and canonical.get('href'):
        url = canonical['href']
    
    # Insert into database
    cursor = conn.execute("""
        INSERT OR REPLACE INTO pages (path, title, content, url, last_modified)
        VALUES (?, ?, ?, ?, ?)
    """, (str(relative_path), title, text_content, url, file_path.stat().st_mtime))
    
    # Update FTS index if available
    if fts_available:
        rowid = cursor.lastrowid
        if not rowid:
            cursor = conn.execute("SELECT id FROM pages WHERE path = ?", (str(relative_path),))
            result = cursor.fetchone()
            if result:
                rowid = result[0]
        
        if rowid:
            conn.execute("""
                INSERT OR REPLACE INTO pages_fts (rowid, title, content, url)
                VALUES (?, ?, ?, ?)
            """, (rowid, title, text_content, url))


@mcp.tool()
async def search_archive(query: str, limit: int = 10) -> str:
    """
    Search for content across all pages in the SPICE documentation.
    
    Args:
        query: Search query (supports basic text search)
        limit: Maximum number of results to return (default: 10)
    
    Returns:
        Search results with titles, paths, and snippets
    """
    if not db_conn:
        return "Error: Database not initialized"
    
    if fts_available:
        # Use FTS5 search
        cursor = db_conn.execute("""
            SELECT p.path, p.title, p.url, snippet(pages_fts, 1, '<mark>', '</mark>', '...', 64) as snippet
            FROM pages_fts
            JOIN pages p ON pages_fts.rowid = p.id
            WHERE pages_fts MATCH ?
            ORDER BY bm25(pages_fts)
            LIMIT ?
        """, (query, limit))
    else:
        # Fallback to LIKE search
        search_pattern = f"%{query}%"
        cursor = db_conn.execute("""
            SELECT path, title, url, 
                   substr(content, max(1, instr(lower(content), lower(?)) - 50), 150) as snippet
            FROM pages
            WHERE title LIKE ? OR content LIKE ?
            LIMIT ?
        """, (query, search_pattern, search_pattern, limit))
    
    results = cursor.fetchall()
    
    if not results:
        return f"No results found for query: '{query}'"
    
    response = f"Found {len(results)} results for '{query}':\n\n"
    for i, (path, title, url, snippet) in enumerate(results, 1):
        response += f"{i}. **{title}**\n"
        response += f"   Path: {path}\n"
        if url != path:
            response += f"   Original URL: {url}\n"
        response += f"   Snippet: {snippet}\n\n"
    
    return response


@mcp.tool()
async def get_page(path: str, include_raw: bool = False) -> str:
    """
    Retrieve the content of a specific page from the SPICE documentation.
    
    Args:
        path: Relative path to the HTML file (e.g., 'index.html', 'ug/mkspk.html')
        include_raw: Include raw HTML content in addition to parsed text
    
    Returns:
        Page content with title, size, and text (optionally raw HTML)
    """
    if not archive_path:
        return "Error: Archive path not initialized"
    
    # Ensure path is safe and within archive
    safe_path = archive_path / path
    try:
        safe_path = safe_path.resolve()
        safe_path.relative_to(archive_path)  # Raises ValueError if outside
    except (ValueError, OSError):
        return f"Error: Path '{path}' is outside the archive or invalid"
    
    if not safe_path.exists():
        return f"Error: File '{path}' not found in archive"
    
    try:
        with open(safe_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract metadata
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else safe_path.stem
        
        # Extract clean text
        for script in soup(["script", "style"]):
            script.decompose()
        text_content = ' '.join(soup.get_text().split())
        
        response = f"# {title}\n\n"
        response += f"**Path:** {path}\n"
        response += f"**File size:** {len(content)} bytes\n\n"
        response += f"**Content:**\n{text_content}"
        
        if include_raw:
            response += f"\n\n**Raw HTML:**\n```html\n{content}\n```"
        
        return response
        
    except Exception as e:
        return f"Error reading file '{path}': {str(e)}"


@mcp.tool()
async def list_pages(filter_pattern: Optional[str] = None, limit: int = 50) -> str:
    """
    List available pages in the SPICE documentation archive.
    
    Args:
        filter_pattern: Optional filter pattern (e.g., '*.html', 'ug/*')
        limit: Maximum number of pages to return (default: 50)
    
    Returns:
        List of pages with titles and paths
    """
    if not db_conn:
        return "Error: Database not initialized"
    
    # Get pages from database
    if filter_pattern:
        cursor = db_conn.execute("""
            SELECT path, title, url FROM pages 
            WHERE path GLOB ? 
            ORDER BY path 
            LIMIT ?
        """, (filter_pattern, limit))
    else:
        cursor = db_conn.execute("""
            SELECT path, title, url FROM pages 
            ORDER BY path 
            LIMIT ?
        """, (limit,))
    
    results = cursor.fetchall()
    
    if not results:
        return "No pages found in archive"
    
    response = f"Archive contains {len(results)} pages"
    if filter_pattern:
        response += f" matching '{filter_pattern}'"
    response += ":\n\n"
    
    for path, title, url in results:
        response += f"• **{title}**\n  Path: {path}\n"
        if url != path:
            response += f"  Original: {url}\n"
        response += "\n"
    
    return response


@mcp.tool()
async def extract_links(path: str, internal_only: bool = True) -> str:
    """
    Extract all links from a specific page in the documentation.
    
    Args:
        path: Relative path to the HTML file
        internal_only: Only return links to other pages in the archive
    
    Returns:
        List of links found in the page
    """
    if not archive_path:
        return "Error: Archive path not initialized"
    
    # Validate path
    safe_path = archive_path / path
    try:
        safe_path = safe_path.resolve()
        safe_path.relative_to(archive_path)
    except (ValueError, OSError):
        return f"Error: Invalid path '{path}'"
    
    if not safe_path.exists():
        return f"Error: File '{path}' not found"
    
    try:
        with open(safe_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().strip()
            
            if internal_only:
                # Check if link points to a file in our archive
                if href.startswith('http'):
                    continue  # Skip external links
                
                # Parse the href to separate path from fragment/query
                base_href = href.split('#')[0].split('?')[0]
                if not base_href and href.startswith('#'):
                    # This is a same-page anchor link
                    links.append((href, text))
                    continue
                
                if not base_href:
                    continue
                
                # Build the path relative to the current file's directory
                current_dir = Path(path).parent
                if base_href.startswith('/'):
                    # Absolute path within archive
                    link_path = Path(base_href.lstrip('/'))
                else:
                    # Relative path from current file
                    link_path = current_dir / base_href
                
                # Normalize the path
                link_path = Path(os.path.normpath(link_path))
                
                # Check if it exists in archive
                full_link_path = archive_path / link_path
                try:
                    full_link_path = full_link_path.resolve()
                    full_link_path.relative_to(archive_path)
                    if not full_link_path.exists():
                        continue
                except (ValueError, OSError):
                    continue
            
            links.append((href, text))
        
        if not links:
            return f"No {'internal ' if internal_only else ''}links found in '{path}'"
        
        response = f"Found {len(links)} {'internal ' if internal_only else ''}links in '{path}':\n\n"
        
        for href, text in links:
            response += f"• [{text or 'No text'}]({href})\n"
        
        return response
        
    except Exception as e:
        return f"Error extracting links from '{path}': {str(e)}"


@mcp.tool()
async def get_archive_stats() -> str:
    """
    Get statistics about the SPICE documentation archive.
    
    Returns:
        Archive statistics including file counts, sizes, and indexed pages
    """
    if not archive_path or not db_conn:
        return "Error: Archive not initialized"
    
    try:
        # Count files
        html_files = list(archive_path.rglob("*.html"))
        other_files = [f for f in archive_path.rglob("*") 
                      if f.is_file() and not f.name.endswith('.html')]
        
        # Calculate total size
        total_size = sum(f.stat().st_size for f in archive_path.rglob("*") if f.is_file())
        
        # Get database stats
        cursor = db_conn.execute("SELECT COUNT(*) FROM pages")
        indexed_pages = cursor.fetchone()[0]
        
        response = "# Archive Statistics\n\n"
        response += f"**Archive Path:** {archive_path}\n"
        response += f"**HTML Pages:** {len(html_files)}\n"
        response += f"**Other Files:** {len(other_files)}\n"
        response += f"**Total Files:** {len(html_files) + len(other_files)}\n"
        response += f"**Indexed Pages:** {indexed_pages}\n"
        response += f"**Total Size:** {total_size / (1024*1024):.1f} MB\n"
        response += f"**Search Type:** {'Full-text search (FTS5)' if fts_available else 'Basic search'}\n"
        
        return response
        
    except Exception as e:
        return f"Error getting archive stats: {str(e)}"


def main():
    """
    Main entry point for the MCP server.

    Usage:
        spicedocs-mcp                    # Use cached docs (download if needed)
        spicedocs-mcp <archive_path>     # Use local archive (backward compatible)
        spicedocs-mcp --refresh          # Force re-download to cache
        spicedocs-mcp --cache-dir        # Show cache directory and exit
        spicedocs-mcp --help             # Show help message
    """
    global archive_path, db_conn

    # Parse command-line arguments
    if len(sys.argv) == 1:
        # No arguments: use cached documentation
        try:
            archive_path = get_or_download_cache()
            logger.info(f"Using cached documentation at: {archive_path}")
        except Exception as e:
            logger.error(f"Failed to initialize documentation cache: {e}")
            logger.error("Check your network connection and try again.")
            sys.exit(1)

    elif len(sys.argv) == 2:
        arg = sys.argv[1]

        if arg in ["--help", "-h"]:
            print(__doc__)
            print("\nUsage: spicedocs-mcp [OPTIONS] [ARCHIVE_PATH]")
            print("\nOptions:")
            print("  ARCHIVE_PATH      Path to local SPICE documentation archive (optional)")
            print("  --refresh         Force re-download of cached documentation")
            print("  --cache-dir       Show cache directory location and exit")
            print("  --help, -h        Show this help message")
            print("\nIf ARCHIVE_PATH is not provided, documentation will be automatically")
            print("downloaded to a platform-appropriate cache directory on first run.")
            sys.exit(0)

        elif arg == "--cache-dir":
            print(get_cache_dir())
            sys.exit(0)

        elif arg == "--refresh":
            import shutil
            cache_dir = get_cache_dir()
            if cache_dir.exists():
                logger.info(f"Removing existing cache at: {cache_dir}")
                shutil.rmtree(cache_dir)
            try:
                archive_path = get_or_download_cache()
                logger.info("Cache refreshed successfully")
            except Exception as e:
                logger.error(f"Failed to refresh cache: {e}")
                sys.exit(1)

        else:
            # Backward compatible: treat as archive path
            archive_path = Path(arg).resolve()
            if not archive_path.exists():
                logger.error(f"Archive path does not exist: {archive_path}")
                sys.exit(1)
            logger.info(f"Using local archive at: {archive_path}")

    else:
        print("Usage: spicedocs-mcp [OPTIONS] [ARCHIVE_PATH]", file=sys.stderr)
        print("Try 'spicedocs-mcp --help' for more information.", file=sys.stderr)
        sys.exit(1)

    logger.info(f"Initializing SpiceDocs MCP server with archive: {archive_path}")

    try:
        # Initialize database
        db_conn = init_database(archive_path)

        # Run the FastMCP server (synchronous)
        mcp.run()

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        if db_conn:
            db_conn.close()


if __name__ == "__main__":
    main()