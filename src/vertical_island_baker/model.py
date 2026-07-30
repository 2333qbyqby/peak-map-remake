from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import BakeConfig


@dataclass
class BakedIsland:
    config: BakeConfig
    height: np.ndarray
    biome_ids: np.ndarray
    slope: np.ndarray
    occlusion: np.ndarray
    objects: list[dict[str, Any]]
    route: list[dict[str, float | int | bool]]
    statistics: dict[str, Any]

