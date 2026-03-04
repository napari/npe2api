"""
Find all napari plugins using the BigQuery public PyPI dataset.

NOTE: We currently use npe2api.find_by_classifier because it's been
historically faster and more reliable, but the XML-RPC API it uses
is deprecated, so that script will probably stop working eventually.

This script queries the official PyPI BigQuery public dataset for all packages
with the "Framework :: napari" classifier. This is the long-term preferred
method over XML-RPC as it uses the authoritative source of truth for PyPI
metadata.

The script fetches package information, validates the current classifier
status, and categorizes packages as active, withdrawn, or deleted.

Requires:
    Google Cloud credentials with access to BigQuery public datasets

Outputs:
    public/classifiers.json - Categorized plugin list with versions
    public/pypi/{package}.json - Individual package metadata

Usage:
    python -m npe2api.bigquery
"""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError

from google.cloud import bigquery
from packaging.utils import canonicalize_name
from packaging.version import Version

from ._network import urlopen_with_retry

PUBLIC = Path("public")
PYPI_DIR = PUBLIC / "pypi"
PYPI_DIR.mkdir(exist_ok=True, parents=True)
CLASSIFIER = "Framework :: napari"
QUERY = """
SELECT
  DISTINCT name,
  STRING_AGG(version) AS versions
FROM `bigquery-public-data.pypi.distribution_metadata`
WHERE "{}" IN UNNEST(classifiers)
GROUP BY name
"""

client = bigquery.Client()
query_job = client.query(QUERY.format(CLASSIFIER))
withdrawn = {}
deleted = {}
active = {
    canonicalize_name(k): {
        "name": k,
        # remove version dupes and sort in descending order
        "pypi_versions": sorted(set(v.split(",")), key=Version, reverse=True),
    }
    for k, v in query_job.result()
}


def _fetch_packge_info(normalized_name: str) -> tuple[str, str]:
    try:
        with urlopen_with_retry(f"https://pypi.org/pypi/{normalized_name}/json") as f:
            data = json.load(f)
    except (HTTPError, URLError) as e:
        print(f"✗ Failed to fetch {normalized_name}: {e}")
        return (normalized_name, "deleted")

    (PYPI_DIR / f"{normalized_name}.json").write_text(json.dumps(data, indent=2))

    if CLASSIFIER not in data["info"].get("classifiers", []):
        return (normalized_name, "withdrawn")
    return (normalized_name, "active")


with ThreadPoolExecutor() as pool:
    icon = {
        "active": "✅",
        "withdrawn": "🔵",
        "deleted": "❌",
    }
    for normalized_name, status in pool.map(_fetch_packge_info, active):
        print(f"{icon[status]} {normalized_name}")
        if status == "deleted":
            deleted[normalized_name] = active.pop(normalized_name)
        elif status == "withdrawn":
            withdrawn[normalized_name] = active.pop(normalized_name)

for info_dict in [active, withdrawn, deleted]:
    # sort by normalized name
    info_dict = dict(sorted(info_dict.items()))

output = {"active": active, "withdrawn": withdrawn, "deleted": deleted}
(PUBLIC / "classifiers.json").write_text(json.dumps(output, indent=2))
