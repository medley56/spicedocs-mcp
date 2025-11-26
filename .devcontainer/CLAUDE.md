# SpiceDocs MCP Server Development Guide

This document provides comprehensive instructions for developing the SpiceDocs MCP server using Claude Code.

## Project Overview

SpiceDocs MCP is a Model Context Protocol (MCP) server that provides Claude with access to a local web archive of NAIF SPICE documentation. It enables full-text search, browsing, and querying of SPICE toolkit documentation through the MCP protocol.

### Key Technologies

- **FastMCP**: Modern MCP server framework for building MCP servers
- **SQLite with FTS5**: Full-text search indexing of documentation
- **BeautifulSoup**: HTML parsing and text extraction
- **uv**: Fast Python package and project manager for dependency management and builds
- **Python 3.12**: Project language version

### Architecture

The server is implemented as a single module at [src/spicedocs_mcp/server.py](../src/spicedocs_mcp/server.py) that:

1. Automatically downloads SPICE documentation to a platform-appropriate cache directory
2. Builds a SQLite database with FTS5 indexing for fast full-text search
3. Exposes 5 MCP tools for searching, browsing, and analyzing documentation
4. Uses path traversal protection for secure file access

## Project Structure

```
spicedocs-mcp/
├── src/
│   └── spicedocs_mcp/
│       ├── __init__.py          # Package metadata
│       ├── server.py            # Main MCP server implementation
│       └── naif.jpl.nasa.gov/   # Local archive of SPICE documentation (HTML files)
├── .devcontainer/
│   ├── Dockerfile               # Development container setup
│   ├── devcontainer.json        # VSCode devcontainer config
│   ├── setup-dev-environment.sh # Post-create setup script
│   └── CLAUDE.md                # This file
├── pyproject.toml               # uv project configuration
├── uv.lock                      # uv dependency lock file
├── README.md                    # User-facing documentation
└── ROADMAP.md                   # Future development plans
```

## Development Environment

### Container Setup

This project uses a VSCode devcontainer with:
- Python 3.12 slim base image
- uv package manager pre-installed
- SQLite3 with FTS5 support
- Git, gh CLI, and development tools
- Claude Code extension pre-configured

The container automatically runs [setup-dev-environment.sh](./setup-dev-environment.sh) on creation, which:
- Installs Python dependencies via `uv sync`
- Configures Git authentication (SSH/HTTPS)
- Sets up GPG commit signing if configured

### Dependencies

All dependencies are managed through uv and specified in [pyproject.toml](../pyproject.toml):
- `beautifulsoup4>=4.12.0,<5.0.0` - HTML parsing
- `mcp>=1.0.0,<2.0.0` - MCP protocol library
- `fastmcp>=2.0.0,<3.0.0` - MCP server framework

### Installing Dependencies

```bash
uv sync
```

This creates a virtual environment and installs all dependencies from the lock file.

## Running the Server

### Standalone Mode

Run the server directly:

```bash
uv run spicedocs-mcp
```

On first run, the server will automatically download the SPICE documentation to a platform-appropriate cache directory.

### Testing with MCP Inspector

Use the MCP Inspector CLI tool to test the server:

```bash
npx @modelcontextprotocol/inspector uv run spicedocs-mcp
```

This opens a web interface for testing MCP tools interactively.

### With Claude Desktop

