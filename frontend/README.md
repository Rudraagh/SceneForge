# SceneForge web UI (React + Vite + Tailwind)

Responsive frontend that mirrors the Streamlit controls: prompt, blueprint, generation mode, asset / Objaverse options, logs, metrics, Plotly 3D object picker, and Ollama explanations.

## Prerequisite

Python deps including FastAPI:

```powershell
cd c:\Users\hridy\Desktop\SceneForge
python -m pip install -r requirements.txt
```

## 1) Start the API (from repo root)

```powershell
cd c:\Users\hridy\Desktop\SceneForge
uvicorn api_app:app --reload --host 127.0.0.1 --port 8765
```

## 2) Install and run the frontend

```powershell
cd c:\Users\hridy\Desktop\SceneForge\frontend
npm install
npm run dev
```

Open **http://localhost:5173** — Vite proxies `/api/*` to the FastAPI server on port **8765**.

## Production build

```powershell
npm run build
npm run preview
```

Serve `frontend/dist` with any static host; set `SCENEFORGE_CORS_ORIGINS` on the API to your production origin.

## Optional backdrop video

The backdrop checks (in order) **`public/hero-loop.mp4`** then **`public/backdrop.mp4`**. Use a **short, dark or abstract loop** (10–30s), muted-friendly B-roll; it plays with low opacity and multiply blend so text stays readable. If neither file exists, you still get **animated SVG orbit**, **drifting topo texture**, **conic wash**, and **pulsing rings** (no video required).

Bundled motion assets: `public/bg-topo.svg`, `public/bg-orbit.svg`.
