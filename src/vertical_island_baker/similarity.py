from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, zoom


def load_height(path: str | Path) -> np.ndarray:
    source = Path(path)
    if source.is_dir():
        source = source / "height.png"
    values = np.asarray(Image.open(source), dtype=np.float64)
    if values.ndim == 3:
        values = values[..., :3].mean(axis=2)
    lo, hi = float(values.min()), float(values.max())
    return (values - lo) / max(hi - lo, 1e-12)


def _resize(values: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    if values.shape == shape:
        return values
    factors = (shape[0] / values.shape[0], shape[1] / values.shape[1])
    return zoom(values, factors, order=1, mode="nearest")[: shape[0], : shape[1]]


def _orientations(values: np.ndarray) -> list[np.ndarray]:
    candidates: list[np.ndarray] = []
    for turns in range(4):
        rotated = np.rot90(values, turns)
        candidates.append(rotated)
        candidates.append(np.fliplr(rotated))
    return candidates


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    aa = a - a.mean()
    bb = b - b.mean()
    denom = float(np.linalg.norm(aa) * np.linalg.norm(bb))
    if denom < 1e-12:
        return 1.0 if np.allclose(a, b) else 0.0
    return float(np.clip(np.sum(aa * bb) / denom, -1.0, 1.0))


def score_height_fields(generated: np.ndarray, reference: np.ndarray) -> dict[str, Any]:
    reference = _resize(reference, generated.shape)
    oriented = _orientations(generated)
    correlations = [_corr(candidate, reference) for candidate in oriented]
    orientation = int(np.argmax(correlations))
    aligned = oriented[orientation]

    # Least-squares scale and offset make the metric insensitive to engine
    # unit conversion while preserving shape.
    design = np.stack((aligned.ravel(), np.ones(aligned.size)), axis=1)
    scale, offset = np.linalg.lstsq(design, reference.ravel(), rcond=None)[0]
    fitted = np.clip(aligned * scale + offset, 0.0, 1.0)
    height_rmse = float(np.sqrt(np.mean((fitted - reference) ** 2)))
    # An exponential tolerance prevents two broadly conical islands from
    # receiving a misleading >90 score when their local geometry differs.
    height_score = float(np.exp(-height_rmse / 0.10))

    gy, gx = np.gradient(fitted)
    ry, rx = np.gradient(reference)
    numerator = gx * rx + gy * ry
    denominator = np.sqrt(gx * gx + gy * gy) * np.sqrt(rx * rx + ry * ry)
    cosine = np.ones_like(numerator)
    np.divide(numerator, denominator, out=cosine, where=denominator > 1e-9)
    direction_score = float(np.mean((np.clip(cosine, -1.0, 1.0) + 1.0) / 2.0))
    generated_magnitude = np.sqrt(gx * gx + gy * gy)
    reference_magnitude = np.sqrt(rx * rx + ry * ry)
    magnitude_error = float(np.mean(np.abs(generated_magnitude - reference_magnitude)))
    magnitude_score = float(
        np.exp(-magnitude_error / max(float(reference_magnitude.mean()) + 0.005, 1e-6))
    )
    gradient_score = math.sqrt(direction_score * magnitude_score)

    gen_mask = fitted > 0.02
    ref_mask = reference > 0.02
    union = np.logical_or(gen_mask, ref_mask).sum()
    silhouette_score = float(np.logical_and(gen_mask, ref_mask).sum() / max(int(union), 1))

    scale_scores = []
    detail_scores = []
    for sigma in (2.0, 5.0, 11.0):
        scale_scores.append((_corr(gaussian_filter(fitted, sigma), gaussian_filter(reference, sigma)) + 1.0) / 2.0)
        detail_scores.append(
            (_corr(fitted - gaussian_filter(fitted, sigma), reference - gaussian_filter(reference, sigma)) + 1.0)
            / 2.0
        )
    multiscale_score = float(np.mean(scale_scores))
    detail_score = float(np.mean(detail_scores))

    generated_hist, _ = np.histogram(fitted, bins=32, range=(0.0, 1.0), density=True)
    reference_hist, _ = np.histogram(reference, bins=32, range=(0.0, 1.0), density=True)
    generated_hist /= max(generated_hist.sum(), 1e-12)
    reference_hist /= max(reference_hist.sum(), 1e-12)
    distribution_score = float(1.0 - 0.5 * np.abs(generated_hist - reference_hist).sum())

    weights = {
        "height": 0.30,
        "gradient": 0.20,
        "silhouette": 0.08,
        "multiscale": 0.14,
        "distribution": 0.08,
        "detail": 0.20,
    }
    total = (
        height_score * weights["height"]
        + gradient_score * weights["gradient"]
        + silhouette_score * weights["silhouette"]
        + multiscale_score * weights["multiscale"]
        + distribution_score * weights["distribution"]
        + detail_score * weights["detail"]
    )
    return {
        "score_percent": round(total * 100.0, 3),
        "passes_90_percent": bool(total >= 0.90),
        "orientation_index": orientation,
        "alignment_scale": round(float(scale), 6),
        "alignment_offset": round(float(offset), 6),
        "components": {
            "height": round(height_score * 100.0, 3),
            "gradient": round(gradient_score * 100.0, 3),
            "silhouette": round(silhouette_score * 100.0, 3),
            "multiscale": round(multiscale_score * 100.0, 3),
            "distribution": round(distribution_score * 100.0, 3),
            "detail": round(detail_score * 100.0, 3),
        },
        "weights": weights,
        "height_rmse_normalized": round(height_rmse, 6),
    }


def _manifest_features(bundle: Path) -> dict[str, Any] | None:
    manifest_path = bundle / "spawn_manifest.json"
    config_path = bundle / "config.json"
    if not manifest_path.exists() or not config_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    objects = manifest.get("objects", [])
    world_size = max(float(config.get("world_size", 1.0)), 1e-6)
    world_height = max(float(config.get("world_height", 1.0)), 1e-6)
    categories = Counter(str(item.get("category", "unknown")) for item in objects)
    radial_height = np.zeros((12, 12), dtype=np.float64)
    scale_hist = np.zeros(16, dtype=np.float64)
    for item in objects:
        position = item.get("position", (0.0, 0.0, 0.0))
        scale = item.get("scale", (1.0, 1.0, 1.0))
        radius = min(
            math.hypot(float(position[0]), float(position[2])) / (world_size * 0.5),
            0.999999,
        )
        elevation = min(max(float(position[1]) / world_height, 0.0), 0.999999)
        radial_height[int(radius * 12), int(elevation * 12)] += 1.0
        relative_scale = min(max(max(float(value) for value in scale) / world_size, 0.0), 0.199999)
        scale_hist[int(relative_scale / 0.2 * 16)] += 1.0
    if radial_height.sum() > 0:
        radial_height /= radial_height.sum()
    if scale_hist.sum() > 0:
        scale_hist /= scale_hist.sum()
    return {
        "count": len(objects),
        "categories": categories,
        "radial_height": radial_height,
        "scale_hist": scale_hist,
    }


def _distribution_similarity(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.clip(1.0 - 0.5 * np.abs(left - right).sum(), 0.0, 1.0))


def _object_similarity(generated: Path, reference: Path) -> dict[str, Any] | None:
    left = _manifest_features(generated)
    right = _manifest_features(reference)
    if left is None or right is None:
        return None
    left_count = int(left["count"])
    right_count = int(right["count"])
    count_score = 1.0 - abs(left_count - right_count) / max(left_count, right_count, 1)

    keys = sorted(set(left["categories"]) | set(right["categories"]))
    left_categories = np.asarray([left["categories"].get(key, 0) for key in keys], dtype=float)
    right_categories = np.asarray([right["categories"].get(key, 0) for key in keys], dtype=float)
    left_categories /= max(float(left_categories.sum()), 1.0)
    right_categories /= max(float(right_categories.sum()), 1.0)
    category_score = _distribution_similarity(left_categories, right_categories)
    spatial_score = _distribution_similarity(left["radial_height"], right["radial_height"])
    scale_score = _distribution_similarity(left["scale_hist"], right["scale_hist"])
    weights = {"count": 0.20, "category": 0.25, "radial_height": 0.40, "scale": 0.15}
    total = (
        count_score * weights["count"]
        + category_score * weights["category"]
        + spatial_score * weights["radial_height"]
        + scale_score * weights["scale"]
    )
    return {
        "score_percent": round(total * 100.0, 3),
        "components": {
            "count": round(count_score * 100.0, 3),
            "category": round(category_score * 100.0, 3),
            "radial_height": round(spatial_score * 100.0, 3),
            "scale": round(scale_score * 100.0, 3),
        },
        "weights": weights,
    }


def score_bundles(generated: str | Path, reference: str | Path) -> dict[str, Any]:
    result = score_height_fields(load_height(generated), load_height(reference))
    generated_path = Path(generated)
    reference_path = Path(reference)
    if generated_path.is_dir() and reference_path.is_dir():
        object_result = _object_similarity(generated_path, reference_path)
        if object_result is not None:
            geometry_score = float(result["score_percent"])
            object_score = float(object_result["score_percent"])
            final_score = geometry_score * 0.75 + object_score * 0.25
            result["geometry_score_percent"] = geometry_score
            result["object_similarity"] = object_result
            result["bundle_weights"] = {"geometry": 0.75, "objects": 0.25}
            result["score_percent"] = round(final_score, 3)
            result["passes_90_percent"] = bool(final_score >= 90.0)
    return result