Add to your Claude Desktop configuration file (`~/.config/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "spicedocs": {
      "command": "uv",
      "args": [
        "run",
        "spicedocs-mcp"
      ],
      "cwd": "/absolute/path/to/spicedocs-mcp"
    }
  }
}
```

## Server Implementation Details

### Database Initialization

When the server starts, it:

1. Downloads documentation to a platform-appropriate cache directory (if not already cached)
2. Creates a SQLite database (`.archive_index.db`) in the cache directory
3. Creates a `pages` table for storing page metadata
4. Attempts to create an FTS5 virtual table for full-text search
5. Falls back to basic LIKE search if FTS5 is unavailable
6. Indexes all HTML files if the database is empty

The index is built automatically on first run and cached for subsequent runs.

### Rebuilding the Index

To force a rebuild of the search index, use the `--refresh` flag:

```bash
uv run spicedocs-mcp --refresh
```

This will re-download the documentation and rebuild the index.

### Available MCP Tools

The server exposes 5 tools to Claude:

1. **`search_archive`** - Full-text search across all documentation pages
   - Parameters: `query` (string), `limit` (int, default 10)
   - Uses FTS5 BM25 ranking if available, otherwise LIKE search
   - Returns ranked results with snippets

2. **`get_page`** - Retrieve specific documentation page content
   - Parameters: `path` (string), `include_raw` (bool, default false)
   - Path traversal protection validates all paths
   - Returns title, parsed text, optionally raw HTML

3. **`list_pages`** - Browse available pages with optional filtering
   - Parameters: `filter_pattern` (string, optional), `limit` (int, default 50)
   - Supports SQLite GLOB patterns (e.g., `ug/*.html`)
   - Returns list of pages with titles and paths

4. **`extract_links`** - Extract links from a specific page
   - Parameters: `path` (string), `internal_only` (bool, default true)
   - Resolves relative and absolute paths within archive
   - Validates that linked pages exist in the archive

5. **`get_archive_stats`** - View archive statistics
   - No parameters
   - Returns file counts, sizes, indexed pages, search type

## Development Workflows

### Adding a New MCP Tool

1. Add a new function decorated with `@mcp.tool()` in [server.py](../src/spicedocs_mcp/server.py)
2. Include comprehensive docstring with Args and Returns sections
3. Use type hints for all parameters
4. Return string responses (MCP tools must return strings)
5. Add error handling with descriptive error messages
6. Test the tool using MCP Inspector

Example:

```python
@mcp.tool()
async def my_new_tool(param: str, optional_param: int = 10) -> str:
    """
    Brief description of what the tool does.

    Args:
        param: Description of required parameter
        optional_param: Description of optional parameter (default: 10)

    Returns:
        Description of what is returned
    """
    # Implementation here
    return "Result string"
```

### Modifying Search Behavior

Search logic is in the `search_archive` function at [server.py:136](../src/spicedocs_mcp/server.py#L136).

FTS5 search uses BM25 ranking:
```python
WHERE pages_fts MATCH ?
ORDER BY bm25(pages_fts)
```

Fallback search uses LIKE pattern matching:
```python
WHERE title LIKE ? OR content LIKE ?
```

### HTML Parsing and Text Extraction

Text extraction logic is in `index_file` at [server.py:89](../src/spicedocs_mcp/server.py#L89):

```python
# Remove script and style tags
for script in soup(["script", "style"]):
    script.decompose()

# Extract clean text
text_content = ' '.join(soup.get_text().split())
```

This same pattern is used in `get_page` for retrieving page content.

### Path Security

All file operations use path traversal protection:

```python
safe_path = archive_path / path
safe_path = safe_path.resolve()
safe_path.relative_to(archive_path)  # Raises ValueError if outside
```

This prevents accessing files outside the archive directory.

## Testing and Debugging

### Testing Tools Manually

Use the Python REPL to test individual functions:

```bash
uv run python
```

```python
from pathlib import Path
from spicedocs_mcp.cache import get_or_download_cache
from spicedocs_mcp.server import init_database, search_archive
import spicedocs_mcp.server as server_module

# Get or download cached documentation
archive_path = get_or_download_cache()
server_module.archive_path = archive_path
init_database(archive_path)

# Test search
import asyncio
result = asyncio.run(search_archive("ephemeris", limit=5))
print(result)
```

### Viewing Logs

The server logs to stderr using Python's logging module:

```python
logger = logging.getLogger("spicedocs-mcp")
logger.info("Information message")
logger.warning("Warning message")
logger.error("Error message")
```

When running with Claude Desktop, check the Claude logs for server output.

### Database Inspection

Find your cache directory first:

```bash
uv run spicedocs-mcp --cache-dir
```

Then examine the SQLite database directly:

```bash
sqlite3 ~/.cache/spicedocs-mcp/spicedocs/.archive_index.db

# Show all tables
.tables

# Count indexed pages
SELECT COUNT(*) FROM pages;

# Check if FTS5 is available
SELECT COUNT(*) FROM pages_fts;

# Test search
SELECT path, title FROM pages_fts WHERE pages_fts MATCH 'ephemeris' LIMIT 5;

.quit
```

## Building and Distribution

### Project Configuration

The project uses uv's build system. Key configuration in [pyproject.toml](../pyproject.toml):

```toml
[project]
name = "spicedocs-mcp"
version = "0.1.0"
requires-python = ">=3.10"

[project.scripts]
spicedocs-mcp = "spicedocs_mcp.server:main"

[build-system]
requires = ["uv_build>=0.9.11,<0.10.0"]
build-backend = "uv_build"
```

The `[project.scripts]` section creates a console script entry point for `uv run spicedocs-mcp`.

### Running with uvx

Users can install and run directly from a Git repository using uvx:

```bash
uvx --from git+https://github.com/username/spicedocs-mcp spicedocs-mcp
```

This creates an isolated environment and runs the server without requiring local installation.

### Building a Wheel

To build a distributable wheel:

```bash
uv build
```

This creates a wheel in the `dist/` directory.

## Code Style and Conventions

### Style Guidelines

- Follow PEP 8 conventions
- Use Ruff for linting and formatting (configured in devcontainer)
- Format on save is enabled in VSCode
- Organize imports with Ruff

### Type Hints

Use type hints for all function parameters and return values:

```python
from typing import Optional
from pathlib import Path

def my_function(path: Path, optional: Optional[str] = None) -> str:
    pass
```

### Docstrings

Use Google-style docstrings for all public functions:

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief one-line description.

    More detailed description if needed. Can span multiple
    lines and include implementation details.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When parameter validation fails
    """
```

### Error Handling

- Return descriptive error messages as strings (not exceptions in MCP tools)
- Use try-except blocks for file operations and database queries
- Log errors to stderr using the logger
- Include context in error messages (e.g., file paths, query strings)

Example:

```python
try:
    with open(file_path, 'r') as f:
        content = f.read()
except FileNotFoundError:
    logger.error(f"File not found: {file_path}")
    return f"Error: File '{file_path}' not found"
except Exception as e:
    logger.error(f"Error reading {file_path}: {e}")
    return f"Error reading file: {str(e)}"
```

## Common Development Tasks

### Add a new dependency

```bash
uv add package-name
```

This updates [pyproject.toml](../pyproject.toml) and regenerates [uv.lock](../uv.lock).

### Update all dependencies

```bash
uv lock --upgrade
uv sync
```

### Run code formatting

```bash
uv run ruff format .
```

### Run linting

```bash
uv run ruff check .
```

### Fix linting issues automatically

```bash
uv run ruff check --fix .
```

## Troubleshooting

### "Database not initialized" errors

Ensure the server's `main()` function is called. The global `db_path` variable must be set before tools can run.

### FTS5 not available

If SQLite doesn't have FTS5 support, the server falls back to basic LIKE search. Check the logs for:

```
FTS5 not available, using basic search
```

To verify FTS5 support:

```bash
sqlite3 -cmd "SELECT sqlite_version();" -cmd ".quit"
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
```

### Search returns no results

1. Find your cache directory: `uv run spicedocs-mcp --cache-dir`
2. Check if the database exists in the cache directory (`.archive_index.db`)
3. Check if pages are indexed: `sqlite3 <db> "SELECT COUNT(*) FROM pages;"`
4. Rebuild the index: `uv run spicedocs-mcp --refresh`
5. Check search query syntax (FTS5 has specific query syntax)

### Path traversal errors

The server protects against path traversal attacks. Valid paths must:
- Be relative to the documentation root
- Resolve to a location inside the archive
- Not contain `..` segments that escape the archive

Example valid paths:
- `pub/naif/toolkit_docs/C/index.html`
- `pub/naif/toolkit_docs/C/cspice/spkpos_c.html`

### Server won't start in Claude Desktop

1. Check the JSON syntax in `claude_desktop_config.json`
2. Ensure the `cwd` directory exists and contains [pyproject.toml](../pyproject.toml)
3. Check Claude Desktop logs for startup errors
4. Test the server command manually in a terminal
5. Check network connection on first run (documentation needs to be downloaded)

## Future Development

See [ROADMAP.md](../ROADMAP.md) for planned features:

1. **GitHub Repository** - Clean git history and publish to GitHub
2. **Clean up UV Management** - Simplify pyproject.toml for uvx installation
3. **Add Basic Tests** - Integration tests with GitHub Actions workflow
4. **Improved User Documentation** - Setup guides for uvx installation

## Additional Resources

### MCP Documentation

- [Model Context Protocol Specification](https://spec.modelcontextprotocol.io/)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

### uv Documentation

- [uv User Guide](https://docs.astral.sh/uv/)
- [uv Project Configuration](https://docs.astral.sh/uv/reference/configuration/)
- [uvx Tool Runner](https://docs.astral.sh/uv/guides/tools/)

### SQLite FTS5

- [SQLite FTS5 Documentation](https://www.sqlite.org/fts5.html)
- [FTS5 Query Syntax](https://www.sqlite.org/fts5.html#full_text_query_syntax)
- [BM25 Ranking](https://www.sqlite.org/fts5.html#the_bm25_function)

### Python Libraries

- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [pathlib Guide](https://docs.python.org/3/library/pathlib.html)

## Getting Help

When asking Claude Code for help with this project:

1. Reference specific files and line numbers (e.g., "in server.py:136")
2. Include error messages and log output
3. Describe what you've already tried
4. Ask specific questions rather than general requests

Examples:

- "How do I add BM25 weighting parameters to the FTS5 search in server.py:152?"
- "The extract_links function isn't resolving relative paths correctly. Can you review the logic at server.py:344?"
- "I'm getting 'Database not initialized' errors. What initialization sequence should I check?"

## Notes for Claude Code

When working on this project:

- Always read [server.py](../src/spicedocs_mcp/server.py) before making changes
- Test changes manually before suggesting them
- Keep the single-file architecture (don't split into multiple modules)
- Maintain backward compatibility with existing MCP tool signatures
- Use path traversal protection for all file operations
- Log informational messages to stderr using the logger
- Return descriptive error strings from MCP tools (don't raise exceptions)
- Keep dependencies minimal (only add if truly necessary)
- Update [README.md](../README.md) when adding new features or changing usage
