import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Tuple
from urllib.error import HTTPError
from urllib.request import urlopen

from packaging.version import Version
from google.cloud import bigquery

from utils import normalize_name

PUBLIC = Path(__file__).parent.parent / "public"
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
    normalize_name(k) : {
        "name": k,
        # remove version dupes and sort in descending order
        "pypi_versions": sorted(set(v.split(",")), key=Version, reverse=True)
    }
    for k, v in sorted(query_job.result(), key=lambda x: x[0].lower())
}


def _fetch_packge_info(normalized_name: str) -> Tuple[str, str]:
    try:
        with urlopen(f"https://pypi.org/pypi/{normalized_name}/json") as f:
            data = json.load(f)
    except HTTPError:
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

output = {"active": active, "withdrawn": withdrawn, "deleted": deleted}
(PUBLIC / "classifiers.json").write_text(json.dumps(output, indent=2))
