"""
Bootstraps Omniverse Kit from Python, enables the required extensions, and
executes the natural-language scene generation script.
"""

from __future__ import annotations

import os
import sys

# Accept the Kit EULA non-interactively so installs/runs do not block.
os.environ.setdefault("OMNI_KIT_ACCEPT_EULA", "yes")

from omni.kit_app import KitApp


def main() -> int:
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

    mode = "ai"
    raw_args = sys.argv[1:]
    filtered_args = []
    for arg in raw_args:
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1].strip() or "ai"
        else:
            filtered_args.append(arg)

    prompt = " ".join(filtered_args).strip() or "a medieval classroom with wooden desks"
    save_path = os.path.abspath("generated_scene.usda")

    try:
        build_scene_from_prompt(prompt=prompt, save_path=save_path, mode=mode)
        print(f"[INFO] Scene generation completed: {save_path}")
        return 0
    finally:
        app.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
