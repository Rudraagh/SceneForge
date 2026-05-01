"""
CLI helper: emit scene objects as JSON for a USDA path.

Used by pipeline_service.list_scene_objects_resolved when the FastAPI host
process cannot import pxr but the pipeline interpreter (SCENEFORGE_PYTHON /
resolve_pipeline_python) can.
"""

from __future__ import annotations

import json
import sys

from scene_explainer import list_scene_objects


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: list_scene_objects_json.py <path.usda>", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    objs = list_scene_objects(path)
    rows = [
        {
            "prim_path": o.prim_path,
            "prim_name": o.prim_name,
            "kind": o.kind,
            "label": o.label,
            "position": list(o.position),
        }
        for o in objs
    ]
    json.dump(rows, sys.stdout)


if __name__ == "__main__":
    main()
