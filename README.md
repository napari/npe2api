# how this repo works

1. [The fetch action](.github/workflows/fetch.yml) is triggered by:
    - any push to the `main` branch
    - a cron job every 5 minutes
    - a `workflow_dispatch` triggered manually from the [actions page](https://github.com/tlambert03/npe2api/actions/workflows/fetch.yml)
    - TODO: a comment on an issue that says `please re-index` (or something like that)
2. When triggered, the fetch action
    1. installs `npe2`
    2. calls `npe2 fetch --all -o public/manifest` which
        - fetches all current napari plugin manifests
        - places them into the [`public/manifest`](public/manifest/) directory
        - records any fetch errors in [`public/manifest/errors.json`](public/manifest/errors.json)
    3. runs [`scripts/reindex.py`](scripts/reindex.py) which validates teh manifests and builds any aggregates/indices.
    3. commits these changes to the `main` branch using [`git-auto-commit-action`](https://github.com/stefanzweifel/git-auto-commit-action)
3. This triggers vercel to build the (fully static) API and deploy to
   https://npe2-talley.vercel.app
3. Endpoints:
    - https://npe2-talley.vercel.app/api/plugins
        - all basic plugin info needed to populate the plugin browser in napari
    - [https://npe2-talley.vercel.app/api/manifest/{plugin-name}](https://npe2-talley.vercel.app/api/manifest/napari-animation)
        - the full manifest for a given plugin
    - https://npe2-talley.vercel.app/errors.json *(temporary)*
        - errors encountered during the last fetch
    - https://npe2-talley.vercel.app/readers.json *(temporary)*
        - lookup of filename pattern to reader

## local development

to run the next.js app locally:

```bash
git checkout https://github.com/tlambert03/npe2api.git
cd npe2api
npm i
npm run dev
```
