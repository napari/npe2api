"""This file includes python functions for accessing the public data.

Currently, it's not used anywhere, just for local interactive convenience.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import TypedDict

    from npe2 import PluginManifest

    Version = str
    PluginName = str

    class Plugins(TypedDict):
        active: dict[PluginName, list[Version]]
        withdrawn: dict[PluginName, list[Version]]
        deleted: dict[PluginName, list[Version]]


PUBLIC = Path(__file__).parent.parent.parent / "public"


def plugins() -> Plugins:
    """Return a dict of active, withdrawn, and deleted plugins."""
    return json.loads((PUBLIC / "classifiers.json").read_text())


def active_plugins() -> list[PluginName]:
    """Return a list of active plugins."""
    return plugins()["active"]


def manifest(name: PluginName) -> PluginManifest:
    """Return the npe2 manifest for a plugin."""
    from npe2 import PluginManifest

    if not (file := PUBLIC / "manifest" / f"{name}.json").exists():
        raise FileNotFoundError(f"No manifest at {file}")
    return PluginManifest.from_file(file)


def pypi_info(name: PluginName) -> dict:
    """Return the PyPI info for a plugin."""
    if not (file := PUBLIC / "pypi" / f"{name}.json").exists():
        raise FileNotFoundError(f"No pypi info at {file}")
    return json.loads(file.read_text())


def conda_info(name: PluginName) -> dict:
    """Return conda info for a plugin."""
    if not (file := PUBLIC / "conda" / f"{name}.json").exists():
        raise FileNotFoundError(f"No conda info at {file}")
    return json.loads(file.read_text())
