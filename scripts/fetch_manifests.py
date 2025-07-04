"""
This replaces `npe2 fetch --all`, which relied on PyPI scraping to retrieve all packages with the
framework::napari classifier. This script instead gets information about active plugins from
`classifiers.json`, which is generated from the PyPI BigQuery data (source of truth) via
`bigquery.py`.

Much of this code is taken from `npe2._inspection._fetch`, where `npe2 fetch --all` was implemented.
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import TypedDict

from npe2 import fetch_manifest
from packaging.version import Version

PUBLIC = Path(__file__).parent.parent / "public"
MANIFEST_DIR = PUBLIC / "manifest"
CLASSIFIERS = PUBLIC / "classifiers.json"
ERRORS = PUBLIC / "errors.json"


def _latest_non_pre_release(versions: list[str]) -> str:
    for v in versions:
        if not Version(v).is_prerelease:
            return v
    return None


def _current_manifest_is_valid(name: str, version: str) -> bool:
    print(f"Checking {name} is valid?")
    try:
        existing_manifest = json.loads((MANIFEST_DIR / f"{name}.json").read_text())
        print(f"{name} manifest valid.")
        return existing_manifest["package_metadata"]["version"] == version
    except Exception:
        print(f"{name} manifest invalid.")
        return False


class ManifestError(TypedDict):
    name: str
    version: str
    error: str


def _try_fetch_and_write_manifest(normalized_name: str, classifiers_info: dict[str, str | list[str]]) -> ManifestError | None:
    pypi_versions = classifiers_info["pypi_versions"]
    version_to_fetch = _latest_non_pre_release(pypi_versions) or pypi_versions[0]

    if _current_manifest_is_valid(normalized_name, version_to_fetch):
        print(f"🟢 {normalized_name}")
        return None

    try:
        mf = fetch_manifest(normalized_name, version_to_fetch)
        print(f"Fetched manifest for {normalized_name}")
        (MANIFEST_DIR / f"{normalized_name}.json").write_text(
            # npe2 is using Pydantic v1, which doesn't support `model_dump_json`
            mf.json(exclude=set(), indent=2)
        )
        print(f"Manifest {normalized_name} written successfully.")
    except Exception as exc:
        print(f"❌ {normalized_name}")
        print(f"{type(exc)}: {exc}", file=sys.stderr)
        return ManifestError(
            name=normalized_name,
            version=version_to_fetch,
            error=str(exc),
        )
    else:
        print(f"✅ {normalized_name}")
        return None


if __name__ == "__main__":
    # the classifiers endpoint is populated by scripts/bigquery.py and it
    # contains the list of active versions on PyPI with the napari classifier -
    try:
        active_pypi_versions = json.loads(CLASSIFIERS.read_text())["active"]
    except Exception as exc:
        print(
            f"failed to retrieve active PyPI versions from {CLASSIFIERS}",
            file=sys.stderr,
        )
        print(f"{type(exc)}: {exc}", file=sys.stderr)
        raise SystemExit(1)
    
    if not MANIFEST_DIR.exists():
        MANIFEST_DIR.mkdir()

    # use processes instead of threads, because many of the subroutines in build
    # and setuptools use `os.chdir()`, which is not thread-safe (used in `fetch_manifest`)
    with ProcessPoolExecutor() as executor:
        errors = executor.map(
            _try_fetch_and_write_manifest,
            active_pypi_versions.keys(),
            active_pypi_versions.values(),
        )

    with open(ERRORS, "w") as f:
        json.dump({e.pop("name"): e for e in errors if e}, f, indent=2)
