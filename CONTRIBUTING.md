# Contributing to npe2api

Thank you for your interest in contributing to npe2api! This guide will help you get started with development and contributions.

## Overview

npe2api is the REST API used by napari to query plugins. It provides a fully static API hosted on Vercel that aggregates and serves metadata about napari plugins registered on PyPI.

## Development setup

### Prerequisites
- Node.js and npm
- Python 3.13+
- Git

### Getting started

1. Fork and clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/npe2api.git
cd npe2api
```

2. Install dependencies
```bash
# Install Node.js dependencies
npm install

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install Python package in editable mode with development dependencies
python -m pip install -e ".[dev]"
```

3. Run the development server
```bash
npm run dev
```

The API will be available at `http://localhost:3000`

## Development tasks

### Running Tests

Before submitting changes, ensure all tests pass:

```bash
# Run Python tests to validate manifest data
pytest tests/test_output.py

# Run Python linting and formatting
ruff check .        # Check for linting issues
ruff format .       # Format code

# Run JavaScript linting
npm run lint
```

### Executing scripts

For testing data collection locally:

```bash
# Find packages by classifier
python scripts/find_by_classifier.py

# Fetch manifests for plugins
python scripts/fetch_manifests.py

# Re-index and validate all plugin data
python scripts/reindex.py
```

### Making changes

#### API endpoints

The API endpoints are implemented in `pages/api/`:
- `plugins.js` - Plugin index
- `extended_summary.js` - Plugin summaries
- `conda.js` - Conda package mapping

#### Data processing scripts

Core scripts in `scripts/`:
- `find_by_classifier.py` - Queries BigQuery for napari plugins
- `fetch_manifests.py` - Downloads plugin manifests
- `reindex.py` - Validates and aggregates plugin data

## How this repo works

1. [The fetch action](.github/workflows/fetch.yml) is triggered by:
    - any push to the `main` branch
    - a cron job every 2 hours
    - a `workflow_dispatch` triggered manually from the [actions page](https://github.com/napari/npe2api/actions/workflows/fetch.yml)
2. When triggered, the fetch action
    1. installs `npe2`
    2. calls `npe2 fetch --all -o public/manifest` which
        - fetches all current napari plugin manifests
        - places them into the [`public/manifest`](public/manifest/) directory
        - records any fetch errors in [`public/manifest/errors.json`](public/errors.json)
    3. runs [`scripts/reindex.py`](scripts/reindex.py) which validates the manifests and builds any aggregates/indices.
    4. commits these changes to the `main` branch using [`git-auto-commit-action`](https://github.com/stefanzweifel/git-auto-commit-action)
3. This triggers vercel to build the (fully static) API and deploy to
   <https://npe2api.vercel.app>

### Development endpoints

 - <https://npe2api.vercel.app/api/plugins>
     - map of {plugin_names -> version}
 - <https://npe2api.vercel.app/api/extended_summary>
     - all basic plugin info needed to populate the plugin browser in napari
     - summary endpoint has been removed. Use extended_summary instead.
 - [https://npe2api.vercel.app/api/manifest/{plugin-name}](https://npe2api.vercel.app/api/manifest/napari-animation)
     - the full manifest for a given plugin
 - <https://npe2api.vercel.app/api/conda>
     - map of {pypi_name -> conda_channel/package_name}
 - [https://npe2api.vercel.app/api/pypi/{plugin-name}](https://npe2api.vercel.app/api/pypi/napari-animation)
     - PyPI info for a plugin.
 - [https://npe2api.vercel.app/api/conda/{plugin-name}](https://npe2api.vercel.app/api/conda/napari-animation)
     - conda info for a plugin. *name is pypi_name, not conda-name*
 - <https://npe2api.vercel.app/errors.json>
     - errors encountered during the last fetch
 - <https://npe2api.vercel.app/readers.json> *(example ... may change)*
     - lookup of filename pattern to reader

## Questions and issues

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- For questions, use the issue tracker or ask us on Zulip

## Additional resources

- [napari plugin documentation](https://napari.org/plugins/)
- [npe2 documentation](https://github.com/napari/npe2)

Thank you for contributing to npe2api!