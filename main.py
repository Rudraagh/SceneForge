"""
Single entry point for the Omniverse scene builder project.

This script:
1. Verifies that the local Ollama server is reachable.
2. Verifies that the requested Ollama model exists locally.
3. Runs the Omniverse scene generation entry point.

Run from this project folder:
    C:/Users/arun1/omniverse-kit-venv312/Scripts/python.exe main.py "a medieval classroom with wooden desks"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from pxr import Usd


PROJECT_ROOT = Path(__file__).resolve().parent
OLLAMA_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("SCENE_GRAPH_OLLAMA_MODEL", "llama3.2:1b")
DEFAULT_PROMPT = "a medieval classroom with wooden desks"


def check_ollama_server() -> None:
    """Fail early with a helpful message if Ollama is not running."""
    tags_url = f"{OLLAMA_URL}/api/tags"
    try:
        with urllib.request.urlopen(tags_url, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f"Ollama server returned status {response.status}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            "Ollama server is not reachable. Start it first with:\n"
            r"C:\Users\arun1\AppData\Local\Programs\Ollama\ollama.exe serve"
        ) from exc


def check_ollama_model() -> None:
    """Verify the configured model is already pulled locally."""
    tags_url = f"{OLLAMA_URL}/api/tags"
    with urllib.request.urlopen(tags_url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    models = payload.get("models", [])
    names = {model.get("name", "") for model in models}
    if OLLAMA_MODEL not in names:
        raise RuntimeError(
            f"Ollama model '{OLLAMA_MODEL}' is not installed.\n"
            f"Pull it first with:\n"
            r"C:\Users\arun1\AppData\Local\Programs\Ollama\ollama.exe pull "
            + OLLAMA_MODEL
        )


def run_scene_builder(args: argparse.Namespace, prompt: str) -> int:
    """Run the scene build entry point."""
    command = [sys.executable, str(PROJECT_ROOT / "direct_usd_scene.py"), "--mode", args.mode, "--output", args.output]
    if args.blueprint:
        command.extend(["--blueprint", "--blueprint-path", args.blueprint_path])
    if args.asset_source_order:
        command.extend(["--asset-source-order", args.asset_source_order])
    if args.prefer_local_assets:
        command.append("--prefer-local-assets")
    if args.disable_cache:
        command.append("--disable-cache")
    if args.disable_objaverse:
        command.append("--disable-objaverse")
    if args.disable_free:
        command.append("--disable-free")
    if args.disable_procedural:
        command.append("--disable-procedural")
    if args.objaverse_candidate_limit is not None:
        command.extend(["--objaverse-candidate-limit", str(args.objaverse_candidate_limit)])
    if args.objaverse_min_score is not None:
        command.extend(["--objaverse-min-score", str(args.objaverse_min_score)])
    command.append(prompt)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
    return completed.returncode


def launch_viewer(scene_path: Path) -> None:
    """Open the lightweight local USDA previewer in a separate process."""
    if os.getenv("OPEN_VIEWER", "1") != "1":
        return

    viewer_script = PROJECT_ROOT / "view_generated_scene.py"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    launcher = str(pythonw if pythonw.exists() else Path(sys.executable))
    subprocess.Popen(
        [launcher, str(viewer_script), str(scene_path)],
        cwd=PROJECT_ROOT,
    )


def export_flattened_scene(scene_path: Path) -> Path:
    """Create a self-contained flattened USDA for online viewers."""
    stage = Usd.Stage.Open(str(scene_path))
    if stage is None:
        raise RuntimeError(f"Could not open scene for flattening: {scene_path}")

    flattened_layer = stage.Flatten()
    flattened_path = scene_path.with_name(f"{scene_path.stem}_flat_{int(time.time())}.usda")
    if not flattened_layer.Export(str(flattened_path)):
        raise RuntimeError(f"Could not export flattened scene: {flattened_path}")
    return flattened_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SceneForge CLI: generate a USD scene from a prompt.",
    )
    parser.add_argument("-help", action="help", help=argparse.SUPPRESS)
    parser.add_argument("prompt", nargs="*", help="Scene prompt.")
    parser.add_argument("--mode", choices=["ai", "rule"], default="ai", help="Scene graph generation mode.")
    parser.add_argument("-b", "--blueprint", action="store_true", help="Use a blueprint image for placement.")
    parser.add_argument("--blueprint-path", default="blueprint.png", help="Blueprint image path.")
    parser.add_argument("-o", "--output", default="generated_scene.usda", help="Output USDA path.")
    parser.add_argument("--skip-ollama-check", action="store_true", help="Do not validate Ollama before running.")
    parser.add_argument("--no-viewer", action="store_true", help="Do not open the local previewer after export.")
    parser.add_argument(
        "--asset-source-order",
        help="Comma-separated source order using cache,objaverse,free,local,procedural.",
    )
    parser.add_argument("--prefer-local-assets", action="store_true", help="Prefer local assets before external sources.")
    parser.add_argument("--disable-cache", action="store_true", help="Do not reuse normalized cache entries.")
    parser.add_argument("--disable-objaverse", action="store_true", help="Skip Objaverse search/download.")
    parser.add_argument("--disable-free", action="store_true", help="Skip curated free-source downloads.")
    parser.add_argument("--disable-procedural", action="store_true", help="Skip procedural fallback assets.")
    parser.add_argument("--objaverse-candidate-limit", type=int, help="Objaverse candidates to inspect per category.")
    parser.add_argument("--objaverse-min-score", type=float, help="Minimum Objaverse quality score.")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    prompt = " ".join(args.prompt).strip() or DEFAULT_PROMPT

    if args.mode == "ai" and not args.skip_ollama_check:
        try:
            check_ollama_server()
            check_ollama_model()
        except RuntimeError as exc:
            print(f"[ERROR] {exc}")
            return 1

    print(f"[INFO] Using Ollama model: {OLLAMA_MODEL}")
    print(f"[INFO] Scene generation mode: {args.mode}")
    print(f"[INFO] Prompt: {prompt}")

    return_code = run_scene_builder(args, prompt)
    if return_code != 0:
        print(f"[ERROR] Scene builder exited with code {return_code}")
        return return_code

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    print(f"[INFO] Scene generation finished successfully.")
    print(f"[INFO] Output file name: {output_path.name}")
    try:
        flattened_path = export_flattened_scene(output_path)
        print(f"[INFO] Flattened file name: {flattened_path.name}")
    except Exception:
        print("[WARN] Flattened export skipped because USD could not safely write the flattened file in this directory.")
    if not args.no_viewer:
        launch_viewer(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
