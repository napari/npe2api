# npe2api

[![vercel](https://img.shields.io/github/deployments/napari/npe2api/production?label=vercel&logo=vercel&style=flat-square)](https://api.napari.org)

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

## Contributing

If you are interested in contributing to this repo, see the [CONTRIBUTING.md](./CONTRIBUTING.md) page.