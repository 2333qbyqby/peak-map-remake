from __future__ import annotations

import argparse
import json
from pathlib import Path

from .baker import export_bundle
from .config import BakeConfig
from .generator import bake_island
from .similarity import load_height, score_bundles, score_height_fields


def _config_from_args(args: argparse.Namespace, seed: int | None = None) -> BakeConfig:
    return BakeConfig(
        seed=args.seed if seed is None else seed,
        resolution=args.resolution,
        world_size=args.world_size,
        world_height=args.world_height,
        second_biome=args.second,
        third_biome=args.third,
        route_mode=args.route_mode,
        object_budget=args.object_budget,
    )


def _add_bake_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--resolution", type=int, default=257)
    parser.add_argument("--world-size", type=float, default=720.0)
    parser.add_argument("--world-height", type=float, default=1200.0)
    parser.add_argument("--second", choices=("rainforest", "redwood"), default="rainforest")
    parser.add_argument("--third", choices=("alpine", "mesa"), default="alpine")
    parser.add_argument("--route-mode", choices=("analyze", "repair"), default="analyze")
    parser.add_argument("--object-budget", type=int, default=520)


def _bake(args: argparse.Namespace) -> None:
    island = bake_island(_config_from_args(args))
    output = export_bundle(args.output, island)
    print(json.dumps({"output": str(output), "statistics": island.statistics}, ensure_ascii=False, indent=2))


def _gallery(args: argparse.Namespace) -> None:
    root = Path(args.output)
    combinations = (
        ("rainforest", "alpine"),
        ("rainforest", "mesa"),
        ("redwood", "alpine"),
        ("redwood", "mesa"),
    )
    outputs = []
    for index, (second, third) in enumerate(combinations):
        args.second = second
        args.third = third
        config = _config_from_args(args, seed=args.seed + index)
        destination = root / f"{index + 1:02d}-{second}-{third}"
        export_bundle(destination, bake_island(config))
        outputs.append(str(destination))
    print(json.dumps({"outputs": outputs}, ensure_ascii=False, indent=2))


def _score(args: argparse.Namespace) -> None:
    print(json.dumps(score_bundles(args.generated, args.reference), ensure_ascii=False, indent=2))


def _calibrate(args: argparse.Namespace) -> None:
    reference = load_height(args.reference)
    resolution = reference.shape[0]
    if resolution % 2 == 0:
        resolution -= 1
    args.resolution = max(33, resolution)
    best: tuple[float, BakeConfig, dict[str, object]] | None = None
    for trial in range(args.trials):
        args.second = ("rainforest", "redwood")[trial % 2]
        args.third = ("alpine", "mesa")[(trial // 2) % 2]
        config = _config_from_args(args, seed=args.seed + trial)
        island = bake_island(config)
        result = score_height_fields(island.height, reference)
        candidate = (float(result["score_percent"]), config, result)
        if best is None or candidate[0] > best[0]:
            best = candidate
    assert best is not None
    output = export_bundle(args.output, bake_island(best[1]))
    final_similarity = score_bundles(output, args.reference)
    report = {
        "output": str(output),
        "best_config": best[1].to_dict(),
        "similarity": final_similarity,
        "search_geometry_similarity": best[2],
        "trials": args.trials,
        "note": "The search uses geometry; the final score also includes object distributions when both bundles provide manifests.",
    }
    (Path(output) / "calibration_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="island-baker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bake_parser = subparsers.add_parser("bake", help="Bake one deterministic vertical island.")
    _add_bake_options(bake_parser)
    bake_parser.add_argument("--output", type=Path, default=Path("build/island"))
    bake_parser.set_defaults(func=_bake)

    gallery_parser = subparsers.add_parser("gallery", help="Bake all four biome rotations.")
    _add_bake_options(gallery_parser)
    gallery_parser.add_argument("--output", type=Path, default=Path("build/gallery"))
    gallery_parser.set_defaults(func=_gallery)

    score_parser = subparsers.add_parser("score", help="Score a generated bundle against a private reference.")
    score_parser.add_argument("--generated", type=Path, required=True)
    score_parser.add_argument("--reference", type=Path, required=True)
    score_parser.set_defaults(func=_score)

    calibrate_parser = subparsers.add_parser("calibrate", help="Search seeds/rotations against a private heightmap.")
    _add_bake_options(calibrate_parser)
    calibrate_parser.add_argument("--reference", type=Path, required=True)
    calibrate_parser.add_argument("--output", type=Path, default=Path("build/calibrated"))
    calibrate_parser.add_argument("--trials", type=int, default=16)
    calibrate_parser.set_defaults(func=_calibrate)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
