from __future__ import annotations

import heapq
import math
from collections import Counter
from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter

from .config import BAND_EDGES, PROFILES, BakeConfig
from .model import BakedIsland
from .noise import domain_warp, fbm, normalized


def _smoothstep(edge0: float, edge1: float, values: np.ndarray) -> np.ndarray:
    t = np.clip((values - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _coordinate_grid(resolution: int) -> tuple[np.ndarray, np.ndarray]:
    axis = np.linspace(-1.0, 1.0, resolution, dtype=np.float64)
    return np.meshgrid(axis, axis)


def _make_base(
    config: BakeConfig, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x, z = _coordinate_grid(config.resolution)
    warped_x, warped_z = domain_warp(x, z, rng, amount=0.10)
    radius = np.sqrt((warped_x / 1.00) ** 2 + (warped_z / 0.92) ** 2)
    island = np.clip(1.0 - radius, 0.0, 1.0)

    # A broad radial mountain is quantized into six soft steps. This mirrors
    # the observed "base staircase + spawners" production idea without
    # copying proprietary meshes or parameters.
    cone = island**0.62
    steps = np.floor(cone * 6.0) / 6.0
    base = cone * 0.60 + steps * 0.40

    low = fbm(x.shape, rng, octaves=5, persistence=0.54)
    ridge_source = fbm(x.shape, rng, octaves=6, persistence=0.50)
    ridges = 1.0 - np.abs(ridge_source)
    details = fbm(x.shape, rng, octaves=4, persistence=0.46)

    biome_ids = np.full(x.shape, 255, dtype=np.uint8)
    inside = radius < 1.0
    for band_id, (lo, hi) in enumerate(zip(BAND_EDGES[:-1], BAND_EDGES[1:])):
        biome_ids[(cone >= lo) & (cone < hi) & inside] = band_id

    height = base.copy()
    for band_id, name in enumerate(config.band_names):
        profile = PROFILES[name]
        mask = biome_ids == band_id
        relief = (0.032 * low + 0.027 * ridges + 0.009 * details)
        relief *= profile.relief
        height[mask] += relief[mask]

        if profile.terrace > 0.5:
            quantized = np.round(height * 34.0) / 34.0
            height[mask] = (
                height[mask] * (1.0 - 0.46 * profile.terrace)
                + quantized[mask] * (0.46 * profile.terrace)
            )

    # Coast: a calmer beach shelf with scattered polygonal outcrops.
    coast = biome_ids == 0
    coast_flat = 0.035 + cone * 0.58 + low * 0.009
    height[coast] = height[coast] * 0.34 + coast_flat[coast] * 0.66

    # Caldera: an annular lava basin, punctured by noise-driven rock islands.
    caldera = biome_ids == 3
    lake_ring = np.exp(-((cone - 0.655) / 0.043) ** 2)
    rock_islands = np.clip((ridges - 0.70) * 4.2, 0.0, 1.0)
    height[caldera] -= (0.030 * lake_ring * (1.0 - 0.72 * rock_islands))[caldera]

    # Kiln: sharp internal volcanic ribs rather than a smooth cone.
    kiln = biome_ids == 4
    ribs = np.abs(np.sin(np.arctan2(z, x) * 8.0 + low * 2.0))
    height[kiln] += ((ribs - 0.48) * 0.026 + details * 0.012)[kiln]

    # Summit: readable final plateau.
    summit = biome_ids == 5
    summit_target = 0.925 + 0.075 * normalized(cone + low * 0.035)
    height[summit] = height[summit] * 0.35 + summit_target[summit] * 0.65

    height[radius >= 1.0] = config.sea_level
    height = np.clip(height, config.sea_level, 1.0)
    return height, biome_ids, x, z


def _surface_fields(config: BakeConfig, height: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    spacing = config.world_size / (config.resolution - 1)
    dz, dx = np.gradient(height * config.world_height, spacing, spacing)
    slope = np.sqrt(dx * dx + dz * dz)
    broad = gaussian_filter(height, sigma=max(1.0, config.resolution / 48.0))
    cavity = np.clip(broad - height, 0.0, None)
    occlusion = np.exp(-cavity * 22.0) * (1.0 - 0.12 * normalized(slope))
    return slope, np.clip(occlusion, 0.0, 1.0)


def _world_position(
    config: BakeConfig, height: np.ndarray, row: int, col: int
) -> tuple[float, float, float]:
    half = config.world_size / 2.0
    x = col / (config.resolution - 1) * config.world_size - half
    z = row / (config.resolution - 1) * config.world_size - half
    y = float(height[row, col] * config.world_height)
    return float(x), y, float(z)


def _object_kind(biome: str, category: str, rng: np.random.Generator) -> str:
    if category != "vegetation":
        return f"{category}_rock"
    vegetation = {
        "coast": ("palm", "beach_grass"),
        "rainforest": ("jungle_tree", "vine", "giant_root"),
        "redwood": ("redwood_tree", "shelf_fungus", "hanging_vine"),
        "alpine": ("pine", "winter_bush", "ice_spike"),
        "mesa": ("cactus", "dry_shrub", "stone_arch"),
        "caldera": ("lava_vent", "charred_stump"),
        "kiln": ("ember_vent", "hot_rock"),
        "summit": ("wildflowers", "summit_grass"),
    }
    return str(rng.choice(vegetation[biome]))


def _place_objects(
    config: BakeConfig,
    height: np.ndarray,
    biome_ids: np.ndarray,
    slope: np.ndarray,
    rng: np.random.Generator,
) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    placements_xz: dict[str, list[tuple[float, float]]] = {
        "large": [],
        "medium": [],
        "small": [],
        "vegetation": [],
    }
    category_scale = {
        "large": (11.0, 26.0),
        "medium": (5.0, 12.0),
        "small": (1.4, 5.5),
        "vegetation": (0.8, 2.5),
    }
    category_spacing = {"large": 24.0, "medium": 11.0, "small": 4.5, "vegetation": 5.0}

    weights: list[tuple[int, str, str, float]] = []
    for band_id, biome in enumerate(config.band_names):
        profile = PROFILES[biome]
        for category, density in (
            ("large", profile.large_density),
            ("medium", profile.medium_density),
            ("small", profile.small_density),
            ("vegetation", profile.vegetation_density),
        ):
            weights.append((band_id, biome, category, density))
    total_weight = sum(item[3] for item in weights)

    for band_id, biome, category, density in weights:
        target = max(1, round(config.object_budget * density / total_weight))
        mask = biome_ids == band_id
        if category == "vegetation":
            mask &= slope < (2.2 if biome in {"rainforest", "redwood"} else 1.35)
        elif category == "large":
            mask &= slope < 8.0
        else:
            mask &= slope < 12.0
        candidates = np.argwhere(mask)
        if not len(candidates):
            continue
        rng.shuffle(candidates)
        min_spacing = category_spacing[category]
        placed = 0
        for row, col in candidates:
            x, y, z = _world_position(config, height, int(row), int(col))
            if any(
                (x - px) ** 2 + (z - pz) ** 2 < min_spacing**2
                for px, pz in placements_xz[category]
            ):
                continue
            lo, hi = category_scale[category]
            scale = float(rng.uniform(lo, hi))
            kind = _object_kind(biome, category, rng)
            objects.append(
                {
                    "id": f"obj-{len(objects):04d}",
                    "kind": kind,
                    "category": category,
                    "biome": biome,
                    "position": [round(x, 3), round(y, 3), round(z, 3)],
                    "rotation_y": round(float(rng.uniform(0.0, 360.0)), 3),
                    "scale": [
                        round(scale * float(rng.uniform(0.68, 1.28)), 3),
                        round(scale * float(rng.uniform(0.72, 1.55)), 3),
                        round(scale * float(rng.uniform(0.68, 1.28)), 3),
                    ],
                }
            )
            placements_xz[category].append((x, z))
            placed += 1
            if placed >= target:
                break
    return objects


def _route(
    config: BakeConfig,
    height: np.ndarray,
    x: np.ndarray,
    z: np.ndarray,
) -> list[dict[str, float | int | bool]]:
    stride = max(1, (config.resolution - 1) // 64)
    rows = np.arange(0, config.resolution, stride)
    cols = np.arange(0, config.resolution, stride)
    if rows[-1] != config.resolution - 1:
        rows = np.append(rows, config.resolution - 1)
    if cols[-1] != config.resolution - 1:
        cols = np.append(cols, config.resolution - 1)
    h = height[np.ix_(rows, cols)]
    gx = x[np.ix_(rows, cols)]
    gz = z[np.ix_(rows, cols)]
    valid = h > config.sea_level + 0.004

    start_cost = gx * gx + (gz - 0.86) ** 2
    start_cost[~valid] = np.inf
    start = tuple(int(v) for v in np.unravel_index(np.argmin(start_cost), h.shape))
    end_cost = gx * gx + gz * gz - h * 0.06
    end_cost[~valid] = np.inf
    end = tuple(int(v) for v in np.unravel_index(np.argmin(end_cost), h.shape))

    dist = np.full(h.shape, np.inf)
    dist[start] = 0.0
    previous: dict[tuple[int, int], tuple[int, int]] = {}
    queue: list[tuple[float, tuple[int, int]]] = [(0.0, start)]
    spacing = config.world_size * stride / (config.resolution - 1)
    neighbors = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))

    while queue:
        current_dist, current = heapq.heappop(queue)
        if current == end:
            break
        if current_dist != dist[current]:
            continue
        r, c = current
        for dr, dc in neighbors:
            nr, nc = r + dr, c + dc
            if nr < 0 or nc < 0 or nr >= h.shape[0] or nc >= h.shape[1] or not valid[nr, nc]:
                continue
            horizontal = spacing * math.sqrt(dr * dr + dc * dc)
            delta_y = float((h[nr, nc] - h[r, c]) * config.world_height)
            grade = max(delta_y, 0.0) / max(horizontal, 1e-6)
            step_cost = horizontal * (1.0 + 0.055 * grade * grade) + max(-delta_y, 0.0) * 0.08
            candidate = current_dist + step_cost
            if candidate < dist[nr, nc]:
                dist[nr, nc] = candidate
                previous[(nr, nc)] = current
                heapq.heappush(queue, (candidate, (nr, nc)))

    if end not in previous:
        return []
    path = [end]
    while path[-1] != start:
        path.append(previous[path[-1]])
    path.reverse()

    route: list[dict[str, float | int | bool]] = []
    prior_position: tuple[float, float, float] | None = None
    for index, (r, c) in enumerate(path):
        full_row = int(rows[r])
        full_col = int(cols[c])
        position = _world_position(config, height, full_row, full_col)
        grade = 0.0
        if prior_position is not None:
            horizontal = math.hypot(position[0] - prior_position[0], position[2] - prior_position[2])
            grade = max(position[1] - prior_position[1], 0.0) / max(horizontal, 1e-6)
        route.append(
            {
                "index": index,
                "x": round(position[0], 3),
                "y": round(position[1], 3),
                "z": round(position[2], 3),
                "grade": round(grade, 4),
                "needs_hold": bool(grade > config.route_max_grade),
            }
        )
        prior_position = position
    return route


def _repair_route(
    config: BakeConfig,
    route: list[dict[str, float | int | bool]],
    objects: list[dict[str, Any]],
) -> None:
    if config.route_mode != "repair":
        return
    for point in route:
        if not bool(point["needs_hold"]):
            continue
        objects.append(
            {
                "id": f"route-hold-{int(point['index']):04d}",
                "kind": "climbing_hold_cluster",
                "category": "route_repair",
                "biome": "route",
                "position": [float(point["x"]), float(point["y"]), float(point["z"])],
                "rotation_y": 0.0,
                "scale": [2.0, 1.0, 2.0],
            }
        )


def bake_island(config: BakeConfig) -> BakedIsland:
    rng = np.random.default_rng(config.seed)
    height, biome_ids, x, z = _make_base(config, rng)
    slope, occlusion = _surface_fields(config, height)
    objects = _place_objects(config, height, biome_ids, slope, rng)
    route = _route(config, height, x, z)
    _repair_route(config, route, objects)

    route_grades = [float(point["grade"]) for point in route[1:]]
    statistics: dict[str, Any] = {
        "seed": config.seed,
        "height_min_m": round(float(height.min() * config.world_height), 3),
        "height_max_m": round(float(height.max() * config.world_height), 3),
        "mean_slope_grade": round(float(slope.mean()), 4),
        "object_count": len(objects),
        "object_categories": dict(Counter(str(item["category"]) for item in objects)),
        "biome_sequence": list(config.band_names),
        "route_points": len(route),
        "route_max_grade": round(max(route_grades, default=0.0), 4),
        "route_hold_segments": sum(bool(point["needs_hold"]) for point in route),
        "route_base_climbable_ratio": round(
            sum(grade <= config.route_max_grade for grade in route_grades)
            / max(len(route_grades), 1),
            4,
        ),
        "generation_mode": "controlled-chaos-with-hold-repair"
        if config.route_mode == "repair"
        else "controlled-chaos-analysis-only",
    }
    return BakedIsland(config, height, biome_ids, slope, occlusion, objects, route, statistics)
