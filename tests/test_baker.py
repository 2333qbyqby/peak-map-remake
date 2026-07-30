from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from vertical_island_baker.baker import export_bundle
from vertical_island_baker.config import BakeConfig
from vertical_island_baker.generator import bake_island
from vertical_island_baker.similarity import load_height, score_height_fields


def small_config(seed: int = 7, route_mode: str = "analyze") -> BakeConfig:
    return BakeConfig(
        seed=seed,
        resolution=65,
        obj_resolution=33,
        object_budget=80,
        route_mode=route_mode,
    )


class GeneratorTests(unittest.TestCase):
    def test_same_seed_is_deterministic(self) -> None:
        left = bake_island(small_config())
        right = bake_island(small_config())
        np.testing.assert_array_equal(left.height, right.height)
        self.assertEqual(left.objects, right.objects)
        self.assertEqual(left.route, right.route)

    def test_different_seed_changes_height(self) -> None:
        left = bake_island(small_config(seed=1))
        right = bake_island(small_config(seed=2))
        self.assertGreater(float(np.abs(left.height - right.height).mean()), 1e-4)
        self.assertLess(score_height_fields(left.height, right.height)["score_percent"], 90.0)

    def test_all_six_elevation_bands_exist(self) -> None:
        island = bake_island(small_config())
        ids = set(np.unique(island.biome_ids).tolist())
        self.assertTrue(set(range(6)).issubset(ids))
        self.assertIn(255, ids)
        self.assertEqual(len(island.config.band_names), 6)

    def test_repair_mode_adds_holds_for_flagged_steps(self) -> None:
        island = bake_island(small_config(route_mode="repair"))
        hold_count = sum(item["category"] == "route_repair" for item in island.objects)
        expected = sum(bool(point["needs_hold"]) for point in island.route)
        self.assertEqual(hold_count, expected)


class BundleTests(unittest.TestCase):
    def test_exported_bundle_is_complete_and_self_scores(self) -> None:
        island = bake_island(small_config())
        with tempfile.TemporaryDirectory() as temp:
            output = export_bundle(temp, island)
            required = {
                "height.png",
                "height.raw",
                "biomes.png",
                "materials.png",
                "normal.png",
                "occlusion.png",
                "config.json",
                "spawn_manifest.json",
                "route.json",
                "statistics.json",
                "terrain.obj",
                "preview.png",
                "preview_3d.png",
            }
            self.assertTrue(required.issubset({path.name for path in output.iterdir()}))
            height = load_height(output)
            score = score_height_fields(height, height)
            self.assertEqual(score["score_percent"], 100.0)
            self.assertTrue(score["passes_90_percent"])


class ValidationTests(unittest.TestCase):
    def test_even_resolution_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            BakeConfig(resolution=64)


if __name__ == "__main__":
    unittest.main()
