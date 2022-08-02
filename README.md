# how this repo works

1. [The fetch action](.github/workflows/fetch.yml) is triggered by:
    - any push to the `main` branch
    - a cron job every 10 minutes
    - a `workflow_dispatch` triggered manually from the [actions page](https://github.com/napari/npe2api/actions/workflows/fetch.yml)
    - TODO: a comment on an issue that says `please re-index` (or something like that)
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
4. Endpoints:
    - <https://npe2api.vercel.app/api/plugins>
        - map of {plugin_names -> version}
    - <https://npe2api.vercel.app/api/summary>
        - all basic plugin info needed to populate the plugin browser in napari
    - [https://npe2api.vercel.app/api/manifest/{plugin-name}](https://npe2api.vercel.app/api/manifest/napari-animation)
        - the full manifest for a given plugin
    - <https://npe2api.vercel.app/api/conda>
        - map of {pypi_name -> conda_channel/package_name}
    - [https://npe2api.vercel.app/api/conda/{plugin-name}](https://npe2api.vercel.app/api/conda/napari-animation)
        - conda info for a plugin. *name is pypi_name, not conda-name*
    - <https://npe2api.vercel.app/errors.json>
        - errors encountered during the last fetch
    - <https://npe2api.vercel.app/readers.json> *(example ... may change)*
        - lookup of filename pattern to reader

## local development

to run the next.js app locally:

```bash
git checkout https://github.com/napari/npe2api.git
cd npe2api
npm i
npm run dev
```
