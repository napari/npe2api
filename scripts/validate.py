"""This script runs during fetch and checks the validity of the data.

If it fails, new data will not be pushed to main or released in the API.
here we can add any additional checks to prevent invalid data from being
published.
"""
import json
from pathlib import Path


PUBLIC = Path(__file__).parent.parent / "public"
MANIFESTS = PUBLIC / "manifest"

# now load each manifest build the indices (while verifying the manifest)
for mf_file in MANIFESTS.glob("*.json"):
    if mf_file.name == "errors.json":
        continue

    with mf_file.open() as f:
        data = json.load(f)

    assert data["name"]
    assert data["package_metadata"]["version"]
    contributions = data["contributions"]

    if not any(contributions.values()):
        print(f"⚠️  No contributions in {mf_file.name}")
        continue
