"""This script runs during fetch and checks the validity of the data.

If it fails, new data will not be pushed to main or released in the API.
here we can add any additional checks to prevent invalid data from being
published.
"""
import json
import logging
from pathlib import Path

import pytest


logger = logging.getLogger(__name__)


PUBLIC = Path(__file__).parent.parent / "public"
MANIFESTS = PUBLIC / "manifest"


@pytest.mark.parametrize(
    "mf_file",
    filter(lambda f: f != "errors.json", MANIFESTS.glob("*.json"))
)
def test_manifests_are_valid(mf_file):
    """load and verify each manifest"""
    with mf_file.open() as f:
        data = json.load(f)
    
    assert data["name"], "package has no name"
    assert data["package_metadata"]["version"], "package has no version"
    assert data["visibility"], "package has no visibility"
    contributions = data["contributions"]
    
    if not any(contributions.values()):
        logger.warning(f"⚠️  No contributions in {mf_file.name}")


def _get_summary_packages():
    with (PUBLIC / "summary.json").open() as f:
        data = json.load(f)
    return data


@pytest.mark.parametrize(
    "pkg",
    _get_summary_packages()
)
def test_summary_packages_parse_with_npe2(pkg):
    """test each summary package can be parsed into an npe2.PackageMetadata"""
    from npe2 import PackageMetadata
    pkg.pop("display_name", None)  # this is a hack because napari pops this value too
    try:
        PackageMetadata(**pkg)
    except Exception:
        raise AssertionError(f"failed to parse package '{pkg['name']}'")
