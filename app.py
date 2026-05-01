"""
Streamlit UI for SceneForge: blueprint upload, USD generation, metrics, and
interactive scene exploration with Ollama-backed object explanations.
"""

import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from typing import Optional

import plotly.graph_objects as go
import streamlit as st

from scene_explainer import (
    SceneObject,
    _ollama_base_url,
    explain_object_in_scene,
    list_scene_objects,
)


st.set_page_config(page_title="SceneForge UI", layout="wide")


PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
BLUEPRINT_PATH = os.path.join(PROJECT_ROOT, "blueprint.png")
USD_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, "generated_scene.usda"))
BLENDER_PATH = r"C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe"
LOG_KEY = "logs"
RETURN_CODE_KEY = "return_code"
LAST_PROMPT_KEY = "last_prompt"
PLOTLY_CHART_KEY = "sceneforge_plotly_objects"


@st.cache_data(ttl=20)
def _ollama_reachable() -> bool:
    try:
        with urllib.request.urlopen(f"{_ollama_base_url()}/api/tags", timeout=3) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def save_blueprint_file(uploaded_file) -> None:
    if uploaded_file is None:
        return
    with open(BLUEPRINT_PATH, "wb") as handle:
        handle.write(uploaded_file.getbuffer())


def run_pipeline(prompt):
    # Use the same interpreter as Streamlit so venv + installed deps (e.g. pxr) match.
    cmd = [sys.executable, "direct_usd_scene.py", "-b", prompt]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )

    stdout, stderr = process.communicate()
    combined_logs = stdout or ""
    if stderr:
        if combined_logs:
            combined_logs += "\n"
        combined_logs += stderr
    return combined_logs, process.returncode


def extract_metrics(logs):
    match = re.search(
        r"\[RESULT\] score=([-\d.]+) \| objects=(\d+) \| violations=(\d+) \| iterations=(\d+)",
        logs,
    )

    if match:
        return {
            "score": float(match.group(1)),
            "objects": int(match.group(2)),
            "violations": int(match.group(3)),
            "iterations": int(match.group(4)),
        }
    return None


def extract_explanation(logs):
    lines = logs.splitlines()
    explanation = []
    for line in lines:
        if "[EXPLAIN]" in line or "[DETAIL]" in line:
            explanation.append(line)
    return explanation


def extract_output_path(logs):
    matches = re.findall(r"\[INFO\] Exported stage to file: (.+)", logs)
    if matches:
        return os.path.abspath(os.path.join(PROJECT_ROOT, matches[-1].strip()))
    return USD_PATH


def open_in_blender(path):
    if not os.path.exists(BLENDER_PATH):
        return "Blender not found"
    if not os.path.exists(path):
        return "USD file not found"

    subprocess.Popen([BLENDER_PATH, path], cwd=PROJECT_ROOT)
    return "Opened in Blender"


def score_badge(score):
    if score > 0.7:
        return "green"
    if score >= 0.5:
        return "orange"
    return "red"


def _marker_color_for_kind(kind: str) -> str:
    hue = abs(hash(kind)) % 360
    return f"hsl({hue}, 65%, 52%)"


def _build_scene_scatter_figure(objects: list[SceneObject]) -> go.Figure:
    xs = [o.position[0] for o in objects]
    ys = [o.position[1] for o in objects]
    zs = [o.position[2] for o in objects]
    labels = [o.prim_name for o in objects]
    colors = [_marker_color_for_kind(o.kind) for o in objects]
    custom_paths = [o.prim_path for o in objects]

    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=xs,
                y=ys,
                z=zs,
                mode="markers+text",
                text=labels,
                textposition="top center",
                marker=dict(size=10, color=colors, opacity=0.92, line=dict(width=1, color="#222")),
                customdata=custom_paths,
                hovertemplate="<b>%{text}</b><br>X %{x:.2f} Y %{y:.2f} Z %{z:.2f}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title=dict(text="Scene objects — click a point to select it", font=dict(size=14)),
        scene=dict(
            xaxis_title="X",
            yaxis_title="Y",
            zaxis_title="Z",
            aspectmode="data",
        ),
        margin=dict(l=0, r=0, t=40, b=0),
        height=560,
        showlegend=False,
    )
    return fig


@st.dialog("Object explanation", width="large")
def _explain_object_dialog(scene_prompt: str, obj: SceneObject) -> None:
    st.caption(f"{obj.label} · `{obj.prim_path}`")
    with st.spinner("Asking Ollama for a short explanation…"):
        try:
            steps = explain_object_in_scene(scene_prompt, obj)
        except RuntimeError as exc:
            st.error(str(exc))
            st.info("Check that Ollama is running and `OLLAMA_API_URL` / model env vars match your setup.")
            return
    for index, step in enumerate(steps, start=1):
        st.markdown(f"**Part {index} of {len(steps)}**")
        st.write(step)


st.title("🧠 SceneForge: Blueprint-driven 3D Scene Generator")

with st.sidebar:
    st.header("Input")

    uploaded_file = st.file_uploader("Upload Blueprint Image", type=["png", "jpg"])

    prompt = st.text_input(
        "Scene Prompt",
        value="a classroom with desks and chairs",
    )

    run_btn = st.button("Generate Scene")

    if uploaded_file is not None:
        st.caption(f"Blueprint ready: `{uploaded_file.name}`")

    st.divider()
    st.caption("AI object explanations")
    if _ollama_reachable():
        st.success("Ollama is reachable")
    else:
        st.warning("Ollama is not running — open **Ollama** from the Start menu or run `ollama serve`, then **Recheck**.")
    if st.button("Recheck Ollama", key="sf_recheck_ollama"):
        _ollama_reachable.clear()
        st.rerun()


