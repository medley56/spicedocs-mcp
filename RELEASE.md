# Release Process

This document describes the release process for SpiceDocs MCP.

## Overview

SpiceDocs MCP uses a Git tag-based release process. Releases are published to GitHub (not PyPI), allowing users to install specific versions using `uvx` or `pip` with Git URLs.

## Versioning

This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

- **MAJOR** version for incompatible API changes
- **MINOR** version for new functionality in a backwards compatible manner
- **PATCH** version for backwards compatible bug fixes

## Branch Strategy

### Main Branch

The `main` branch contains the latest development code. All feature development happens here or in feature branches that merge into `main`.

### Release Branches

Minor and major releases are prepared in release branches:

- Branch naming: `release/X.Y` (e.g., `release/1.0`, `release/1.1`, `release/2.0`)
- Release branches are created from `main` when preparing a new minor or major release
- After release, the release branch is merged back into `main`

### Patch Releases

Patches are applied to existing release branches:

- Bug fixes can be backported from `main` to a release branch
- Patch releases are tagged on release branches (e.g., `1.0.1`, `1.0.2`)

## Creating a Release

### 1. Prepare the Release Branch

For a new minor or major release:

```bash
# Create release branch from main
git checkout main
git pull origin main
git checkout -b release/X.Y
```

For a patch release, checkout the existing release branch:

```bash
git checkout release/X.Y
git pull origin release/X.Y
```

### 2. Update Version and Changelog

1. Update the version in `pyproject.toml`:
   ```toml
   [project]
   version = "X.Y.Z"
   ```

2. Update `CHANGELOG.md`:
   - Move items from `[Unreleased]` to a new version section
   - Add the release date
   - Update the comparison links at the bottom

   Example:
   ```markdown
   ## [X.Y.Z] - YYYY-MM-DD

   ### Added
   - New feature description

   [X.Y.Z]: https://github.com/medley56/spicedocs-mcp/compare/PREVIOUS_TAG...X.Y.Z
   ```

3. Commit the changes:
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "Prepare release X.Y.Z"
   ```

### 3. Create and Push the Tag

```bash
# Create annotated tag
git tag -a X.Y.Z -m "Release X.Y.Z"

# Push the tag to trigger the release workflow
git push origin X.Y.Z
```

### 4. Merge Back to Main (for minor/major releases)

After tagging, merge the release branch back into main:

```bash
git checkout main
git pull origin main
git merge release/X.Y
git push origin main
```

### 5. Verify the Release

1. Check the [Actions tab](https://github.com/medley56/spicedocs-mcp/actions) to verify the release workflow completed
2. Verify the release appears in [Releases](https://github.com/medley56/spicedocs-mcp/releases)
3. Verify the release artifacts (wheel and tarball) are attached

## Pre-releases

Pre-release versions use suffixes like `-alpha`, `-beta`, or `-rc.N`:

- `1.0.0-alpha.1`
- `1.0.0-beta.1`
- `1.0.0-rc.1`

Tags not matching the `X.Y.Z` pattern are automatically marked as pre-releases in GitHub.

## Installing from a Release

Users can install specific versions:

```bash
# Install a specific version (recommended)
uvx --from git+https://github.com/medley56/spicedocs-mcp@1.0.0 spicedocs-mcp

# Using pip
pip install git+https://github.com/medley56/spicedocs-mcp@1.0.0
```

**Note:** Installing without a tag (e.g., `uvx --from git+https://github.com/medley56/spicedocs-mcp`) will install from the default branch, which may include unreleased changes. Always specify a version tag for production use.

## Release Workflow

The release is automated via GitHub Actions (`.github/workflows/release.yml`):

1. Triggered when a tag is pushed
2. Builds the Python package using `uv build`
3. Creates a GitHub release with auto-generated release notes
4. Uploads wheel and tarball artifacts to the release

## Hotfix Process

For critical fixes that need to be applied to an older release:

1. Checkout the release branch: `git checkout release/X.Y`
2. Cherry-pick or create the fix
3. Update version to next patch: e.g., if the previous version was `1.0.2`, update to `1.0.3`
4. Update CHANGELOG.md
5. Tag and push: `git tag -a 1.0.3 -m "Release 1.0.3" && git push origin 1.0.3`
6. Optionally cherry-pick the fix to `main` if applicable
