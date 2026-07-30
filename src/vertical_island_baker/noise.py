from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter


def normalized(values: np.ndarray) -> np.ndarray:
    lo = float(values.min())
    hi = float(values.max())
    if hi - lo < 1e-12:
        return np.zeros_like(values, dtype=np.float64)
    return (values - lo) / (hi - lo)


def fbm(
    shape: tuple[int, int],
    rng: np.random.Generator,
    octaves: int = 5,
    persistence: float = 0.52,
) -> np.ndarray:
    """Fast, deterministic fractal field built from filtered white noise."""

    result = np.zeros(shape, dtype=np.float64)
    amplitude = 1.0
    total = 0.0
    base_sigma = max(shape) / 7.0
    for octave in range(octaves):
        sigma = max(0.65, base_sigma / (2**octave))
        layer = gaussian_filter(rng.standard_normal(shape), sigma=sigma, mode="wrap")
        layer = normalized(layer) * 2.0 - 1.0
        result += amplitude * layer
        total += amplitude
        amplitude *= persistence
    return result / total


def domain_warp(
    x: np.ndarray,
    z: np.ndarray,
    rng: np.random.Generator,
    amount: float = 0.12,
) -> tuple[np.ndarray, np.ndarray]:
    nx = fbm(x.shape, rng, octaves=3, persistence=0.55)
    nz = fbm(x.shape, rng, octaves=3, persistence=0.55)
    return x + amount * nx, z + amount * nz

