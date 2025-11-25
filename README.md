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

## Quick Start

The easiest way to use SpiceDocs MCP is with Claude Desktop and `uvx`:

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager

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
        "git+https://github.com/medley56/spicedocs-mcp",
        "spicedocs-mcp",
        "src/spicedocs_mcp/naif.jpl.nasa.gov"
      ]
    }
  }
}
```

3. Restart Claude Desktop

That's it! Claude will now have access to SPICE documentation through the MCP server. The documentation archive is bundled with the repository, so no additional setup is needed.

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

### For Development/Testing

If you've cloned the repository and want to run the server locally:

```bash
# From the project root
uv run spicedocs-mcp src/spicedocs_mcp/naif.jpl.nasa.gov
```

Or using Python directly:

```bash
uv run python src/spicedocs_mcp/server.py src/spicedocs_mcp/naif.jpl.nasa.gov
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
        "spicedocs-mcp",
        "src/spicedocs_mcp/naif.jpl.nasa.gov"
      ],
      "cwd": "/absolute/path/to/your/cloned/spicedocs-mcp"
    }
  }
}
```

Replace `/absolute/path/to/your/cloned/spicedocs-mcp` with the actual path to your cloned repository.

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

## Database Indexing

The server automatically creates a SQLite database (`.archive_index.db`) in the archive directory on first run. This database:

- Indexes all HTML files in the archive
- Extracts titles and text content
- Creates a full-text search index (FTS5) if available
- Caches metadata for fast retrieval

The index is built automatically if the database is empty. Rebuilding can be triggered by deleting the `.archive_index.db` file.

## Architecture

Built using:

- **FastMCP**: Modern MCP server framework
- **SQLite + FTS5**: Full-text search capabilities
- **BeautifulSoup**: HTML parsing and text extraction
- **uv**: Fast Python package and project manager

## Troubleshooting

### Server won't start

- Verify the archive path exists and contains HTML files
- Check that uv dependencies are installed: `uv sync`
- Look for error messages in the logs (written to stderr)

### Search returns no results

- Ensure the database has been built (check for `.archive_index.db` in archive directory)
- Try rebuilding the index by deleting `.archive_index.db` and restarting the server
- Check if FTS5 is available in your SQLite installation

### Claude Desktop doesn't see the server

- Verify the configuration file path and JSON syntax
- Ensure all paths in the configuration are absolute paths
- Restart Claude Desktop after modifying the configuration
- Check Claude Desktop logs for connection errors

## Development

To modify or extend the server:

1. Edit [server.py](src/spicedocs_mcp/server.py)
2. Add new tools using the `@mcp.tool()` decorator
3. Test changes by running the server directly

## License

[Specify your license here]

## Contributing

[Add contribution guidelines if applicable]
