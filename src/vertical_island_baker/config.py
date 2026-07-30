from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


@dataclass(frozen=True)
class TerrainProfile:
    """Rules for one elevation band.

    Names are deliberately generic. The project contains no game assets or
    extracted proprietary parameters.
    """

    name: str
    palette: tuple[int, int, int]
    relief: float
    roughness: float
    terrace: float
    large_density: float
    medium_density: float
    small_density: float
    vegetation_density: float
    hazard: str | None = None


PROFILES: dict[str, TerrainProfile] = {
    "coast": TerrainProfile(
        "coast", (218, 194, 135), 0.35, 0.25, 0.30, 0.45, 0.55, 0.35, 0.45
    ),
    "rainforest": TerrainProfile(
        "rainforest", (47, 111, 72), 0.78, 0.72, 0.12, 0.75, 0.85, 0.90, 1.00, "poison"
    ),
    "redwood": TerrainProfile(
        "redwood", (98, 73, 48), 0.68, 0.55, 0.18, 0.60, 0.70, 0.80, 1.00, "spiders"
    ),
    "alpine": TerrainProfile(
        "alpine", (214, 230, 235), 0.92, 0.78, 0.15, 1.00, 0.85, 0.65, 0.35, "cold"
    ),
    "mesa": TerrainProfile(
        "mesa", (191, 104, 62), 0.84, 0.48, 0.88, 0.95, 0.80, 0.60, 0.28, "heat"
    ),
    "caldera": TerrainProfile(
        "caldera", (66, 52, 48), 0.82, 0.82, 0.25, 1.00, 1.00, 0.90, 0.05, "lava"
    ),
    "kiln": TerrainProfile(
        "kiln", (90, 66, 58), 1.00, 0.90, 0.35, 0.85, 1.00, 1.00, 0.02, "heat"
    ),
    "summit": TerrainProfile(
        "summit", (113, 151, 83), 0.30, 0.20, 0.42, 0.20, 0.35, 0.45, 0.60
    ),
}


@dataclass
class BakeConfig:
    seed: int = 20260729
    resolution: int = 257
    world_size: float = 720.0
    world_height: float = 1200.0
    second_biome: Literal["rainforest", "redwood"] = "rainforest"
    third_biome: Literal["alpine", "mesa"] = "alpine"
    route_mode: Literal["analyze", "repair"] = "analyze"
    route_max_grade: float = 4.0
    obj_resolution: int = 129
    object_budget: int = 520
    sea_level: float = 0.015
    band_names: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        if self.resolution < 33 or self.resolution % 2 == 0:
            raise ValueError("resolution must be an odd integer >= 33")
        if self.obj_resolution < 17:
            raise ValueError("obj_resolution must be >= 17")
        if self.second_biome not in {"rainforest", "redwood"}:
            raise ValueError("second_biome must be rainforest or redwood")
        if self.third_biome not in {"alpine", "mesa"}:
            raise ValueError("third_biome must be alpine or mesa")
        self.band_names = (
            "coast",
            self.second_biome,
            self.third_biome,
            "caldera",
            "kiln",
            "summit",
        )

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["profiles"] = {name: asdict(PROFILES[name]) for name in self.band_names}
        return data


BAND_EDGES = (0.0, 0.13, 0.34, 0.56, 0.74, 0.91, 1.01)