if uploaded_file is not None:
    save_blueprint_file(uploaded_file)


if run_btn:
    if uploaded_file is None:
        st.error("Please upload a blueprint image before running the pipeline.")
    elif not prompt.strip():
        st.error("Please enter a scene prompt.")
    else:
        with st.spinner("Running pipeline..."):
            logs, return_code = run_pipeline(prompt.strip())
        st.session_state[LOG_KEY] = logs
        st.session_state[RETURN_CODE_KEY] = return_code
        st.session_state[LAST_PROMPT_KEY] = prompt.strip()

        if return_code == 0:
            st.success("Scene generated successfully")
        else:
            st.error(f"Pipeline exited with code {return_code}")


logs = st.session_state.get(LOG_KEY, "")
return_code = st.session_state.get(RETURN_CODE_KEY)

if logs:
    metrics = extract_metrics(logs)
    explanation = extract_explanation(logs)
    usd_path = extract_output_path(logs)

    top_left, top_right = st.columns([2, 1])

    with top_left:
        st.subheader("Logs")
        st.text_area("Pipeline Output", logs, height=400)

    with top_right:
        st.subheader("Run Summary")
        if st.session_state.get(LAST_PROMPT_KEY):
            st.write(f"**Prompt:** {st.session_state[LAST_PROMPT_KEY]}")
        if return_code is not None:
            st.write(f"**Return code:** {return_code}")
        st.write(f"**Blueprint file:** `{BLUEPRINT_PATH}`")
        st.write(f"**USD exists:** {'Yes' if os.path.exists(usd_path) else 'No'}")

    if metrics:
        st.subheader("Metrics")
        col1, col2, col3, col4 = st.columns(4)

        score_color = score_badge(metrics["score"])
        col1.metric("Score", metrics["score"])
        col1.markdown(
            f"<span style='color:{score_color};font-weight:600'>Quality band</span>",
            unsafe_allow_html=True,
        )
        col2.metric("Objects", metrics["objects"])
        col3.metric("Violations", metrics["violations"])
        col4.metric("Iterations", metrics["iterations"])

    if explanation:
        st.subheader("Explanation")
        for line in explanation:
            st.write(line)

    st.subheader("Output File")
    st.code(usd_path)

    blender_col, temp_col = st.columns([1, 2])
    with blender_col:
        if st.button("Open in Blender", disabled=not os.path.exists(usd_path)):
            msg = open_in_blender(usd_path)
            st.write(msg)
    with temp_col:
        st.caption(f"Workspace temp directory: `{tempfile.gettempdir()}`")

    if return_code == 0 and os.path.exists(usd_path):
        st.subheader("Explore scene — Ollama explanations")
        st.caption(
            "Each marker is a prim under `/World`. Click a point in the 3D chart (or pick from the list), "
            "then load a short multi-part explanation from your local Ollama server."
        )
        try:
            scene_objs = list_scene_objects(usd_path)
        except RuntimeError as exc:
            st.warning(str(exc))
            scene_objs = []

        if scene_objs:
            if "sf_obj_idx" not in st.session_state:
                st.session_state.sf_obj_idx = 0
            if int(st.session_state.sf_obj_idx) >= len(scene_objs):
                st.session_state.sf_obj_idx = 0

            fig = _build_scene_scatter_figure(scene_objs)
            plotly_event = st.plotly_chart(
                fig,
                on_select="rerun",
                selection_mode="points",
                key=PLOTLY_CHART_KEY,
                use_container_width=True,
            )

            picked: Optional[SceneObject] = None
            sel_points: list = []
            if isinstance(plotly_event, dict):
                selection = plotly_event.get("selection") or {}
                sel_points = selection.get("points", []) if isinstance(selection, dict) else []
            elif plotly_event is not None:
                selection = getattr(plotly_event, "selection", None)
                if isinstance(selection, dict):
                    sel_points = selection.get("points", [])
                elif selection is not None:
                    sel_points = getattr(selection, "points", []) or []

            if sel_points:
                point = sel_points[0]
                path_hit = point.get("customdata")
                if isinstance(path_hit, (list, tuple)) and path_hit:
                    path_hit = path_hit[0]
                path_hit = str(path_hit) if path_hit else ""
                for candidate in scene_objs:
                    if candidate.prim_path == path_hit:
                        picked = candidate
                        break
                if picked is None:
                    pidx = point.get("point_index")
                    if isinstance(pidx, int) and 0 <= pidx < len(scene_objs):
                        picked = scene_objs[pidx]

            if picked is not None:
                st.session_state.sf_obj_idx = scene_objs.index(picked)

            labels = [f"{o.label} ({o.prim_name})" for o in scene_objs]
            choice_idx = st.selectbox(
                "Selected object",
                list(range(len(scene_objs))),
                format_func=lambda i: labels[i],
                key="sf_obj_idx",
            )
            effective = scene_objs[int(choice_idx)]

            st.write(f"**Explaining:** {effective.label} · `{effective.prim_path}`")
            if st.button("Get AI explanation (Ollama)", key="sf_explain_ollama"):
                scene_prompt = st.session_state.get(LAST_PROMPT_KEY, "") or ""
                _explain_object_dialog(scene_prompt, effective)
else:
    st.info("Upload a blueprint, enter a prompt, and run the pipeline to generate a scene.")
