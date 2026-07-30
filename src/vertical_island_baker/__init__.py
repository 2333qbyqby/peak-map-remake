"""Procedural vertical-island terrain baker."""

from .config import BakeConfig, TerrainProfile
from .generator import bake_island

__all__ = ["BakeConfig", "TerrainProfile", "bake_island"]
__version__ = "0.1.0"

