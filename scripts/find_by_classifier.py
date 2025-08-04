import json
import sys
import xmlrpc.client
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Tuple
from urllib.error import HTTPError
from urllib.request import urlopen

from packaging.utils import canonicalize_name
from packaging.version import Version


PUBLIC = Path(__file__).parent.parent / "public"
PYPI_DIR = PUBLIC / "pypi"
PYPI_DIR.mkdir(exist_ok=True, parents=True)
CLASSIFIER = "Framework :: napari"

XML_RPC_MSG = """\
There was an error or unexpected response from PyPI XML-RPC API.
The XML-RPC API is unsupported and may have been deprecated.
See:
    https://warehouse.pypa.io/api-reference/xml-rpc.html#package-querying

See also:
    scripts/bigquery.py
    for an alternative method using BigQuery and the public metadata dataset

See also:
    https://github.com/pypi/warehouse/issues/16008
    for an issue with the BigQuery dataset that motivated the creation of this script
"""


def _validate_xmlrpc_browse_response(packages):
    assert isinstance(packages, list)
    assert all(isinstance(package, list) and len(package) == 2 for package in packages)
    assert all(
        isinstance(name, str) and isinstance(version, str) for name, version in packages
    )


def _find_by_classifier(classifier: str) -> dict[str, list[str]]:
    """Find all packages with a given classifier on PyPI.

    Returns a dictionary with package names as keys and a sorted list of versions as values.
    """
    try:
        with xmlrpc.client.ServerProxy("https://pypi.org/pypi") as client:
            packages = client.browse([classifier])
        _validate_xmlrpc_browse_response(packages)
    except Exception as e:
        print(e, sys.stderr)
        raise RuntimeError(XML_RPC_MSG)

    package_versions = {}
    for name, version in packages:
        assert isinstance(name, str) and isinstance(version, str), XML_RPC_MSG
        package_versions.setdefault(name, []).append(version)

    return {
        name: sorted(versions, key=Version, reverse=True)
        for name, versions in package_versions.items()
    }


def _fetch_packge_info(name: str) -> Tuple[str, str]:
    normalized_name = canonicalize_name(name)
    try:
        with urlopen(f"https://pypi.org/pypi/{name}/json") as f:
            info = json.load(f)
        (PYPI_DIR / f"{normalized_name}.json").write_text(json.dumps(info, indent=2))
    except HTTPError:
        return None
    return name, info


def _prune_yanked_versions(info, versions):
    releases = info["releases"] if info else {}
    return [
        version
        for version in versions
        if version in releases and not all(dist["yanked"] for dist in releases[version])
    ]


if __name__ == "__main__":
    all_packages_with_classifier = _find_by_classifier(CLASSIFIER)
    active = {}
    withdrawn = {}
    deleted = {}

    with ThreadPoolExecutor() as pool:
        icon = {
            "active": "✅",
            "withdrawn": "🔵",
            "deleted": "❌",
        }
        for name, info in pool.map(_fetch_packge_info, all_packages_with_classifier):
            normalized_name = canonicalize_name(name)
            status = "active"
            versions = _prune_yanked_versions(info, all_packages_with_classifier[name])

            if not versions:
                deleted[normalized_name] = versions
                status = "deleted"

            if status == "active" and CLASSIFIER not in info["info"].get(
                "classifiers", []
            ):
                withdrawn[normalized_name] = versions
                status = "withdrawn"

            if status == "active":
                active[normalized_name] = {
                    "name": name,
                    "pypi_versions": versions,
                }

            print(f"{icon[status]} {normalized_name}")
    
    for info_dict in [active, withdrawn, deleted]:
        # sort by normalized name
        info_dict = dict(sorted(info_dict.items()))

    output = {"active": active, "withdrawn": withdrawn, "deleted": deleted}
    (PUBLIC / "classifiers.json").write_text(json.dumps(output, indent=2))
