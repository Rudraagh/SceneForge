import os
import re
import subprocess
import tempfile

import streamlit as st


st.set_page_config(page_title="SceneForge UI", layout="wide")


PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
BLUEPRINT_PATH = os.path.join(PROJECT_ROOT, "blueprint.png")
USD_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, "generated_scene.usda"))
BLENDER_PATH = r"C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe"
LOG_KEY = "logs"
RETURN_CODE_KEY = "return_code"
LAST_PROMPT_KEY = "last_prompt"


def save_blueprint_file(uploaded_file) -> None:
    if uploaded_file is None:
        return
    with open(BLUEPRINT_PATH, "wb") as handle:
        handle.write(uploaded_file.getbuffer())


def run_pipeline(prompt):
    cmd = ["python", "direct_usd_scene.py", "-b", prompt]
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
else:
    st.info("Upload a blueprint, enter a prompt, and run the pipeline to generate a scene.")
