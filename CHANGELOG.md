# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of SpiceDocs MCP Server
- Full-text search capabilities using SQLite FTS5
- Automatic documentation download and caching from NAIF website
- MCP tools: `search_archive`, `get_page`, `list_pages`, `extract_links`, `get_archive_stats`
- Platform-appropriate cache directory management
- CLI options for cache management (`--refresh`, `--cache-dir`)

### Changed
- Nothing yet

### Deprecated
- Nothing yet

### Removed
- **BREAKING**: Removed support for custom archive path argument. Documentation is now always automatically downloaded and cached to a platform-appropriate directory.
  - The `ARCHIVE_PATH` command-line argument is no longer supported
  - The database is now always stored in the cache directory, not in the archive directory
  - Users who were using local archive directories should migrate to the automatic caching workflow
  - Use `--cache-dir` to see the cache location and `--refresh` to re-download documentation

### Fixed
- Nothing yet

### Security
- Nothing yet

### Migration Notes

If you were previously using the server with a local archive path:

```bash
# Old usage (no longer supported)
spicedocs-mcp /path/to/local/archive

# New usage (documentation is automatically downloaded)
spicedocs-mcp
```

For development and CI environments, you can override the cache location using the `SPICEDOCS_CACHE_DIR` environment variable:

```bash
SPICEDOCS_CACHE_DIR=/custom/cache/path spicedocs-mcp
```

[Unreleased]: https://github.com/medley56/spicedocs-mcp/commits/main
