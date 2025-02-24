# Run notebooks

## Create virtual environment

Make sure that uv is installed (though it should work with only pip)

```sh
uv venv
source .venv/bin/activate
```

## Install dependencies

From the `notebooks` directory:

```sh
uv pip install -r requirements-nb.txt
```

## Start jupyterlab

```sh
jupyter lab
```

## Tables example

Uses polars, great tables, and itables to display a json data file.
