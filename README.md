# npe2api

The REST API used by [napari-hub.org](https://napari-hub.org) to query plugins.

The endpoint for the API is: <https://api.napari.org>

## Endpoints

| Type             | Endpoint                                                             | Note                                             |
|------------------|----------------------------------------------------------------------|--------------------------------------------------|
| Plugin index     | [/api/plugins](https://api.napari.org/api/plugins)                   |                                                  |
| Summary info     | [/api/extended_summary](https://api.napari.org/api/extended_summary) |                                                  |
| PyPI information |                                                                      | For an individual plugin: /api/pypi/{pypi_name}  |
| Conda index      | [/api/conda](https://api.napari.org/api/conda)                       | For an individual plugin: /api/conda/{pypi_name} |
| Fetch errors     | [/errors.json](https://api.napari.org/errors.json)                   |                                                  |
| manifests        | For an individual manifest: /api/manifest/{plugin_name}              |                                                  |

## Development

### Prerequisites

- **[Conda/Miniconda](https://docs.conda.io/en/latest/miniconda.html)**
  - conda is required for the reindex script to fetch conda package metadata
- **Python 3.12+**
- **Cloudflare account** with R2 and Workers enabled

### Setup

1. **Install conda/miniconda** if not already installed

2. **Clone the repository**
   ```bash
   git clone https://github.com/napari/npe2api.git
   cd npe2api
   ```

3. **Create environment and install dependencies**
   ```bash
   # Create conda environment
   conda create -n npe2api python=3.12
   conda activate npe2api

   # Install conda Python package (required for reindex script)
   conda install conda

   # Install package with pipeline dependencies
   pip install -e .[pipeline]
   ```

4. **Configure credentials** (for local testing)
   ```bash
   cp .env.example .env
   # Edit .env with your Cloudflare credentials
   ```

### Running the data pipeline

```bash
# Find plugins by classifier
python -m npe2api.find_by_classifier

# Fetch manifests
python -m npe2api.fetch_manifests

# Reindex and generate summary data
python -m npe2api.reindex

# Upload to R2
python -m npe2api.upload_to_r2
```

### Deployment

The API is served by `worker.py`, a FastAPI application deployed to Cloudflare Workers. The worker handles:
- Name normalization for plugin manifest routes
- Dynamic shields.io badge generation
- Pass-through requests to R2 object storage for all API endpoints

For production deployment, the data pipeline modules generate JSON files that are uploaded to R2, and the worker serves them via the public API.

### Local worker development

```bash
# Install pywrangler (Python wrapper for wrangler, cloudflare's worker CLI)
pip install workers-py

# Generate wrangler config
python -m npe2api.wrangler_config --prod

# Run worker locally (connects to remote R2 bucket)
pywrangler dev

# Generate preview wrangler config
python -m npe2api.wrangler_config --preview \<env_name\>

# Deploy *preview* version to Cloudflare Workers (connects to remote R2 bucket)
pywrangler deploy --env \<env_name\>
```

## Contributing

If you are interested in contributing to this repo, see the [CONTRIBUTING.md](./CONTRIBUTING.md) page.

## Code of conduct

`npe2api` is maintained by the [napari](https://napari.org/) community. The `napari` community has a [Code of Conduct](https://napari.org/dev/community/code_of_conduct.html) that should be honored by everyone who participates in the `napari` community.
