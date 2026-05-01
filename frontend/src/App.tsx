import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";

/** Plotly is heavy and can break Vite’s initial eval on some setups — load only when the 3D panel mounts. */
const Plot = lazy(async () => {
  const mod = await import("react-plotly.js");
  return { default: mod.default };
});
import {
  getOllamaStatus,
  getPipelinePython,
  getSceneObjects,
  postExplain,
  postGenerate,
  postOpenBlender,
  type GenerateResponse,
  type SceneObjectDTO,
} from "./api";
import { FormAccordion } from "./components/FormAccordion";
import { SceneBackdrop } from "./components/SceneBackdrop";
import {
  ArchitectureStackSection,
  FAQSection,
  InteroperabilitySection,
  MarketingHero,
  ObservabilitySection,
  PlatformCapabilitiesSection,
  PositioningSection,
  PrivacyDataFlowSection,
  QuickStartSection,
  RequirementsSection,
  ResearchUseCasesSection,
  SamplePromptsSection,
  SiteFooter,
  WorkflowSection,
} from "./components/SiteMarketing";

function markerColor(kind: string): string {
  let h = 0;
  for (let i = 0; i < kind.length; i++) h = (h * 31 + kind.charCodeAt(i)) >>> 0;
  return `hsl(${h % 360} 65% 52%)`;
}

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export default function App() {
  const [prompt, setPrompt] = useState("a medieval classroom with wooden desks and a blackboard");
  const [mode, setMode] = useState<"ai" | "rule">("rule");
  const [useBlueprint, setUseBlueprint] = useState(true);
  const [blueprintFile, setBlueprintFile] = useState<File | null>(null);
  const [outputPath, setOutputPath] = useState("");
  const [preferLocal, setPreferLocal] = useState(true);
  const [disCache, setDisCache] = useState(false);
  const [disObj, setDisObj] = useState(false);
  const [disFree, setDisFree] = useState(false);
  const [disProc, setDisProc] = useState(false);
  const [assetOrder, setAssetOrder] = useState("");
  const [objLimit, setObjLimit] = useState(5);
  const [objScore, setObjScore] = useState(0.45);

  const [ollama, setOllama] = useState<{ ok: boolean; models: string[] }>({ ok: false, models: [] });
  const [pipelinePy, setPipelinePy] = useState("");

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [scenePrompt, setScenePrompt] = useState("");

  const [objects, setObjects] = useState<SceneObjectDTO[]>([]);
  const [selectedPath, setSelectedPath] = useState<string>("");

  const [modalOpen, setModalOpen] = useState(false);
  const [explainTitle, setExplainTitle] = useState("");
  const [explainSteps, setExplainSteps] = useState<string[]>([]);
  const [explainErr, setExplainErr] = useState<string | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);

  const [toast, setToast] = useState<string | null>(null);
  const [studioTab, setStudioTab] = useState<"configure" | "output">("configure");

  const refreshMeta = useCallback(async () => {
    try {
      const [o, p] = await Promise.all([getOllamaStatus(), getPipelinePython()]);
      setOllama({ ok: o.reachable, models: o.models });
      setPipelinePy(p.python);
    } catch {
      setOllama({ ok: false, models: [] });
    }
  }, []);

  useEffect(() => {
    void refreshMeta();
  }, [refreshMeta]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 4200);
    return () => window.clearTimeout(t);
  }, [toast]);

  const fileToB64 = (file: File) =>
    new Promise<string>((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve((r.result as string) || "");
      r.onerror = () => reject(new Error("read failed"));
      r.readAsDataURL(file);
    });

  const onGenerate = async () => {
    setErr(null);
    setLoading(true);
    setStudioTab("output");
    setResult(null);
    setObjects([]);
    setSelectedPath("");
    try {
      let blueprint_base64: string | undefined;
      if (useBlueprint && blueprintFile) {
        blueprint_base64 = await fileToB64(blueprintFile);
      }
      const res = await postGenerate({
        prompt: prompt.trim(),
        mode,
        use_blueprint: useBlueprint,
        blueprint_base64,
        output_path: outputPath.trim(),
        prefer_local_assets: preferLocal,
        disable_cache: disCache,
        disable_objaverse: disObj,
        disable_free: disFree,
        disable_procedural: disProc,
        asset_source_order: assetOrder,
        objaverse_candidate_limit: objLimit,
        objaverse_min_score: objScore,
      });
      setResult(res);
      setScenePrompt(prompt.trim());
      if (res.return_code === 0 && res.usd_exists) {
        const objs = await getSceneObjects(res.usd_path);
        setObjects(objs);
        if (objs.length) setSelectedPath(objs[0].prim_path);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const plotData = useMemo(() => {
    if (!objects.length) return null;
    const xs = objects.map((o) => o.position[0]);
    const ys = objects.map((o) => o.position[1]);
    const zs = objects.map((o) => o.position[2]);
    const text = objects.map((o) => o.prim_name);
    const colors = objects.map((o) => markerColor(o.kind));
    const customdata = objects.map((o) => o.prim_path);
    return {
      data: [
        {
          type: "scatter3d" as const,
          mode: "markers+text" as const,
          x: xs,
          y: ys,
          z: zs,
          text,
          textposition: "top center" as const,
          marker: {
            size: 11,
            color: colors,
            opacity: 0.92,
            line: { width: 1, color: "#1a1a1a" },
          },
          customdata: customdata,
          hovertemplate: "<b>%{text}</b><br>%{x:.2f}, %{y:.2f}, %{z:.2f}<extra></extra>",
        },
      ],
      layout: {
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { color: "#2a2a2a", size: 11 },
        title: { text: "Scene objects — click a marker", font: { size: 14, color: "#0c0c0c" } },
        margin: { l: 0, r: 0, t: 40, b: 0 },
        autosize: true,
        scene: {
          bgcolor: "rgba(255,255,255,0.92)",
          xaxis: { title: "X", gridcolor: "rgba(0,0,0,0.08)", color: "#525252" },
          yaxis: { title: "Y", gridcolor: "rgba(0,0,0,0.08)", color: "#525252" },
          zaxis: { title: "Z", gridcolor: "rgba(0,0,0,0.08)", color: "#525252" },
          aspectmode: "data" as const,
        },
        showlegend: false,
      },
      config: { responsive: true, displayModeBar: true, scrollZoom: true },
    };
  }, [objects]);

  const onPlotClick = (ev: { points?: Array<{ customdata?: unknown }> }) => {
    const p = ev.points?.[0];
    if (!p) return;
    const cd = p.customdata;
    const path = Array.isArray(cd) ? String(cd[0]) : String(cd ?? "");
    if (path) setSelectedPath(path);
  };

  const onExplain = async () => {
    if (!result?.usd_path || !selectedPath) return;
    setModalOpen(true);
    setExplainErr(null);
    setExplainSteps([]);
    setExplainTitle(selectedPath);
    setExplainLoading(true);
    try {
      const ex = await postExplain(scenePrompt, result.usd_path, selectedPath);
      setExplainTitle(`${ex.label} · ${selectedPath}`);
      setExplainSteps(ex.steps);
    } catch (e) {
      setExplainErr(e instanceof Error ? e.message : String(e));
    } finally {
      setExplainLoading(false);
    }
  };

  const onOpenBlender = async () => {
    if (!result?.usd_path) return;
    try {
      const r = await postOpenBlender(result.usd_path);
      setToast(r.message);
    } catch {
      setToast("Could not launch Blender. Check API logs and SCENEFORGE_BLENDER_PATH.");
    }
  };

  const metrics = result?.metrics;
  const showOutputPanel = Boolean(result || loading || err);

  const fieldClass =
    "w-full rounded-xl border border-ink/12 bg-white/90 px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint shadow-sm focus:border-ink/25 focus:outline-none focus:ring-2 focus:ring-neon/40";

  return (
    <div className="relative flex min-h-screen flex-col">
      <SceneBackdrop />
      <div className="relative z-10 flex min-h-screen flex-col">
      <a
        href="#studio"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-neon focus:px-3 focus:py-2 focus:text-sm focus:text-ink"
      >
        Skip to studio
      </a>

      <header className="sticky top-0 z-40 border-b border-ink/10 bg-canvas/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-3 motion-safe:animate-fadeInDown sm:flex-row sm:items-center sm:justify-between md:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-ink/15 bg-white font-display text-sm font-bold tracking-tight text-ink shadow-sm motion-safe:animate-scaleIn">
              SF
            </div>
            <div>
              <p className="font-display text-lg font-semibold tracking-tight text-ink">SceneForge</p>
              <p className="text-xs text-ink-faint">OpenUSD authoring · Local pipeline · Optional Ollama</p>
            </div>
          </div>
          <nav className="flex flex-wrap items-center gap-2 sm:gap-3" aria-label="Primary">
            <button
              type="button"
              onClick={() => scrollToId("capabilities")}
              className="rounded-lg px-3 py-2 text-sm text-ink-soft transition duration-200 hover:scale-105 hover:bg-white/80 hover:text-ink active:scale-95"
            >
              Platform
            </button>
            <button
              type="button"
              onClick={() => scrollToId("research")}
              className="hidden rounded-lg px-3 py-2 text-sm text-ink-soft transition duration-200 hover:scale-105 hover:bg-white/80 hover:text-ink active:scale-95 xl:inline-flex"
            >
              Research
            </button>
            <button
              type="button"
              onClick={() => scrollToId("sample-prompts")}
              className="hidden rounded-lg px-3 py-2 text-sm text-ink-soft transition duration-200 hover:scale-105 hover:bg-white/80 hover:text-ink active:scale-95 sm:inline-flex"
            >
              Prompts
            </button>
            <button
              type="button"
              onClick={() => scrollToId("quick-start")}
              className="rounded-lg px-3 py-2 text-sm text-ink-soft transition duration-200 hover:scale-105 hover:bg-white/80 hover:text-ink active:scale-95"
            >
              Setup
            </button>
            <button
              type="button"
              onClick={() => scrollToId("faq")}
              className="rounded-lg px-3 py-2 text-sm text-ink-soft transition duration-200 hover:scale-105 hover:bg-white/80 hover:text-ink active:scale-95"
            >
              FAQ
            </button>
            <button
              type="button"
              onClick={() => scrollToId("workflow")}
              className="rounded-lg px-3 py-2 text-sm text-ink-soft transition duration-200 hover:scale-105 hover:bg-white/80 hover:text-ink active:scale-95"
            >
              Workflow
            </button>
            <button
              type="button"
              onClick={() => scrollToId("studio")}
              className="rounded-lg px-3 py-2 text-sm text-ink-soft transition duration-200 hover:scale-105 hover:bg-white/80 hover:text-ink active:scale-95"
            >
              Studio
            </button>
            <div className="mx-1 hidden h-6 w-px bg-ink/10 sm:block" />
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium ${
                ollama.ok
                  ? "border-emerald-200/80 bg-emerald-50/90 text-emerald-900"
                  : "border-amber-200/80 bg-amber-50/90 text-amber-900"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full motion-safe:animate-pulse ${ollama.ok ? "bg-emerald-500" : "bg-amber-500"}`}
              />
              Ollama {ollama.ok ? "online" : "offline"}
              {ollama.ok && ollama.models.length ? (
                <span className="hidden text-ink-faint sm:inline">· {ollama.models.length} models</span>
              ) : null}
            </span>
            <button
              type="button"
              onClick={() => void refreshMeta()}
              className="rounded-lg border border-ink/12 bg-white/80 px-3 py-1.5 text-xs font-medium text-ink shadow-sm transition duration-200 hover:scale-105 hover:bg-white active:scale-95"
            >
              Recheck
            </button>
          </nav>
        </div>
      </header>

      <MarketingHero onStart={() => scrollToId("studio")} />
      <PlatformCapabilitiesSection />
      <ArchitectureStackSection />
      <InteroperabilitySection />
      <ResearchUseCasesSection />
      <ObservabilitySection />
      <PositioningSection />
      <SamplePromptsSection />
      <RequirementsSection />
      <PrivacyDataFlowSection />
      <FAQSection />
      <QuickStartSection />
      <WorkflowSection />

      <section id="studio" className="scroll-mt-24 border-b border-ink/10 py-10 sm:py-12">
        <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
          <div className="flex flex-col gap-2 motion-safe:animate-fadeInUp sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">Studio</h2>
              <p className="mt-1 max-w-2xl text-sm text-ink-soft sm:text-base">
                Same controls as Streamlit: prompt, blueprint, generation mode, asset flags, Objaverse tuning, logs, Plotly explorer, and Ollama explanations.
              </p>
            </div>
          </div>

          {/* Mobile / tablet: tab switcher */}
          {showOutputPanel && (
            <div className="mt-6 flex rounded-xl border border-ink/10 bg-white/70 p-1 shadow-sm motion-safe:animate-fadeIn sm:hidden">
              <button
                type="button"
                onClick={() => setStudioTab("configure")}
                className={`flex-1 rounded-lg py-2.5 text-sm font-medium transition-all duration-300 ease-out ${
                  studioTab === "configure" ? "scale-[1.02] bg-neon text-ink shadow-sm" : "text-ink-faint"
                }`}
              >
                Configure
              </button>
              <button
                type="button"
                onClick={() => setStudioTab("output")}
                className={`flex-1 rounded-lg py-2.5 text-sm font-medium transition-all duration-300 ease-out ${
                  studioTab === "output" ? "scale-[1.02] bg-neon text-ink shadow-sm" : "text-ink-faint"
                }`}
              >
                Output
              </button>
            </div>
          )}

          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,420px)_1fr] lg:items-start">
            {/* Configure column */}
            <div
              className={`space-y-4 sm:block ${
                showOutputPanel && studioTab === "output" ? "hidden" : "block"
              }`}
            >
              <div className="rounded-3xl border border-ink/10 bg-white/55 p-4 shadow-md backdrop-blur-md motion-safe:animate-fadeInUp motion-safe:[animation-delay:80ms] sm:p-5">
                <div className="space-y-3">
                  <FormAccordion id="acc-input" title="Scene input" subtitle="Prompt and blueprint placement" defaultOpen>
                    <label className="block text-xs font-medium uppercase tracking-wide text-ink-faint">Scene prompt</label>
                    <textarea
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      rows={4}
                      className={`${fieldClass} mt-1 min-h-[100px] resize-y`}
                    />
                    <label className="mt-3 flex cursor-pointer items-center gap-3 rounded-xl border border-ink/10 bg-white/80 px-3 py-2.5">
                      <input
                        type="checkbox"
                        checked={useBlueprint}
                        onChange={(e) => setUseBlueprint(e.target.checked)}
                        className="h-4 w-4 rounded border-ink/20 bg-white accent-neon focus:ring-neon/50"
                      />
                      <span className="text-sm text-ink">Use blueprint placement</span>
                    </label>
                    <label className="mt-3 block text-xs font-medium uppercase tracking-wide text-ink-faint">Blueprint image</label>
                    <input
                      type="file"
                      accept="image/png,image/jpeg"
                      onChange={(e) => setBlueprintFile(e.target.files?.[0] ?? null)}
                      className="mt-1 w-full text-xs text-ink-soft file:mr-3 file:rounded-lg file:border file:border-ink/10 file:bg-canvas-muted file:px-3 file:py-2 file:text-sm file:font-medium file:text-ink"
                    />
                    {blueprintFile ? (
                      <p className="mt-2 text-xs font-medium text-emerald-800">Attached: {blueprintFile.name}</p>
                    ) : null}
                  </FormAccordion>

                  <FormAccordion id="acc-gen" title="Generation" subtitle="Mode and output path">
                    <label className="block text-xs font-medium uppercase tracking-wide text-ink-faint">Mode</label>
                    <select
                      value={mode}
                      onChange={(e) => setMode(e.target.value as "ai" | "rule")}
                      className={`${fieldClass} mt-1`}
                    >
                      <option value="rule">Rule — fast, deterministic</option>
                      <option value="ai">AI — Ollama scene graph</option>
                    </select>
                    {mode === "rule" ? (
                      <p className="mt-2 text-xs leading-relaxed text-ink-faint">
                        Rule mode picks a small template from your prompt (for example courtyard vs studio). If blueprint
                        placement is enabled and <span className="font-medium text-ink-soft">blueprint.png</span> parses,
                        those regions replace or merge with that template (solar-system scenes skip blueprint).
                      </p>
                    ) : null}
                    <label className="mt-3 block text-xs font-medium uppercase tracking-wide text-ink-faint">Output USDA path (optional)</label>
                    <input
                      value={outputPath}
                      onChange={(e) => setOutputPath(e.target.value)}
                      placeholder="Default: generated_scene.usda in project"
                      className={`${fieldClass} mt-1`}
                    />
                  </FormAccordion>

                  <FormAccordion id="acc-assets" title="Assets & Objaverse" subtitle="Source toggles and scoring">
                    <div className="space-y-2">
                      {[
                        ["Prefer local assets", preferLocal, () => setPreferLocal((v) => !v)] as const,
                        ["Disable cache", disCache, () => setDisCache((v) => !v)] as const,
                        ["Disable Objaverse", disObj, () => setDisObj((v) => !v)] as const,
                        ["Disable free downloads", disFree, () => setDisFree((v) => !v)] as const,
                        ["Disable procedural fallback", disProc, () => setDisProc((v) => !v)] as const,
                      ].map(([label, checked, flip]) => (
                        <label
                          key={label}
                          className="flex cursor-pointer items-center gap-3 rounded-xl border border-ink/10 bg-white/80 px-3 py-2"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={flip}
                            className="h-4 w-4 rounded border-ink/20 bg-white accent-neon focus:ring-neon/50"
                          />
                          <span className="text-sm text-ink">{label}</span>
                        </label>
                      ))}
                    </div>
                    <label className="mt-3 block text-xs font-medium uppercase tracking-wide text-ink-faint">Custom source order</label>
                    <input
                      value={assetOrder}
                      onChange={(e) => setAssetOrder(e.target.value)}
                      placeholder="local,free,cache,objaverse,procedural"
                      className={`${fieldClass} mt-1`}
                    />
                    <label className="mt-3 block text-xs font-medium uppercase tracking-wide text-ink-faint">Objaverse candidate limit (1–50)</label>
                    <input
                      type="number"
                      min={1}
                      max={50}
                      value={objLimit}
                      onChange={(e) => setObjLimit(Number(e.target.value))}
                      className={`${fieldClass} mt-1`}
                    />
                    <label className="mt-3 block text-xs font-medium uppercase tracking-wide text-ink-faint">
                      Objaverse min score <span className="font-semibold text-ink">{objScore.toFixed(2)}</span>
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.01}
                      value={objScore}
                      onChange={(e) => setObjScore(Number(e.target.value))}
                      className="mt-2 h-2 w-full cursor-pointer appearance-none rounded-full bg-canvas-subtle accent-neon"
                    />
                  </FormAccordion>
                </div>

                <button
                  type="button"
                  disabled={loading || !prompt.trim()}
                  onClick={() => void onGenerate()}
                  className="relative mt-5 w-full overflow-hidden rounded-2xl bg-neon py-3.5 text-sm font-semibold uppercase tracking-wide text-ink shadow-md transition duration-200 hover:bg-neon-hover hover:scale-[1.01] active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:scale-100"
                >
                  {!loading && (
                    <span
                      className="pointer-events-none absolute inset-0 -translate-x-full skew-x-[-10deg] bg-gradient-to-r from-transparent via-black/8 to-transparent motion-safe:animate-shimmerSweep"
                      aria-hidden
                    />
                  )}
                  {loading ? (
                    <span className="relative z-[1] inline-flex items-center justify-center gap-2 text-ink">
                      <Spinner />
                      Generating scene…
                    </span>
                  ) : (
                    <span className="relative z-[1]">Generate scene</span>
                  )}
                </button>

                <p className="mt-4 text-[11px] leading-relaxed text-ink-faint">
                  Pipeline Python:{" "}
                  <code className="break-all rounded border border-ink/10 bg-canvas-muted px-1.5 py-0.5 text-ink-soft">{pipelinePy || "…"}</code>
                </p>
              </div>
            </div>

            {/* Output column */}
            <div
              className={`min-w-0 space-y-6 sm:block ${
                showOutputPanel && studioTab === "configure" ? "hidden" : "block"
              }`}
            >
              {loading && (
                <div className="rounded-3xl border border-ink/10 bg-white/60 p-6 shadow-md backdrop-blur-sm motion-safe:animate-fadeIn">
                  <div className="flex items-center gap-3 text-ink">
                    <Spinner className="h-6 w-6" />
                    <div>
                      <p className="font-display font-semibold">Running pipeline…</p>
                      <p className="text-sm text-ink-soft">Parsing blueprint, resolving assets, writing USDA.</p>
                    </div>
                  </div>
                  <div className="mt-6 grid animate-pulse gap-3 sm:grid-cols-3">
                    <div className="h-24 rounded-2xl bg-canvas-subtle/80" />
                    <div className="h-24 rounded-2xl bg-canvas-subtle/80" />
                    <div className="h-24 rounded-2xl bg-canvas-subtle/80" />
                  </div>
                </div>
              )}

              {err && (
                <div
                  role="alert"
                  className="rounded-2xl border border-red-200 bg-red-50/95 px-4 py-3 text-sm text-red-900 shadow-sm motion-safe:animate-slideUp"
                >
                  {err}
                </div>
              )}

              {!result && !loading && !err && (
                <div className="relative overflow-hidden rounded-3xl border border-dashed border-ink/15 bg-white/50 p-8 motion-safe:animate-fadeInUp sm:p-12">
                  <div className="absolute -right-8 -top-8 h-40 w-40 rounded-full bg-neon/15 blur-2xl motion-safe:animate-pulse" />
                  <div className="relative mx-auto max-w-lg text-center">
                    <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-ink/10 bg-white/80 text-2xl text-ink motion-safe:animate-floatSoft">
                      ◎
                    </div>
                    <h3 className="font-display text-lg font-semibold text-ink sm:text-xl">Ready when you are</h3>
                    <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                      Tune options in the panel, then generate. Results, logs, the 3D explorer, and Ollama explanations appear here—mirroring the Streamlit flow in a layout that scales from phone to desktop.
                    </p>
                  </div>
                </div>
              )}

              {result && (
                <>
                  <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                    <MetricCard
                      label="Return code"
                      value={String(result.return_code)}
                      tone={result.return_code === 0 ? "ok" : "bad"}
                      enterDelayMs={0}
                    />
                    {metrics ? (
                      <>
                        <MetricCard label="Score" value={String(metrics.score)} enterDelayMs={70} />
                        <MetricCard label="Objects" value={String(metrics.objects)} enterDelayMs={140} />
                        <MetricCard label="Violations" value={String(metrics.violations)} enterDelayMs={210} />
                      </>
                    ) : (
                      <>
                        <MetricCard label="Score" value="—" muted enterDelayMs={70} />
                        <MetricCard label="Objects" value="—" muted enterDelayMs={140} />
                        <MetricCard label="Violations" value="—" muted enterDelayMs={210} />
                      </>
                    )}
                  </div>

                  {result.explanation_lines.length > 0 && (
                    <section className="rounded-3xl border border-ink/10 bg-white/60 p-5 shadow-sm backdrop-blur-sm">
                      <h3 className="font-display text-sm font-semibold text-ink">Pipeline explanation</h3>
                      <ul className="mt-3 space-y-2 font-mono text-xs leading-relaxed text-ink-soft">
                        {result.explanation_lines.map((l, i) => (
                          <li key={i} className="border-l-2 border-neon pl-3">
                            {l}
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}

                  <section className="overflow-hidden rounded-3xl border border-ink/10 bg-white/60 shadow-sm backdrop-blur-sm">
                    <div className="flex flex-col gap-2 border-b border-ink/10 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
                      <h3 className="font-display text-sm font-semibold text-ink">Logs</h3>
                      <code className="truncate text-[10px] text-ink-faint" title={result.usd_path}>
                        {result.usd_path}
                      </code>
                    </div>
                    <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words p-4 text-[11px] leading-relaxed text-ink-soft sm:p-5">
                      {result.logs}
                    </pre>
                  </section>

                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      disabled={!result.usd_exists}
                      onClick={() => void onOpenBlender()}
                      className="inline-flex items-center gap-2 rounded-xl border border-ink/12 bg-white/90 px-4 py-2.5 text-sm font-medium text-ink shadow-sm transition duration-200 hover:scale-[1.02] hover:bg-white active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100"
                    >
                      Open in Blender
                    </button>
                    <span className="text-xs text-ink-faint">
                      Temp: <code className="text-ink-soft">{result.temp_dir}</code>
                    </span>
                  </div>

                  {result.return_code === 0 && result.usd_exists && plotData && (
                    <section className="overflow-hidden rounded-3xl border border-ink/10 bg-white/60 p-4 shadow-sm backdrop-blur-sm sm:p-5">
                      <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <h3 className="font-display text-sm font-semibold text-ink">Explore scene</h3>
                          <p className="text-xs text-ink-faint">Click a marker or pick from the list, then run Ollama.</p>
                        </div>
                      </div>
                      <div className="plot-shell w-full overflow-hidden rounded-2xl border border-ink/10 bg-white/90">
                        <Suspense
                          fallback={
                            <div className="flex min-h-[min(70vh,520px)] w-full items-center justify-center bg-canvas-muted/30 text-sm text-ink-soft">
                              Loading 3D view…
                            </div>
                          }
                        >
                          <Plot
                            data={plotData.data as never}
                            layout={{ ...plotData.layout, height: undefined } as never}
                            config={plotData.config}
                            onClick={onPlotClick as never}
                            className="min-h-[min(70vh,520px)] w-full"
                            style={{ width: "100%", minHeight: "min(70vh, 520px)" }}
                            useResizeHandler
                          />
                        </Suspense>
                      </div>
                      <label className="mt-4 block text-xs font-medium uppercase tracking-wide text-ink-faint">Selected object</label>
                      <select
                        value={selectedPath}
                        onChange={(e) => setSelectedPath(e.target.value)}
                        className={`${fieldClass} mt-1 max-w-full sm:max-w-xl`}
                      >
                        {objects.map((o) => (
                          <option key={o.prim_path} value={o.prim_path}>
                            {o.label} ({o.prim_name})
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => void onExplain()}
                        disabled={!selectedPath || explainLoading}
                        className="mt-3 inline-flex items-center gap-2 rounded-xl bg-neon px-4 py-2.5 text-sm font-semibold uppercase tracking-wide text-ink shadow-md transition duration-200 hover:bg-neon-hover hover:scale-[1.02] active:scale-[0.98] disabled:opacity-40 disabled:hover:scale-100"
                      >
                        {explainLoading ? <Spinner className="h-4 w-4" /> : null}
                        Get AI explanation (Ollama)
                      </button>
                    </section>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </section>

      <SiteFooter />

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="explain-dialog-title"
        >
          <button
            type="button"
            className="absolute inset-0 bg-ink/40 backdrop-blur-sm"
            aria-label="Close dialog"
            onClick={() => setModalOpen(false)}
          />
          <div className="relative z-10 flex max-h-[90vh] w-full max-w-lg flex-col rounded-t-3xl border border-ink/10 bg-white shadow-2xl motion-safe:animate-slideUp sm:rounded-3xl">
            <div className="flex items-start justify-between gap-3 border-b border-ink/10 px-5 py-4">
              <h3 id="explain-dialog-title" className="font-display text-lg font-semibold text-ink">
                Object explanation
              </h3>
              <button
                type="button"
                className="rounded-lg p-2 text-ink-faint transition hover:bg-canvas-muted hover:text-ink"
                onClick={() => setModalOpen(false)}
                aria-label="Close"
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" />
                </svg>
              </button>
            </div>
            <div className="overflow-y-auto px-5 py-4">
              <p className="break-all text-xs text-ink-faint">{explainTitle}</p>
              {explainLoading && (
                <p className="mt-4 flex items-center gap-2 text-sm text-ink-soft">
                  <Spinner className="h-4 w-4" /> Asking Ollama…
                </p>
              )}
              {explainErr && (
                <div className="mt-4 whitespace-pre-line rounded-xl border border-red-200 bg-red-50 p-3 text-sm leading-relaxed text-red-900">
                  {explainErr}
                </div>
              )}
              {!explainLoading &&
                explainSteps.map((step, i) => (
                  <div key={i} className="mt-4 border-l-2 border-neon pl-4 first:mt-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
                      Part {i + 1} of {explainSteps.length}
                    </p>
                    <p className="mt-1 text-sm leading-relaxed text-ink">{step}</p>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 z-[60] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 rounded-2xl border border-ink/10 bg-white/95 px-4 py-3 text-center text-sm text-ink shadow-xl backdrop-blur motion-safe:animate-fadeIn"
        >
          {toast}
        </div>
      )}
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  tone,
  muted,
  enterDelayMs = 0,
}: {
  label: string;
  value: string;
  tone?: "ok" | "bad";
  muted?: boolean;
  enterDelayMs?: number;
}) {
  const color =
    tone === "ok" ? "text-emerald-700" : tone === "bad" ? "text-red-600" : muted ? "text-ink-faint" : "text-ink";
  return (
    <div
      className="rounded-2xl border border-ink/10 bg-white/70 p-4 shadow-sm backdrop-blur-sm transition duration-300 motion-safe:animate-fadeInUp hover:-translate-y-0.5 hover:border-ink/18 hover:shadow-md"
      style={{ animationDelay: `${enterDelayMs}ms` }}
    >
      <p className="text-[11px] font-medium uppercase tracking-wide text-ink-faint">{label}</p>
      <p className={`mt-1 font-display text-2xl font-semibold tabular-nums ${color}`}>{value}</p>
    </div>
  );
}

function Spinner({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg className={`animate-spin text-ink ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}
