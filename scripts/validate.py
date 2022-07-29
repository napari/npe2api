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

    contributions = data["contributions"]

    if not any(contributions.values()):
        print(f"No contributions in {mf_file.name}")
        continue

    if data["npe1_shim"]:
        print(f"npe1 shim in {mf_file.name}")