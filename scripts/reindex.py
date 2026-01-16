"""This is the main script that runs every 10 minutes (currently).

It processes and validates the data written to public/manifest from npe2 fetch
Then also searches conda and github for additional info.

See also scripts/bigquery.py, which runs ~every 2 hours, to double check the napari
classifier from the official public database (rather than parsing pypi.org html).
"""

import contextlib
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypedDict
from urllib import error, request

from packaging.utils import canonicalize_name
from packaging.version import Version

try:
    import conda
except ImportError:
    conda = None

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.pyapi import github  # noqa
from collections import defaultdict


PluginName = str


class SummaryDict(TypedDict):
    """Structure of dicts in index.json."""

    normalized_name: str
    name: str
    version: str
    display_name: str
    summary: str
    author: str
    license: str
    home_page: str
    project_url: list[str]
    pypi_versions: list[str]
    conda_versions: list[str]


HERE = Path(__file__)
# Path to the public directory in this repo
PUBLIC = HERE.parent.parent / "public"
# index of filename pattern to list of plugin names
READER_INDEX: defaultdict[str, list[PluginName]] = defaultdict(list)
# summary index, used plugin install widget list items
PYPI_INDEX: list["SummaryDict"] = []
# anaconda api
ANACONDA_ORG = "https://api.anaconda.org/package/{channel}/{package}"


def _normname(name: str, delim="-") -> str:
    """replace underscores and dots by `delim` and change to lowercase."""
    return re.sub(r"[-_.]+", delim, name).lower()


def repodatas(channel: str = "conda-forge") -> dict:
    from conda.core.subdir_data import SubdirData
    from conda.gateways.logging import initialize_logging
    from conda.models.channel import Channel

    initialize_logging()

    def repodata_inner(url):
        print(f"Fetching {url}...")
        subdir_data = SubdirData(Channel(url))
        return {
            f"{rec.subdir}/{rec.fn}": dict(rec.dump())
            for rec in subdir_data.iter_records()
        }

    subdirs = ("noarch", "linux-64", "osx-64", "osx-arm64", "win-64")
    urls = Channel(channel).urls(subdirs=subdirs)

    with ThreadPoolExecutor() as pool:
        index = {}
        for repo in pool.map(repodata_inner, urls):
            index.update(repo)

    SubdirData.clear_cached_local_channel_data()
    return index


def patch_api_data_with_repodata(data: dict[str, Any], repodata: dict):
    patched_files = []
    for package in data["files"].copy():
        # dependencies are available in a more useful way under `attrs`
        package.pop("dependencies", None)
        if repodata_record := repodata.get(package["basename"]):
            package["attrs"]["depends"] = tuple(repodata_record["depends"])
            package["attrs"]["constrains"] = tuple(repodata_record["constrains"])
        patched_files.append(package)
    data["files"] = patched_files


def conda_data(package_name, channel="conda-forge", repodata=None) -> tuple[str, dict]:
    """Try to fetch conda package data from anaconda.org.

    Will try package_name as provided, then lower-case with delimiters replaced by
    dashes, then lower-case with delimiters replaced by underscores.
    """
    print(f"conda {package_name}...")
    for name in (package_name, _normname(package_name), _normname(package_name, "_")):
        url = ANACONDA_ORG.format(channel=channel, package=name)
        with contextlib.suppress(error.HTTPError):
            with request.urlopen(url) as resp:
                data = json.load(resp)
                if repodata:
                    try:
                        patch_api_data_with_repodata(data, repodata)
                    except Exception as exc:
                        print(f"{package_name} -> {type(exc)}: {exc}", file=sys.stderr)
                data["builds"] = sorted(data["builds"])
                data["conda_platforms"] = sorted(data["conda_platforms"])
                return (package_name, data)
    return (package_name, {})


def conda_data_wrapper(args):
    return conda_data(*args)


