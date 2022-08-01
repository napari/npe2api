import json
from pathlib import Path
from typing import DefaultDict, List, TypedDict

PluginName = str


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

# index of filename pattern to list of plugin names
READER_INDEX: DefaultDict[str, List[PluginName]] = DefaultDict(list)
# summary index, used plugin install widget list items
INDEX: List[SummaryDict] = []

# now load each manifest build the indices (while verifying the manifest)
for mf_file in MANIFESTS.glob("*.json"):
    # move the errors file to top /public folder
    if mf_file.name == "errors.json":
        mf_file.rename(PUBLIC / "errors.json")
        continue

    with mf_file.open() as f:
        data = json.load(f)

    # create the summary index item
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

    # index contributions
    for contrib_type, contribs in data.get("contributions", {}).items():

        if not contribs:
            continue

        if contrib_type == "readers":
            for contrib in contribs:
                for pattern in contrib["filename_patterns"]:
                    READER_INDEX[pattern].append(name)

INDEX = sorted(INDEX, key=lambda x: x["name"].lower())
READER_INDEX = dict(sorted(READER_INDEX.items()))

(PUBLIC / "summary.json").write_text(json.dumps(INDEX, indent=2))
(PUBLIC / "readers.json").write_text(json.dumps(READER_INDEX))
(PUBLIC / "index.json").write_text(
    json.dumps({x["name"]: x["version"] for x in INDEX}, indent=2)
)
