"""Find all napari plugins on PyPI and write their status to classifiers.json.

Candidate packages and versions come from the public PyPI BigQuery dataset
(`bigquery-public-data.pypi.distribution_metadata`). Each package is then checked
against the PyPI JSON API, which is authoritative for whether the package still
exists, which versions are yanked, and whether the latest release still has the
napari classifier.

Requires Google Cloud credentials, e.g. via GOOGLE_APPLICATION_CREDENTIALS.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from google.cloud import bigquery
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

PUBLIC = Path(__file__).parent.parent / "public"
PYPI_DIR = PUBLIC / "pypi"
CLASSIFIER = "Framework :: napari"
QUERY = """
SELECT
  name,
  ARRAY_AGG(DISTINCT version) AS versions
FROM `bigquery-public-data.pypi.distribution_metadata`
WHERE @classifier IN UNNEST(classifiers)
GROUP BY name
"""


def _sorted_versions(versions) -> list[str]:
    """De-dupe and sort versions in descending order, dropping unparseable ones."""
    valid = []
    for version in set(versions):
        try:
            Version(version)
        except InvalidVersion:
            print(f"  ⚠️ skipping invalid version {version!r}", file=sys.stderr)
            continue
        valid.append(version)
    return sorted(valid, key=Version, reverse=True)


def _find_by_classifier(classifier: str) -> dict[str, list[str]]:
    """Find all packages with a given classifier using the PyPI BigQuery dataset.

    Returns a dictionary with normalized package names as keys and a sorted list
    of versions as values.
    """
    client = bigquery.Client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("classifier", "STRING", classifier)
        ]
    )
    rows = client.query(QUERY, job_config=job_config).result()

    # the same project may appear under differently-cased/punctuated names
    # across releases, so merge versions by normalized name
    package_versions: dict[str, set[str]] = {}
    for name, versions in rows:
        package_versions.setdefault(canonicalize_name(name), set()).update(versions)

    return {
        name: _sorted_versions(versions) for name, versions in package_versions.items()
    }


def _fetch_package_info(normalized_name: str) -> tuple[str, dict | None]:
    try:
        with urlopen(f"https://pypi.org/pypi/{normalized_name}/json") as f:
            info = json.load(f)
    except HTTPError as e:
        if e.code == 404:
            return normalized_name, {}
        print(f"  ⚠️ HTTP {e.code} fetching {normalized_name}", file=sys.stderr)
        return normalized_name, None
    (PYPI_DIR / f"{normalized_name}.json").write_text(json.dumps(info, indent=2))
    return normalized_name, info


def _prune_yanked_versions(info, versions):
    releases = info["releases"] if info else {}
    return [
        version
        for version in versions
        if version in releases and not all(dist["yanked"] for dist in releases[version])
    ]


def main():
    PYPI_DIR.mkdir(exist_ok=True, parents=True)
    all_packages_with_classifier = _find_by_classifier(CLASSIFIER)
    if not all_packages_with_classifier:
        # never overwrite classifiers.json with an empty index
        raise RuntimeError(f"BigQuery returned no packages with {CLASSIFIER!r}")

    active = {}
    withdrawn = {}
    deleted = {}

    with ThreadPoolExecutor() as pool:
        icon = {
            "active": "✅",
            "withdrawn": "🔵",
            "deleted": "❌",
            "error": "⚠️",
        }
        for normalized_name, info in pool.map(
            _fetch_package_info, all_packages_with_classifier
        ):
            if info is None:
                print(f"{icon['error']} {normalized_name} (could not fetch info)")
                continue

            status = "active"
            versions = _prune_yanked_versions(
                info, all_packages_with_classifier[normalized_name]
            )

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
                    "name": info["info"]["name"],
                    "pypi_versions": versions,
                }

            print(f"{icon[status]} {normalized_name}")

    # sort by normalized name
    output = {
        "active": dict(sorted(active.items())),
        "withdrawn": dict(sorted(withdrawn.items())),
        "deleted": dict(sorted(deleted.items())),
    }
    (PUBLIC / "classifiers.json").write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
