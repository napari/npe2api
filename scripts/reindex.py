import json
from pathlib import Path
from typing import Dict, List, TypedDict, DefaultDict


class SummaryDict(TypedDict):
    """available at index.json"""

    name: str
    version: str
    display_name: str
    summary: str
    author: str
    license: str
    home_page: str


PUBLIC = Path(__file__).parent.parent / "public"
MANIFESTS = PUBLIC / "manifest"

CONTRIB_INDEX: DefaultDict[str, List[str]] = DefaultDict(list)
READER_INDEX: DefaultDict[str, List[str]] = DefaultDict(list)
INDEX: List[SummaryDict] = []

for mf_file in MANIFESTS.glob("*.json"):
    if mf_file.name == "errors.json":
        mf_file.rename(PUBLIC / "errors.json")
        continue

    with mf_file.open() as f:
        data = json.load(f)

    name = data["name"]
    meta = data["package_metadata"]
    INDEX.append(
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

    for contrib_type, contribs in data.get("contributions", {}).items():

        if not contribs:
            continue

        CONTRIB_INDEX[contrib_type].append(name)
        if contrib_type == "readers":
            for contrib in contribs:
                for pattern in contrib["filename_patterns"]:
                    READER_INDEX[pattern].append(name)


(PUBLIC / "index.json").write_text(json.dumps(INDEX))
(PUBLIC / "contributions.json").write_text(json.dumps(CONTRIB_INDEX))
(PUBLIC / "readers.json").write_text(json.dumps(READER_INDEX))
