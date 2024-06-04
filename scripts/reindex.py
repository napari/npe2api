"""This is the main script that runs every 10 minutes (currently).

It processes and validates the data written to public/manifest from npe2 fetch
Then also searches conda and github for additional info.

See also scripts/bigquery.py, which runs ~every 2 hours, to double check the napari
classifier from the official public database (rather than parsing pypi.org html).
"""
import contextlib
import json
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Tuple, TypedDict
import re
from urllib import request, error
import os
import sys
from concurrent.futures import ThreadPoolExecutor

from packaging.version import Version

try:
    import conda
except ImportError:
    conda = None

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.pyapi import github  # noqa


PluginName = str


class SummaryDict(TypedDict):
    """Structure of dicts in index.json."""

    name: str
    version: str
    display_name: str
    summary: str
    author: str
    license: str
    home_page: str
    pypi_versions: List[str]
    conda_versions: List[str]


HERE = Path(__file__)
# Path to the public directory in this repo
PUBLIC = HERE.parent.parent / "public"
# index of filename pattern to list of plugin names
READER_INDEX: DefaultDict[str, List[PluginName]] = DefaultDict(list)
# summary index, used plugin install widget list items
PYPI_INDEX: List["SummaryDict"] = []
# anaconda api
ANACONDA_ORG = "https://api.anaconda.org/package/{channel}/{package}"


def _normname(name: str, delim="-") -> str:
    """replace underscores and dots by `delim` and change to lowercase."""
    return re.sub(r"[-_.]+", delim, name).lower()


def repodatas(channel: str = "conda-forge") -> Dict:
    from conda.models.channel import Channel
    from conda.core.subdir_data import SubdirData
    from conda.gateways.logging import initialize_logging

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


def patch_api_data_with_repodata(data: Dict[str, Any], repodata: Dict):
    patched_files = []
    for package in data["files"].copy():
        # dependencies are available in a more useful way under `attrs`
        package.pop("dependencies", None)
        if repodata_record := repodata.get(package["basename"]):
            package["attrs"]["depends"] = tuple(repodata_record["depends"])
            package["attrs"]["constrains"] = tuple(repodata_record["constrains"])
        patched_files.append(package)
    data["files"] = patched_files


def conda_data(package_name, channel="conda-forge", repodata=None) -> Tuple[str, dict]:
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
    for mf_file in (PUBLIC / "manifest").glob("*.json"):
        # move the errors file to top /public folder
        if mf_file.name == "errors.json":
            mf_file.rename(PUBLIC / "errors.json")
            continue

        with mf_file.open() as f:
            data = json.load(f)

        # create the summary index item
        name = data["name"]
        meta = data["package_metadata"]
        PYPI_INDEX.append(
            {
                "name": name,
                "version": meta["version"],
                "display_name": data["display_name"],
                "visibility": data["visibility"],
                "summary": meta["summary"],
                "author": meta["author"],
                "license": meta["license"],
                "home_page": meta["home_page"],
            }
        )

        # index contributions
        for contrib_type, contribs in data.get("contributions", {}).items():

            if not contribs:
                continue

            if contrib_type == "readers":
                for contrib in contribs:
                    for pattern in contrib["filename_patterns"]:
                        READER_INDEX[pattern].append(name)

    # sort things
    PYPI_INDEX = sorted(PYPI_INDEX, key=lambda x: x["name"].lower())
    READER_INDEX = {  # type: ignore
        k: sorted(v, key=str.lower) for k, v in sorted(READER_INDEX.items())
    }

    EXTENDED_SUMMARY = [
        {
            **pkg,
            "pypi_versions": sorted(
                vs, key=Version, reverse=True
            ),
        }
        for pkg in PYPI_INDEX if len(vs := active_pypi_versions.get(pkg["name"], []) > 0)
    ]

    # now check conda for each package and write data to public/conda/{package}.json
    if not os.getenv("SKIP_CONDA") and (conda is not None):
        # output directory for conda info
        CONDA = PUBLIC / "conda"
        CONDA.mkdir(exist_ok=True)

        # conda summary, mapping from pypi package name to conda channel/name
        CONDA_INDEX: Dict[str, str] = {}

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
            CONDA_INDEX[package_name] = info.get("full_name")
            if not info:
                continue

            # pop ndownloads, since it makes for an unnecessarily noisy git history
            for file in info.get("files", []):
                file.pop("ndownloads", None)

            (CONDA / f"{package_name}.json").write_text(json.dumps(info, indent=2))

        # write summary map of pypi package name to conda channel/name
        (PUBLIC / "conda.json").write_text(json.dumps(CONDA_INDEX, indent=2))

        # update the main index (summary) with the conda versions
        # de-dupe and sort as in scripts/bigquery.py
        for pkg in EXTENDED_SUMMARY:
            versions = data.get(pkg["name"], {}).get("versions", [])
            pkg["conda_versions"] = sorted(set(versions), key=Version, reverse=True)

    # write out data to public locations
    (PUBLIC / "summary.json").write_text(json.dumps(PYPI_INDEX, indent=2))
    (PUBLIC / "extended_summary.json").write_text(
        json.dumps(EXTENDED_SUMMARY, indent=2)
    )
    (PUBLIC / "readers.json").write_text(json.dumps(READER_INDEX))
    (PUBLIC / "index.json").write_text(
        json.dumps({x["name"]: x["version"] for x in PYPI_INDEX}, indent=2)
    )

    github.fetch_all_github_info()
