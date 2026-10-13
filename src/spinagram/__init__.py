"""spinagram — diagrams as code, rendered editable to SVG, PNG, PowerPoint and Figma."""
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

from .api import render, scenes
from .behavior import Activity, Flowchart, StateMachine
from .layout import build_scene
from .model import Diagram, Edge, Legend, Node, Table, Zone
from .theme import Theme
from .yaml_io import load

__all__ = ["Activity", "Diagram", "Flowchart", "StateMachine", "Edge", "Legend", "Node", "Table", "Zone", "Theme", "build_scene", "load", "render",
           "scenes"]
try:
    __version__ = _dist_version("spinagram")  # pyproject.toml is the only place the version is written
except PackageNotFoundError:  # source tree imported without being installed
    __version__ = "0+unknown"
