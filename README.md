# SpiceDocs MCP Server

A Model Context Protocol (MCP) server that provides Claude with access to a local web archive of NAIF SPICE documentation. This server enables searching, browsing, and querying SPICE toolkit documentation through the MCP protocol.

## Overview

The SpiceDocs MCP server indexes and provides full-text search capabilities across NAIF SPICE documentation pages. It uses SQLite with FTS5 (Full-Text Search) for efficient searching and includes several tools for exploring the documentation:

- **search_archive**: Full-text search across all documentation pages
- **get_page**: Retrieve specific documentation pages
- **list_pages**: Browse available pages with optional filtering
- **extract_links**: Extract internal/external links from pages
- **get_archive_stats**: View statistics about the documentation archive

## Features

- Full-text search with FTS5 (falls back to basic search if unavailable)
- Automatic indexing of HTML documentation files
- Clean text extraction from HTML pages
- Path traversal protection for secure file access
- Support for both relative and absolute paths within the archive
- Link extraction for navigation between related pages

## System Requirements

### Required

- **Python 3.10 or higher** - The server requires Python 3.10+ for type hints and async features
- **[uv](https://docs.astral.sh/uv/getting-started/installation/) package manager** - Used for dependency management and running the server
- **Internet connection** - Required for first-time documentation download (~28MB)
- **Disk space** - At least 100MB free for downloading and caching documentation

### Optional (Recommended)

- **SQLite with FTS5 extension** - Enables fast full-text search with BM25 ranking. Python includes SQLite, but FTS5 support depends on how your system's SQLite library was compiled. The server automatically falls back to basic search if FTS5 is unavailable.

To check if FTS5 is available on your system:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect(':memory:')
try:
    conn.execute('CREATE VIRTUAL TABLE t USING fts5(c)')
    print('FTS5 is available')
except Exception:
    print('FTS5 is not available')
"
```

If the command shows "FTS5 is not available", your SQLite doesn't support FTS5. The server will still work, but search will be slower.

## Quick Start

The easiest way to use SpiceDocs MCP is with Claude Desktop and `uvx`:

### Installation with Claude Desktop

1. Install uv if you haven't already:

```bash
# On macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2. Add SpiceDocs MCP to your Claude Desktop configuration:

**macOS/Linux:** `~/.config/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "spicedocs": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/medley56/spicedocs-mcp@1.0.0",
        "spicedocs-mcp"
      ]
    }
  }
}
```

**Note:** Replace `@1.0.0` with the desired version tag. See [Releases](https://github.com/medley56/spicedocs-mcp/releases) for available versions. Installing without a version tag will install unreleased code from the main branch.

3. Restart Claude Desktop

On first run, the server will automatically download and cache the NAIF SPICE documentation (~28MB, ~710 HTML files). This takes 2-5 minutes depending on your connection. Subsequent starts are instant.

## Advanced Installation

### For Development

If you want to modify or extend the server:

1. Clone this repository:

```bash
git clone https://github.com/medley56/spicedocs-mcp
cd spicedocs-mcp
```

2. Install dependencies using uv:

```bash
uv sync
```

### Documentation Archive Structure

The server expects a directory structure similar to:

```text
archive_directory/
  naif.jpl.nasa.gov/
    pub/
      naif/
        toolkit_docs/
          C/
            index.html
            cspice/
              spkpos_c.html
              furnsh_c.html
              ...
            ug/
              mkspk.html
              ...
```

## Running the Server

### Command-Line Options

```
spicedocs-mcp [OPTIONS] [ARCHIVE_PATH]

Options:
  ARCHIVE_PATH      Path to local SPICE documentation archive (optional)
  --refresh         Force re-download of cached documentation
  --cache-dir       Show cache directory location and exit
  --help, -h        Show help message
```

If ARCHIVE_PATH is not provided, documentation will be automatically downloaded to a platform-appropriate cache directory on first run.

### For Development/Testing

If you've cloned the repository and want to run the server locally:

```bash
# Use cached/downloaded documentation (recommended)
uv run spicedocs-mcp

# Or provide a local archive path for testing
uv run spicedocs-mcp /path/to/local/archive
```

### Using with Claude Desktop (Development Mode)

If you've cloned the repository and want to use your local version with Claude Desktop:

```json
{
  "mcpServers": {
    "spicedocs": {
      "command": "uv",
      "args": [
        "run",
        "spicedocs-mcp"
      ],
      "cwd": "/absolute/path/to/your/cloned/spicedocs-mcp"
    }
  }
}
```

Replace `/absolute/path/to/your/cloned/spicedocs-mcp` with the actual path to your cloned repository.

**Note:** For development, you can also provide a local archive path if you want to test with a custom documentation set:
```json
{
  "mcpServers": {
    "spicedocs": {
      "command": "uv",
      "args": [
        "run",
        "spicedocs-mcp",
        "/path/to/local/archive"
      ],
      "cwd": "/absolute/path/to/your/cloned/spicedocs-mcp"
    }
  }
}
```

## Usage Examples

Once connected, Claude can use the following tools:

### Search Documentation

```text
Search for "ephemeris kernels" in the SPICE documentation
```

This uses the `search_archive` tool to find relevant pages.

### Get Specific Page

```text
Show me the documentation for spkpos_c.html
```

This uses the `get_page` tool to retrieve the full content of a specific page.

### List Available Pages

```text
List all pages in the user guide (ug/ directory)
```

This uses the `list_pages` tool with filtering.

### Extract Links

```text
Show me all internal links from the index.html page
```

This uses the `extract_links` tool to find navigation links.

### Archive Statistics

```text
What's the size and structure of the documentation archive?
```

This uses the `get_archive_stats` tool to get overview information.

## Cache Management

### Cache Location

Documentation is cached in platform-appropriate directories:
- **Linux**: `~/.cache/spicedocs-mcp`
- **macOS**: `~/Library/Caches/spicedocs-mcp`
- **Windows**: `%LOCALAPPDATA%\spicedocs\spicedocs-mcp\Cache`

To see your cache location:
```bash
uvx --from git+https://github.com/medley56/spicedocs-mcp@1.0.0 spicedocs-mcp --cache-dir
```

### Refresh Cache

To re-download the documentation (e.g., if NAIF updates their docs):
```bash
uvx --from git+https://github.com/medley56/spicedocs-mcp@1.0.0 spicedocs-mcp --refresh
```

### Clear Cache

To free up disk space, delete the cache directory:
```bash
# Linux/macOS
rm -rf ~/.cache/spicedocs-mcp

# Windows
rmdir /s "%LOCALAPPDATA%\spicedocs-mcp"
```

## Database Indexing

The server automatically creates a SQLite database (`.archive_index.db`) in the cache directory on first run. This database:

- Indexes all HTML files in the downloaded documentation
- Extracts titles and text content
- Creates a full-text search index (FTS5) if available
- Caches metadata for fast retrieval

The index is built automatically after downloading documentation. To rebuild, use the `--refresh` flag to re-download and re-index.

## Architecture

Built using:

- **FastMCP**: Modern MCP server framework
- **SQLite + FTS5**: Full-text search capabilities
- **BeautifulSoup**: HTML parsing and text extraction
- **httpx**: HTTP client for downloading documentation
- **platformdirs**: Platform-appropriate cache directory management
- **uv**: Fast Python package and project manager

## Troubleshooting

### Server won't start

- **Network issues**: Check your internet connection if downloading documentation for the first time
- **Cache directory**: Ensure you have write permissions to the cache directory
- **Dependencies**: Check that uv dependencies are installed: `uv sync`
- **Logs**: Look for error messages in the logs (written to stderr)

### First download is slow or fails

- The first run downloads ~28MB of documentation, which may take 2-5 minutes
- If download fails due to network issues, delete the cache directory and try again
- Use `--cache-dir` to see where documentation is being cached
- Check firewall settings if unable to connect to naif.jpl.nasa.gov

### Search returns no results

- Ensure the documentation has been downloaded successfully
- Check the cache directory contains `.archive_index.db`
- Try refreshing: `spicedocs-mcp --refresh`
- Check if FTS5 is available (see [System Requirements](#system-requirements))

### FTS5 not available

If you see "FTS5 not available, using basic search" in the logs:

- **Linux (Debian/Ubuntu)**: FTS5 is typically included with Python 3.10+ on most distributions
- **macOS**: FTS5 is usually included with the system SQLite
- **Windows**: FTS5 is typically included with Python's bundled SQLite

If FTS5 is missing, you can still use the server - it will fall back to basic LIKE-based search which is slower but functional.

### Claude Desktop doesn't see the server

- Verify the configuration file path and JSON syntax
- Restart Claude Desktop after modifying the configuration
- Check Claude Desktop logs for connection errors
- Ensure uv is installed and in your PATH

## Development

To modify or extend the server:

1. Edit [server.py](src/spicedocs_mcp/server.py)
2. Add new tools using the `@mcp.tool()` decorator
3. Test changes by running the server directly

## License

[Specify your license here]

## Contributing

[Add contribution guidelines if applicable]
