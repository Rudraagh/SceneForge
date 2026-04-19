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


def run_scene_builder(prompt: str, mode: str) -> int:
    """Run the scene build entry point."""
    command = [sys.executable, str(PROJECT_ROOT / "direct_usd_scene.py"), f"--mode={mode}", prompt]
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


def main() -> int:
    mode = "ai"
    filtered_args = []
    for arg in sys.argv[1:]:
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1].strip() or "ai"
        else:
            filtered_args.append(arg)
    prompt = " ".join(filtered_args).strip() or DEFAULT_PROMPT

    try:
        check_ollama_server()
        check_ollama_model()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"[INFO] Using Ollama model: {OLLAMA_MODEL}")
    print(f"[INFO] Scene generation mode: {mode}")
    print(f"[INFO] Prompt: {prompt}")

    return_code = run_scene_builder(prompt, mode)
    if return_code != 0:
        print(f"[ERROR] Scene builder exited with code {return_code}")
        return return_code

    output_path = PROJECT_ROOT / "generated_scene.usda"
    print(f"[INFO] Scene generation finished successfully.")
    print(f"[INFO] Output file name: {output_path.name}")
    try:
        flattened_path = export_flattened_scene(output_path)
        print(f"[INFO] Flattened file name: {flattened_path.name}")
    except Exception:
        print("[WARN] Flattened export skipped because USD could not safely write the flattened file in this directory.")
    launch_viewer(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
