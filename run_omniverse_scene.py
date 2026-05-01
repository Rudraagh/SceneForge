"""
Bootstraps Omniverse Kit from Python, enables the required extensions, and
executes the natural-language scene generation script.
"""

from __future__ import annotations

import argparse
import os
import sys

# Accept the Kit EULA non-interactively so installs/runs do not block.
os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "yes")

from omni.kit_app import KitApp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Omniverse Kit SceneForge backend.")
    parser.add_argument("-help", action="help", help=argparse.SUPPRESS)
    parser.add_argument("prompt", nargs="*", help="Scene prompt.")
    parser.add_argument("--mode", choices=["ai", "rule"], default="ai", help="Scene graph generation mode.")
    parser.add_argument("-o", "--output", default="generated_scene.usda", help="Output USDA path.")
    parser.add_argument("--asset-source-order", help="Comma-separated source order using cache,objaverse,free,local,procedural.")
    parser.add_argument("--prefer-local-assets", action="store_true", help="Prefer local assets before external sources.")
    parser.add_argument("--disable-cache", action="store_true", help="Do not reuse normalized cache entries.")
    parser.add_argument("--disable-objaverse", action="store_true", help="Skip Objaverse search/download.")
    parser.add_argument("--disable-free", action="store_true", help="Skip curated free-source downloads.")
    parser.add_argument("--disable-procedural", action="store_true", help="Skip procedural fallback assets.")
    parser.add_argument("--objaverse-candidate-limit", type=int, help="Objaverse candidates to inspect per category.")
    parser.add_argument("--objaverse-min-score", type=float, help="Minimum Objaverse quality score.")
    return parser.parse_args()


def apply_asset_env(args: argparse.Namespace) -> None:
    if args.prefer_local_assets and not args.asset_source_order:
        os.environ["SCENE_ASSET_SOURCE_ORDER"] = "local,free,cache,objaverse,procedural"
    elif args.asset_source_order:
        os.environ["SCENE_ASSET_SOURCE_ORDER"] = args.asset_source_order

    for flag_name, env_name in (
        ("disable_cache", "SCENE_DISABLE_CACHE"),
        ("disable_objaverse", "SCENE_DISABLE_OBJAVERSE"),
        ("disable_free", "SCENE_DISABLE_FREE"),
        ("disable_procedural", "SCENE_DISABLE_PROCEDURAL"),
    ):
        if getattr(args, flag_name):
            os.environ[env_name] = "1"

    if args.objaverse_candidate_limit is not None:
        os.environ["OBJAVERSE_CANDIDATE_LIMIT"] = str(max(1, args.objaverse_candidate_limit))
    if args.objaverse_min_score is not None:
        os.environ["OBJAVERSE_MIN_SCORE"] = str(args.objaverse_min_score)


def main() -> int:
    args = parse_args()
    apply_asset_env(args)
    app = KitApp()

    # Enable the core Omniverse extensions we need for USD stage editing and
    # command-based prim/reference creation.
    app.startup(
        [
            "--enable",
            "omni.usd",
            "--enable",
            "omni.kit.commands",
        ]
    )

    from natural_language_scene import build_scene_from_prompt

    prompt = " ".join(args.prompt).strip() or "a medieval classroom with wooden desks"
    save_path = os.path.abspath(args.output)

    try:
        build_scene_from_prompt(prompt=prompt, save_path=save_path, mode=args.mode)
        print(f"[INFO] Scene generation completed: {save_path}")
        return 0
    finally:
        app.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