if __name__ == "__main__":
    # the classifiers endpoint is populated by scripts/bigquery.py and it
    # contains the list of active versions on PyPI with the napari classifier -
    # we get the available versions from there to include in the summary
    CLASSIFIERS = PUBLIC / "classifiers.json"
    try:
        active_pypi_versions = json.loads(CLASSIFIERS.read_text())["active"]
    except Exception as exc:
        print(
            f"failed to retrieve active PyPI versions from {CLASSIFIERS}",
            file=sys.stderr,
        )
        print(f"{type(exc)}: {exc}", file=sys.stderr)
        active_pypi_versions = {}

    # load each manifest & build the indices (while verifying the manifest)
    for normalized_name, info in active_pypi_versions.items():
        name = info["name"]
        pypi_versions = info["pypi_versions"]

        manifest_file = Path(f"{PUBLIC}/manifest/{normalized_name}.json")
        if not manifest_file.exists():
            print(f"❌ {normalized_name} - no manifest found.")
            continue

        with manifest_file.open() as f:
            data = json.load(f)

        if data.get("visibility", "public") != "public":
            print(f"❌ {normalized_name} - not public.")
            continue

        # create the summary index item
        meta = data["package_metadata"]
        # the license may be null, in which case we check for the presence
        # of a 'license_expression` key in the PyPI info loaded from
        # the pypa warehouse XML-RPC API
        plugin_license = meta["license"]
        if not plugin_license:
            plugin_pypi_json_path = Path(f"{PUBLIC}/pypi/{normalized_name}.json")
            if plugin_pypi_json_path.exists():
                with plugin_pypi_json_path.open() as f:
                    plugin_pypi_json_info = json.load(f)
                    if license_expression := (
                        plugin_pypi_json_info.get("info", {}).get("license_expression")
                    ):
                        plugin_license = license_expression

        PYPI_INDEX.append(
            {
                "normalized_name": normalized_name,
                "name": name,
                "version": meta["version"],
                "display_name": data["display_name"],
                "summary": meta["summary"],
                "author": meta["author"],
                "license": plugin_license,
                "home_page": meta["home_page"],
                "project_url": meta["project_url"],
            }
        )

        # index contributions
        for contrib_type, contribs in data.get("contributions", {}).items():
            if not contribs:
                continue

            if contrib_type == "readers":
                for contrib in contribs:
                    for pattern in contrib["filename_patterns"]:
                        READER_INDEX[pattern].append(normalized_name)

    # sort things
    READER_INDEX = {  # type: ignore
        # sort reader index by filename pattern and sort the list of plugins
        # that provide each filename pattern
        k: sorted(v, key=str.lower)
        for k, v in sorted(READER_INDEX.items())
    }

    EXTENDED_SUMMARY = [
        {
            **pkg,
            "pypi_versions":
            # pypi versions are sorted before writing to classifiers.json
            active_pypi_versions.get(pkg["normalized_name"], {}).get(
                "pypi_versions", []
            ),
        }
        for pkg in PYPI_INDEX
    ]

    # now check conda for each package and write data to public/conda/{package}.json
    if not os.getenv("SKIP_CONDA") and (conda is not None):
        # output directory for conda info
        CONDA = PUBLIC / "conda"
        CONDA.mkdir(exist_ok=True)

        # conda summary, mapping from pypi package name to conda channel/name
        CONDA_INDEX: dict[str, str] = {}

        # fetch the index
        channel = "conda-forge"
        repodata = repodatas(channel)

        with ThreadPoolExecutor() as pool:
            data = dict(
                pool.map(
                    conda_data_wrapper,
                    ((i["name"], channel, repodata) for i in PYPI_INDEX),
                )
            )
        for package_name, info in data.items():
            normalized_name = canonicalize_name(package_name)
            CONDA_INDEX[normalized_name] = info.get("full_name")
            if not info:
                continue

            # pop ndownloads, since it makes for an unnecessarily noisy git history
            for file in info.get("files", []):
                file.pop("ndownloads", None)

            (CONDA / f"{normalized_name}.json").write_text(json.dumps(info, indent=2))

        # write summary map of pypi package name to conda channel/name
        (PUBLIC / "conda.json").write_text(json.dumps(CONDA_INDEX, indent=2))

        # update the main index (summary) with the conda versions
        # de-dupe and sort as in scripts/bigquery.py
        for pkg in EXTENDED_SUMMARY:
            versions = data.get(pkg["name"], {}).get("versions", [])
            pkg["conda_versions"] = sorted(set(versions), key=Version, reverse=True)

    # write out data to public locations
    (PUBLIC / "extended_summary.json").write_text(
        json.dumps(EXTENDED_SUMMARY, indent=2)
    )
    (PUBLIC / "readers.json").write_text(json.dumps(READER_INDEX))
    (PUBLIC / "index.json").write_text(
        json.dumps({x["normalized_name"]: x["version"] for x in PYPI_INDEX}, indent=2)
    )

    github.fetch_all_github_info()
