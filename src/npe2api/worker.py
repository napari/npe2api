"""
Cloudflare Worker for npe2api - FastAPI server and CloudFlare Workers entrypoint.

This module serves as the entrypoint for remote deployment on Cloudflare Workers.
It implements a FastAPI application that handles API requests and serves data from
R2 object storage.

Key Features:
- FastAPI server with Pyodide/Workers integration
- Name normalization for /api/manifest/{slug} routes (PyPI canonical names)
- Dynamic shields.io badge generation for /api/shields/{slug}
- Pass-through to R2 for all other routes (plugins, conda, pypi metadata)
- Automatic response caching via Cloudflare Cache API

Deployment:
    This file is deployed to Cloudflare Workers using pywrangler/wrangler.
    See wrangler_config.py for configuration generation.

Local Development:
    python -m npe2api.wrangler_config
    pywrangler dev

Endpoints:
    /api/manifest/{plugin_name} - Plugin manifest with name normalization
    /api/shields/{slug} - shields.io badge schema
    /api/plugins - Plugin index
    /api/extended_summary - Extended plugin summary
    /api/conda - Conda package index
    /api/pypi/{package} - PyPI metadata
    /errors.json - Fetch errors
"""

import json
import sys
import traceback

import _index_html
import _napari_svg
from fastapi import FastAPI
from fastapi import Request as FastAPIRequest
from fastapi import Response as FastAPIResponse
from fastapi.responses import HTMLResponse, JSONResponse
from js import Request, caches
from packaging.utils import canonicalize_name
from pyodide.ffi import create_proxy
from workers import WorkerEntrypoint


def log_info(msg: str, **kwargs):
    """Log info messages to stdout."""
    print(json.dumps({"message": msg, **kwargs}), flush=True)


def log_error(msg: str, **kwargs):
    """Log error messages to stderr."""
    print(json.dumps({"message": msg, **kwargs}), file=sys.stderr, flush=True)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        cache_url = request.url

        cache_key = Request.new(cache_url)
        cache = caches.default

        # Check whether the value is already available in the cache
        # if not, you will need to fetch it from origin, and store it in the cache
        response = await cache.match(cache_key)

        if response is None:
            log_info("Cache miss, fetching and caching request", url=request.url)
            # If not in cache, pass through to the FastAPI app
            import asgi

            response = await asgi.fetch(app, request.js_object, self.env)

            # Store in cache (expiry controlled by Cache-Control headers from FastAPI)
            self.ctx.waitUntil(create_proxy(cache.put(cache_key, response.clone())))
        else:
            log_info("Cache hit", url=request.url)

        return response


app = FastAPI()


@app.exception_handler(Exception)
async def global_exception_handler(request: FastAPIRequest, exc: Exception):
    """Catch all exceptions and return detailed error info."""
    error_detail = {
        "error": str(exc),
        "type": type(exc).__name__,
        "traceback": traceback.format_exc(),
    }
    log_error("Unhandled exception", **error_detail)
    return JSONResponse(
        status_code=500,
        content=error_detail,
    )


async def get_from_r2(request: FastAPIRequest, key: str) -> FastAPIResponse:
    """
    Fetch object from R2 and return as HTTP response.

    Args:
        request: FastAPI request object (to access env)
        key: R2 object key

    Returns:
        Response with content and appropriate headers
    """
    env = request.scope.get("env")
    if env is None:
        raise RuntimeError("env not found in request.scope - R2 not available")

    # API allows specifying files without .json extension
    # Try with .json first since most files have that extension
    if not key.endswith(".json"):
        obj = await env.BUCKET.get(f"{key}.json")
    else:
        obj = None

    # Try again without .json extension if not found
    if not obj:
        obj = await env.BUCKET.get(key)

    if not obj:
        return FastAPIResponse(
            content='{"error": "Not found"}',
            status_code=404,
            media_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    content = await obj.text()

    media_type = "application/json"
    if key.endswith(".html"):
        media_type = "text/html"

    return FastAPIResponse(
        content=content,
        media_type=media_type,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
            "ETag": obj.httpEtag,
        },
    )


@app.get("/api/shields/{slug:path}")
async def get_shields_badge(slug: str, request: FastAPIRequest):
    """
    Generate shields.io badge schema for a plugin.

    Returns different badge based on whether plugin exists in the index.
    Normalizes the slug to match PyPI canonical names.
    """
    normalized = canonicalize_name(slug)

    env = request.scope["env"]
    obj = await env.BUCKET.get("index.json")

    shield_schema = {
        "color": "#82001A",
        "label": "napari hub",
        "logoSvg": _napari_svg.NAPARI_LOGO_SVG,
        "message": "unavailable",
        "schemaVersion": 1,
        "style": "flat-square",
    }

    if obj:
        content = await obj.text()
        plugins = json.loads(content)

        if normalized in plugins:
            shield_schema["color"] = "#0074B8"
            # Use original slug, not normalized
            shield_schema["message"] = slug

    return JSONResponse(
        content=shield_schema,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=3600",
        },
    )


@app.get("/api/plugins")
async def get_plugins(request: FastAPIRequest):
    return await get_from_r2(request, "index.json")


@app.get("/api/extended_summary")
async def get_extended_summary(request: FastAPIRequest):
    return await get_from_r2(request, "extended_summary.json")


@app.get("/api/readers")
async def get_readers(request: FastAPIRequest):
    return await get_from_r2(request, "readers.json")


@app.get("/api/conda")
async def get_conda_index(request: FastAPIRequest):
    return await get_from_r2(request, "conda.json")


@app.get("/api/conda/{plugin_name:path}")
async def get_conda_package(plugin_name: str, request: FastAPIRequest):
    return await get_from_r2(request, f"conda/{plugin_name}")


@app.get("/api/pypi/{plugin_name:path}")
async def get_pypi_package(plugin_name: str, request: FastAPIRequest):
    return await get_from_r2(request, f"pypi/{plugin_name}")


@app.get("/api/manifest/{plugin_name:path}")
async def get_manifest(plugin_name: str, request: FastAPIRequest):
    """
    Get plugin manifest with name normalization.

    Handles names like "My_Plugin.Name" by normalizing to "my-plugin-name".
    Uses packaging.utils.canonicalize_name which matches PyPI's normalization.
    """
    normalized = canonicalize_name(plugin_name)
    r2_key = f"manifest/{normalized}"

    return await get_from_r2(request, r2_key)


@app.get("/{full_path:path}")
async def catch_all(full_path: str, request: FastAPIRequest):
    """
    Catch-all route for paths not handled by specific API routes.

    Handles:
    - / (root) - generates dynamic index.html
    - /errors.json, index.json, etc. - top-level files
    """
    # Handle root path - generate dynamic index.html
    if not full_path or full_path == "/":
        env = request.scope.get("env")
        if env is None:
            raise RuntimeError("env not found in request.scope - R2 not available")

        html_content = await _index_html.generate_index_html(env)
        return HTMLResponse(
            content=html_content,
            headers={
                "Cache-Control": "public, max-age=3600",
            },
        )

    return await get_from_r2(request, full_path)
