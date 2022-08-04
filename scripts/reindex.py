import contextlib
import json
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Tuple, TypedDict, Optional
import re
from urllib import request, error
import os
import sys

PluginName = str
ANACONDA_ORG = "https://api.anaconda.org/package/{channel}/{package}"


class SummaryDict(TypedDict):
    """available at index.json"""

    name: str
    version: str
    display_name: str
    summary: str
    author: str
    license: str
    home_page: str


# Path to the public directory in this repo
# Path to the public directory in this repo
PUBLIC = Path(__file__).parent.parent / "public"

# index of filename pattern to list of plugin names
READER_INDEX: DefaultDict[str, List[PluginName]] = DefaultDict(list)
# summary index, used plugin install widget list items
PYPI_INDEX: List[SummaryDict] = []


def _normname(name: str, delim="-") -> str:
    """replace underscores and dots by `delim` and change to lowercase."""
    return re.sub(r"[-_.]+", delim, name).lower()


def repodatas(channel: str = "conda-forge") -> Dict:
    from concurrent.futures import ThreadPoolExecutor
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
        repodata_record = repodata.get(package["basename"])
        if repodata_record:
            unpatched = package["attrs"]["depends"]
            package["attrs"]["depends"] = repodata_record["depends"]
            package["attrs"]["constrains"] = repodata_record["constrains"]
            if sorted(unpatched) != sorted(package["attrs"]["depends"]):
                print("Unpatched:")
                print(*unpatched, sep="\n")
                print("Patched:")
                print(*package["attrs"]["depends"], sep="\n")
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
                        print(f"{type(exc)}", file=sys.stderr)
                return (package_name, data)
    return (package_name, {})


def conda_data_wrapper(args):
    return conda_data(*args)


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


PYPI_INDEX = sorted(PYPI_INDEX, key=lambda x: x["name"].lower())
READER_INDEX = {k: sorted(v, key=str.lower) for k, v in sorted(READER_INDEX.items())}


# now check conda for each package and write data to public/conda/{package}.json
if not os.getenv("SKIP_CONDA"):
    from concurrent.futures import ThreadPoolExecutor

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


(PUBLIC / "summary.json").write_text(json.dumps(PYPI_INDEX, indent=2))
(PUBLIC / "readers.json").write_text(json.dumps(READER_INDEX))
(PUBLIC / "index.json").write_text(
    json.dumps({x["name"]: x["version"] for x in PYPI_INDEX}, indent=2)
)
