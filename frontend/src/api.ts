const json = (r: Response) => r.json();

export type GeneratePayload = {
  prompt: string;
  mode: "ai" | "rule";
  use_blueprint: boolean;
  blueprint_base64?: string | null;
  output_path: string;
  prefer_local_assets: boolean;
  disable_cache: boolean;
  disable_objaverse: boolean;
  disable_free: boolean;
  disable_procedural: boolean;
  asset_source_order: string;
  objaverse_candidate_limit: number;
  objaverse_min_score: number;
};

export type GenerateResponse = {
  return_code: number;
  logs: string;
  metrics: {
    score: number;
    objects: number;
    violations: number;
    iterations: number;
  } | null;
  explanation_lines: string[];
  usd_path: string;
  usd_exists: boolean;
  pipeline_python: string;
  blueprint_path: string;
  temp_dir: string;
  objects?: SceneObjectDTO[];
  objects_error?: string | null;
};

export async function postGenerate(body: GeneratePayload): Promise<GenerateResponse> {
  const r = await fetch("/api/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const err = (await r.json().catch(() => ({}))) as { detail?: string | unknown[] };
    const d = err.detail;
    const msg = Array.isArray(d) ? JSON.stringify(d) : typeof d === "string" ? d : r.statusText;
    throw new Error(msg);
  }
  return json(r) as Promise<GenerateResponse>;
}

export async function getOllamaStatus(): Promise<{ reachable: boolean; models: string[] }> {
  const r = await fetch("/api/ollama-status");
  if (!r.ok) throw new Error("ollama-status failed");
  return json(r);
}

export async function getPipelinePython(): Promise<{ python: string }> {
  const r = await fetch("/api/pipeline-python");
  if (!r.ok) throw new Error("pipeline-python failed");
  return json(r);
}

export type SceneObjectDTO = {
  prim_path: string;
  prim_name: string;
  kind: string;
  label: string;
  position: [number, number, number];
};

export async function getSceneObjects(usdPath: string): Promise<SceneObjectDTO[]> {
  const q = encodeURIComponent(usdPath);
  const r = await fetch(`/api/scene-objects?usd_path=${q}`);
  if (!r.ok) {
    const err = (await r.json().catch(() => ({}))) as { detail?: string | unknown[] };
    const d = err.detail;
    const msg = Array.isArray(d) ? JSON.stringify(d) : typeof d === "string" ? d : r.statusText;
    throw new Error(msg || "scene-objects failed");
  }
  const data = await json(r);
  return (data as { objects: SceneObjectDTO[] }).objects;
}

export async function postExplain(
  scenePrompt: string,
  usdPath: string,
  primPath: string,
): Promise<{ steps: string[]; label: string }> {
  const r = await fetch("/api/explain-object", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scene_prompt: scenePrompt,
      usd_path: usdPath,
      prim_path: primPath,
    }),
  });
  if (!r.ok) {
    const err = (await r.json().catch(() => ({}))) as { detail?: string | unknown[] };
    const d = err.detail;
    const msg = Array.isArray(d) ? JSON.stringify(d) : typeof d === "string" ? d : r.statusText;
    throw new Error(msg);
  }
  return json(r);
}

export async function postOpenBlender(path: string): Promise<{ message: string }> {
  const r = await fetch("/api/open-blender", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!r.ok) throw new Error("open-blender failed");
  return json(r);
}

export function downloadUsdUrl(usdPath: string): string {
  return `/api/download-usd?usd_path=${encodeURIComponent(usdPath)}`;
}
