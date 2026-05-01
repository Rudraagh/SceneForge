/**
 * Marketing sections: hero, platform capabilities, architecture, interoperability,
 * research, observability, positioning, sample prompts, requirements, privacy, FAQ,
 * quick start, workflow, footer. Layout uses max-w-7xl for alignment with the studio shell.
 */

import { useCallback, useState, type ReactNode } from "react";

function CopyInlineButton({ text, children, className = "" }: { text: string; children: ReactNode; className?: string }) {
  const [copied, setCopied] = useState(false);
  const onCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard may be denied */
    }
  }, [text]);
  return (
    <button
      type="button"
      onClick={() => void onCopy()}
      className={`inline-flex min-h-[44px] min-w-[4.5rem] shrink-0 items-center justify-center rounded-lg border border-ink/12 bg-white/90 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-ink shadow-sm transition hover:border-ink/20 hover:bg-white active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-neon/50 sm:min-h-0 sm:py-1.5 ${className}`.trim()}
      aria-label={copied ? "Copied" : "Copy to clipboard"}
    >
      {copied ? "Copied" : children}
    </button>
  );
}

function HeroWireArt() {
  return (
    <div
      className="flex h-full min-h-[220px] w-full max-w-[420px] items-center justify-center motion-safe:animate-floatSoft motion-reduce:animate-none lg:min-h-[300px]"
      aria-hidden
    >
      <svg viewBox="0 0 280 240" className="h-auto w-full max-w-[340px] text-ink" fill="none">
        <g stroke="currentColor" strokeWidth="0.65" opacity="0.16">
          <path d="M24 178 L140 88 L256 178 M140 88 L140 28 L256 88 M140 88 L24 88" />
          <path d="M72 198 L140 152 L208 198 M140 152 V118" />
          <ellipse cx="218" cy="52" rx="36" ry="36" />
          <path d="M182 52 h72 M218 16 v72" />
          <path d="M12 64 Q72 18 140 48 T268 58" />
          <circle cx="48" cy="118" r="3" fill="currentColor" opacity="0.35" stroke="none" />
          <circle cx="232" cy="168" r="2.5" fill="currentColor" opacity="0.3" stroke="none" />
        </g>
      </svg>
    </div>
  );
}

export function MarketingHero({ onStart }: { onStart: () => void }) {
  return (
    <section className="relative overflow-hidden border-b border-ink/10">
      <div className="relative mx-auto max-w-7xl px-4 pb-16 pt-12 sm:pb-20 sm:pt-16 md:px-6 lg:px-8">
        <div className="grid items-center gap-10 lg:grid-cols-[minmax(0,1.05fr)_minmax(260px,0.95fr)] lg:gap-12 xl:gap-16">
          <div className="flex w-full max-w-xl flex-col items-center text-center lg:max-w-none lg:items-start lg:text-left">
            <p
              className="mb-5 inline-flex items-center gap-2 rounded-full border border-ink/10 bg-white/60 px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-ink-soft backdrop-blur-sm motion-safe:animate-fadeInDown"
              style={{ animationDelay: "40ms" }}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-ink motion-safe:animate-pulse" />
              OpenUSD · Blueprint-aware layout · Local LLM
            </p>
            <h1 className="font-display text-[2.35rem] font-semibold leading-[1.05] tracking-tight text-ink sm:text-5xl md:text-6xl md:leading-[1.02] motion-safe:animate-fadeInUp motion-safe:[animation-delay:90ms]">
              From spatial intent to a{" "}
              <span className="relative inline-block rounded-md bg-neon px-2 py-0.5 font-semibold text-ink shadow-sm">
                production-ready OpenUSD scene
              </span>
            </h1>
            <div className="mt-6 max-w-2xl space-y-4 text-center text-base leading-relaxed text-ink-soft sm:text-lg lg:text-left motion-safe:animate-fadeInUp motion-safe:[animation-delay:160ms]">
              <p>
                <span className="font-medium text-ink">SceneForge</span> is an authoring stack that turns natural-language intent—and optional 2D blueprint imagery—into structured{" "}
                <span className="font-medium text-ink">Universal Scene Description (USD)</span>. A Python pipeline scores layout, resolves meshes from local caches and curated sources, and exports USDA suitable for DCC tools such as Blender.
              </p>
              <p>
                The workflow supports teaching and technical review: generate a scene, inspect prims in an interactive 3D view, then optionally attach short, context-aware explanations via a{" "}
                <span className="font-medium text-ink">local Ollama</span> model so sensitive geometry never leaves your machine. The same engine powers this interface and the original Streamlit UI, with a FastAPI layer for integration and demos.
              </p>
            </div>
            <div className="mt-10 flex w-full max-w-2xl flex-col items-stretch gap-3 motion-safe:animate-fadeInUp motion-safe:[animation-delay:240ms] sm:flex-row sm:flex-wrap sm:justify-center lg:max-w-none lg:justify-start">
              <button
                type="button"
                onClick={onStart}
                className="relative inline-flex min-h-[48px] flex-1 items-center justify-center overflow-hidden rounded-xl bg-neon px-6 py-3.5 text-sm font-semibold uppercase tracking-wide text-ink shadow-md transition hover:bg-neon-hover active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-ink/30 sm:flex-none sm:min-h-0 sm:px-8"
              >
                <span className="pointer-events-none absolute inset-0 -translate-x-full skew-x-[-10deg] bg-gradient-to-r from-transparent via-black/10 to-transparent motion-safe:animate-shimmerSweep" />
                <span className="relative z-[1]">Open studio</span>
              </button>
              <a
                href="#workflow"
                className="inline-flex min-h-[48px] flex-1 items-center justify-center rounded-xl border border-ink/15 bg-white/70 px-6 py-3.5 text-sm font-medium text-ink shadow-sm backdrop-blur-sm transition duration-300 hover:border-ink/25 hover:bg-white active:scale-[0.98] sm:flex-none sm:min-h-0"
              >
                How it works
              </a>
              <a
                href="#sample-prompts"
                className="inline-flex min-h-[48px] flex-1 items-center justify-center rounded-xl border border-ink/12 bg-white/50 px-6 py-3.5 text-sm font-medium text-ink-soft shadow-sm backdrop-blur-sm transition duration-300 hover:border-ink/20 hover:bg-white/80 hover:text-ink active:scale-[0.98] sm:flex-none sm:min-h-0"
              >
                Sample prompts
              </a>
            </div>
          </div>

          <div className="hidden justify-center lg:flex lg:justify-end xl:pr-4">
            <HeroWireArt />
          </div>
        </div>
      </div>
    </section>
  );
}

export function PlatformCapabilitiesSection() {
  const pillars = [
    {
      title: "Layout intelligence",
      body: "Rule-based and optional LLM-driven scene graphs respect prompts and blueprint regions, then iterate on spacing and relational consistency before meshes are bound.",
    },
    {
      title: "Asset orchestration",
      body: "The resolver blends local libraries, normalized caches, Objaverse candidates, and procedural fallbacks so each prim receives a defensible mesh choice with traceable provenance.",
    },
    {
      title: "Review-ready outputs",
      body: "USDA exports, metrics, and logs are produced for reproducible grading, lab notebooks, or pipeline gates—so reviewers see not only geometry but the decisions behind it.",
    },
  ];
  return (
    <section id="capabilities" className="scroll-mt-24 border-b border-ink/10 bg-canvas py-14 sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center md:mx-0 md:max-w-none md:text-left">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">What the platform delivers</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            SceneForge is designed as a teaching and research vehicle: deterministic where possible, augmented by models where helpful, and always inspectable before you commit to downstream rendering or grading.
          </p>
        </div>
        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {pillars.map((p) => (
            <article
              key={p.title}
              className="rounded-2xl border border-ink/10 bg-white/55 p-6 shadow-sm backdrop-blur-sm transition hover:border-ink/18 hover:shadow-md"
            >
              <h3 className="font-display text-lg font-semibold text-ink">{p.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-ink-soft">{p.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function ArchitectureStackSection() {
  const layers = [
    { label: "Authoring core", detail: "Python pipeline (`direct_usd_scene.py`), blueprint parser, layout refinement, Objaverse loader." },
    { label: "Interfaces", detail: "Streamlit reference UI, FastAPI (`api_app.py`), and this Vite + React studio sharing the same service layer." },
    { label: "Inference", detail: "Optional Ollama JSON scene planning and prim-level explanations; configurable models and context windows." },
    { label: "Visualization", detail: "Plotly 3D prim picker aligned with USD paths for classroom walkthroughs." },
  ];
  return (
    <section id="architecture" className="scroll-mt-24 border-b border-ink/10 bg-white/40 py-14 backdrop-blur-[2px] sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center md:mx-0 md:max-w-none md:text-left">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">Architecture & stack</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            The system favors small, composable modules so you can reason about each concern—graph construction, asset retrieval, USD authoring, and UI—without a monolithic runtime dependency.
          </p>
        </div>
        <div className="mt-10 grid gap-10 lg:grid-cols-2 lg:items-start">
          <div className="space-y-4 text-sm leading-relaxed text-ink-soft sm:text-base">
            <p>
              At the center is a <span className="font-medium text-ink">Pixar USD</span> authoring path that runs on standard Python environments. Scene graphs can be produced deterministically for repeatability, or enriched with structured JSON from a local LLM when teams want to experiment with language-conditioned layouts.
            </p>
            <p>
              Surrounding services handle IO, subprocess orchestration, and HTTP boundaries: FastAPI exposes generation, logs, metrics, and Ollama-backed explanation endpoints, while the React client focuses on responsive layout, accessibility, and clear operator feedback during long-running jobs.
            </p>
          </div>
          <ul className="space-y-3 rounded-2xl border border-ink/10 bg-white/60 p-5 shadow-sm">
            {layers.map((row) => (
              <li key={row.label} className="border-b border-ink/10 pb-3 last:border-0 last:pb-0">
                <p className="font-display text-sm font-semibold text-ink">{row.label}</p>
                <p className="mt-1 text-sm text-ink-soft">{row.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

export function InteroperabilitySection() {
  const chips = ["USDA / USD", "Blender", "FastAPI", "Vite + React", "Plotly", "Ollama (local)", "Streamlit (legacy UI)"];
  return (
    <section id="interop" className="scroll-mt-24 border-b border-ink/10 bg-canvas py-14 sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center md:mx-0 md:max-w-none md:text-left">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">Interoperability & operations</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            SceneForge meets teams where they already work: standard file formats, familiar DCC entry points, and local inference so air-gapped or policy-heavy environments remain viable.
          </p>
        </div>
        <div className="mt-6 flex flex-wrap justify-center gap-2 md:justify-start">
          {chips.map((c) => (
            <span
              key={c}
              className="rounded-full border border-ink/12 bg-white/70 px-3 py-1.5 text-xs font-medium text-ink-soft shadow-sm"
            >
              {c}
            </span>
          ))}
        </div>
        <div className="mt-8 grid gap-6 text-sm leading-relaxed text-ink-soft sm:grid-cols-2 sm:text-base">
          <p>
            Exported scenes target <span className="font-medium text-ink">OpenUSD</span> text layers for diffing and version control. Operators can launch Blender against the generated path from either UI surface, preserving a tight loop between automated layout and manual polish.
          </p>
          <p>
            Environment variables configure model endpoints, asset search limits, and Blender binaries—so the same repository can move from a student laptop to a shared lab host without forked code paths.
          </p>
        </div>
      </div>
    </section>
  );
}

export function ResearchUseCasesSection() {
  const cases = [
    {
      title: "Instructional labs",
      body: "Pair deterministic templates with optional LLM variation so cohorts can compare rule-based scenes against model-assisted layouts on identical prompts.",
    },
    {
      title: "Pipeline literacy",
      body: "Expose logs, metrics, and USD paths explicitly so learners trace how blueprint colors, relation hints, and asset scoring influence the final prim hierarchy.",
    },
    {
      title: "Demonstration & review",
      body: "Use the web studio for responsive walkthroughs, or Streamlit for rapid scripting—both surfaces call the same generation and explanation endpoints.",
    },
  ];
  return (
    <section id="research" className="scroll-mt-24 border-b border-ink/10 bg-white/40 py-14 backdrop-blur-[2px] sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center md:mx-0 md:max-w-none md:text-left">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">Research & teaching scenarios</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            SceneForge is intentionally opinionated about observability: every run should be explainable to a reviewer or TA without opening proprietary hosts or cloud consoles.
          </p>
        </div>
        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {cases.map((c) => (
            <article key={c.title} className="rounded-2xl border border-ink/10 bg-white/60 p-6 shadow-sm">
              <h3 className="font-display text-base font-semibold text-ink">{c.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-ink-soft">{c.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function ObservabilitySection() {
  const bullets = [
    "Return codes and structured metrics after each generation for pass/fail automation.",
    "Pipeline explanation lines summarize scoring, refinement, and asset decisions in plain language.",
    "Full subprocess logs retained in the UI for diffing across runs or attaching to lab submissions.",
    "3D prim picker binds to concrete USD paths so explanations and manual edits target the same identifiers.",
  ];
  return (
    <section id="observability" className="scroll-mt-24 border-b border-ink/10 bg-canvas py-14 sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center md:mx-0 md:max-w-none md:text-left">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">Observability & review signals</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            Beyond geometry, reviewers need evidence. SceneForge surfaces machine-readable outcomes alongside human-readable narratives so you can defend a scene in a design critique or a grading rubric.
          </p>
        </div>
        <ul className="mt-8 max-w-4xl space-y-3 text-sm leading-relaxed text-ink-soft sm:text-base">
          {bullets.map((b) => (
            <li key={b} className="flex gap-3 rounded-xl border border-ink/10 bg-white/55 px-4 py-3 shadow-sm">
              <span className="mt-0.5 font-display text-neon-dim" aria-hidden>
                ●
              </span>
              <span>{b}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function PositioningSection() {
  const rows = [
    {
      title: "SceneForge",
      tag: "Structured USD · Teaching",
      highlight: true,
      points: [
        "Targets OpenUSD text layers you can diff, grade, and open in Blender or other USD tools.",
        "Blueprint-aware placement plus explicit logs, metrics, and prim paths for review.",
        "Runs locally: rule mode stays deterministic; AI mode can use Ollama on your machine only.",
      ],
    },
    {
      title: "Generic 3D generation",
      tag: "Mesh-first · Often cloud",
      highlight: false,
      points: [
        "Many tools optimize for single meshes or proprietary viewers—not a prim-level USDA teaching story.",
        "Harder to trace why an object landed where it did without pipeline-grade instrumentation.",
        "Cloud-hosted models may conflict with data policies even when outputs look impressive.",
      ],
    },
    {
      title: "Hand-authored USD",
      tag: "Maximum control",
      highlight: false,
      points: [
        "Ideal for final hero assets and bespoke shading—but slow for layout what-if experiments.",
        "You carry all relational and asset decisions manually unless you build your own automation.",
        "SceneForge sits between: automated layout with export you can still hand-edit in a DCC.",
      ],
    },
  ];
  return (
    <section id="positioning" className="scroll-mt-24 border-b border-ink/10 bg-white/40 py-14 backdrop-blur-[2px] sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center md:mx-0 md:max-w-none md:text-left">
          <p className="font-display text-xs font-semibold uppercase tracking-widest text-ink-faint">When to reach for it</p>
          <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">SceneForge vs other approaches</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            A compact comparison—not a vendor matrix. Use SceneForge when you care about USD structure, pedagogy, or repeatable pipeline signals alongside geometry.
          </p>
        </div>
        <div className="mt-10 grid gap-4 sm:gap-5 lg:grid-cols-3">
          {rows.map((row) => (
            <article
              key={row.title}
              className={`flex h-full flex-col rounded-2xl border p-5 shadow-sm transition sm:p-6 ${
                row.highlight
                  ? "border-neon/50 bg-gradient-to-b from-white/90 to-neon/15 ring-1 ring-neon/30"
                  : "border-ink/10 bg-white/60 hover:border-ink/16 hover:shadow-md"
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-display text-lg font-semibold text-ink">{row.title}</h3>
                <span className="rounded-full border border-ink/10 bg-canvas-muted/80 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-soft">
                  {row.tag}
                </span>
              </div>
              <ul className="mt-4 flex flex-1 flex-col gap-3 text-sm leading-relaxed text-ink-soft">
                {row.points.map((p) => (
                  <li key={p} className="flex gap-2.5">
                    <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-neon-dim" aria-hidden />
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function SamplePromptsSection() {
  const samples: { prompt: string; hint: "prompt" | "blueprint"; label: string }[] = [
    { prompt: "a medieval classroom with wooden desks and a blackboard", hint: "prompt", label: "Prompt only" },
    {
      prompt: "open-plan studio with drafting table, bookshelf, and north-facing windows along one wall",
      hint: "blueprint",
      label: "Best with blueprint",
    },
    { prompt: "minimal solar system with labeled planets in stable orbits", hint: "prompt", label: "Prompt only" },
    {
      prompt: "single-story home: living room adjoining kitchen; use color-coded zones on the blueprint for each room",
      hint: "blueprint",
      label: "Best with blueprint",
    },
    {
      prompt: "outdoor courtyard with stone benches, a central fountain, and shaded trees along the eastern edge",
      hint: "prompt",
      label: "Prompt only",
    },
    {
      prompt: "small lecture hall: instructor desk near the board, rows of student desks facing forward, rear exit door",
      hint: "blueprint",
      label: "Best with blueprint",
    },
  ];
  return (
    <section id="sample-prompts" className="scroll-mt-24 border-b border-ink/10 bg-canvas py-14 sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center md:mx-0 md:max-w-none md:text-left">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">Sample prompts</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            Copy a line into the studio as a starting point. Blueprint-tagged ideas work best when your PNG regions line up with the color legend the pipeline expects.
          </p>
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 sm:gap-5 xl:grid-cols-3">
          {samples.map((s) => (
            <article
              key={s.prompt}
              className="flex flex-col rounded-2xl border border-ink/10 bg-white/65 p-4 shadow-sm backdrop-blur-sm transition hover:border-ink/18 hover:shadow-md sm:p-5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span
                  className={
                    s.hint === "blueprint"
                      ? "rounded-full border border-forge-accent/25 bg-forge-accent/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-forge-900"
                      : "rounded-full border border-ink/10 bg-canvas-muted px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-soft"
                  }
                >
                  {s.label}
                </span>
                <CopyInlineButton text={s.prompt}>Copy</CopyInlineButton>
              </div>
              <p className="mt-3 flex-1 text-sm leading-relaxed text-ink sm:text-[15px]">{s.prompt}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function RequirementsSection() {
  const rows = [
    { k: "Python", v: "3.10 or newer recommended (3.9+ may work depending on USD wheels)." },
    { k: "Node.js", v: "18 LTS or newer for the Vite dev server and build tooling." },
    { k: "Ollama", v: "Optional—required only for AI scene mode and prim explanations." },
    { k: "Disk", v: "Reserve several GB for normalized caches and remote asset downloads when Objaverse or free sources are enabled." },
  ];
  return (
    <section id="requirements" className="scroll-mt-24 border-b border-ink/10 bg-white/40 py-14 backdrop-blur-[2px] sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center md:mx-0 md:max-w-none md:text-left">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">Requirements</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            Pin installs from the manifests at the repository root and under <span className="font-medium text-ink">frontend/</span>. Paths below are relative to your clone.
          </p>
        </div>
        <div className="mt-8 overflow-x-auto rounded-2xl border border-ink/10 bg-white/70 shadow-sm [-webkit-overflow-scrolling:touch]">
          <table className="w-full min-w-[300px] border-collapse text-left text-sm">
            <caption className="sr-only">Runtime requirements for SceneForge</caption>
            <thead className="border-b border-ink/10 bg-canvas-muted/60">
              <tr>
                <th scope="col" className="px-4 py-3 font-display font-semibold text-ink sm:px-5">
                  Topic
                </th>
                <th scope="col" className="px-4 py-3 font-display font-semibold text-ink sm:px-5">
                  Guidance
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink/10 text-ink-soft">
              {rows.map((r) => (
                <tr key={r.k} className="transition hover:bg-white/80">
                  <th scope="row" className="align-top px-4 py-3.5 font-medium text-ink sm:px-5 sm:py-4">
                    {r.k}
                  </th>
                  <td className="px-4 py-3.5 sm:px-5 sm:py-4">{r.v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col rounded-2xl border border-ink/10 bg-white/65 p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-5">
            <div className="min-w-0">
              <p className="font-display text-sm font-semibold text-ink">Python manifest</p>
              <code className="mt-1 block truncate text-xs text-ink-soft sm:text-sm">requirements.txt</code>
            </div>
            <CopyInlineButton text="requirements.txt" className="mt-3 sm:mt-0">
              Copy path
            </CopyInlineButton>
          </div>
          <div className="flex flex-col rounded-2xl border border-ink/10 bg-white/65 p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-5">
            <div className="min-w-0">
              <p className="font-display text-sm font-semibold text-ink">Frontend lockfile</p>
              <code className="mt-1 block truncate text-xs text-ink-soft sm:text-sm">frontend/package-lock.json</code>
            </div>
            <CopyInlineButton text="frontend/package-lock.json" className="mt-3 sm:mt-0">
              Copy path
            </CopyInlineButton>
          </div>
        </div>
        <p className="mt-4 text-center text-xs text-ink-faint md:text-left">
          Install commands live in{" "}
          <a href="#quick-start" className="font-medium text-ink-soft underline decoration-ink/20 underline-offset-2 transition hover:text-ink">
            Quick start
          </a>{" "}
          below. Open the copied paths in your editor or terminal from the repo root.
        </p>
      </div>
    </section>
  );
}

export function PrivacyDataFlowSection() {
  const lanes = [
    {
      title: "Prompts & blueprints",
      body: "The web studio sends your text and optional blueprint image to your local FastAPI process. SceneForge does not ship them to a vendor-hosted inference API by default.",
    },
    {
      title: "Ollama traffic",
      body: "When explanations or AI scene planning are enabled, the API talks to Ollama on your machine (typically localhost). Model weights and prompts for those calls stay off the public internet.",
    },
    {
      title: "Asset resolver",
      body: "Objaverse search, free-source fetches, and remote normalization use outbound HTTPS unless you disable those sources. Cached assets and local libraries avoid repeat downloads.",
    },
  ];
  return (
    <section id="privacy" className="scroll-mt-24 border-b border-ink/10 bg-canvas py-14 sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center md:mx-0 md:max-w-none md:text-left">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">Privacy & data flow</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            A tight mental model for labs and policy reviews: what stays on localhost, what touches your local LLM runtime, and what can still reach the network for assets.
          </p>
        </div>
        <div className="mt-10 grid gap-5 sm:gap-6 lg:grid-cols-3">
          {lanes.map((lane, i) => (
            <article
              key={lane.title}
              className="relative flex h-full flex-col overflow-hidden rounded-2xl border border-ink/10 bg-white/65 p-5 shadow-sm sm:p-6"
            >
              <div className="absolute right-3 top-3 font-display text-4xl font-bold leading-none text-neon/20 sm:right-4 sm:top-4 sm:text-5xl">
                {i + 1}
              </div>
              <h3 className="relative max-w-[88%] font-display text-base font-semibold text-ink sm:text-lg">{lane.title}</h3>
              <p className="mt-3 flex-1 text-sm leading-relaxed text-ink-soft">{lane.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function FAQSection() {
  const items: { q: string; a: string }[] = [
    {
      q: "Do I need a GPU?",
      a: "No dedicated GPU is required for the default pipeline and UI. Generation is CPU-oriented Python plus USD I/O; a GPU helps your OS generally but is not a gate. Optional Ollama performance depends on the model you pick and whether it uses GPU acceleration locally.",
    },
    {
      q: "Blender vs USDA only?",
      a: "SceneForge emits USDA you can version, diff, and inspect without Blender. Blender is an optional convenience: launch it from the UI when you want a familiar DCC view or manual polish. You can stop at the file export if your workflow is USD-native.",
    },
    {
      q: "What stays local with Ollama?",
      a: "Prim explanations and AI-assisted scene planning are requested from your FastAPI app to the Ollama HTTP API on your machine. The browser does not call Ollama directly. Keep Ollama bound to localhost in untrusted networks so other devices cannot drive inference.",
    },
    {
      q: "Objaverse and network usage?",
      a: "When Objaverse or free remote sources are enabled, the resolver performs outbound HTTPS to search, download, or normalize meshes. Disable those toggles (and rely on local caches or procedural fallbacks) for fully offline runs after you have seeded assets.",
    },
    {
      q: "Difference between rule and AI mode?",
      a: "Rule mode follows deterministic templates and constraints for repeatable teaching runs. AI mode asks your configured Ollama model for structured scene JSON first, then falls back to rules if the model is offline or returns invalid structure—so the UI stays usable in either case.",
    },
  ];
  return (
    <section id="faq" className="scroll-mt-24 border-b border-ink/10 bg-white/40 py-14 backdrop-blur-[2px] sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center md:mx-0 md:max-w-none md:text-left">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">FAQ</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            Short answers for operators and course staff. For ports and install order, pair this section with{" "}
            <a href="#requirements" className="font-medium text-ink underline decoration-ink/20 underline-offset-2 hover:text-ink">
              Requirements
            </a>{" "}
            and{" "}
            <a href="#quick-start" className="font-medium text-ink underline decoration-ink/20 underline-offset-2 hover:text-ink">
              Quick start
            </a>
            .
          </p>
        </div>
        <div className="mx-auto mt-8 max-w-3xl space-y-3 md:mx-0 lg:max-w-4xl">
          {items.map((item) => (
            <details
              key={item.q}
              className="group rounded-2xl border border-ink/10 bg-white/70 shadow-sm transition open:border-ink/18 open:shadow-md"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-2xl px-4 py-4 text-left font-display text-sm font-semibold text-ink outline-none transition hover:bg-white/90 sm:px-5 sm:text-base [&::-webkit-details-marker]:hidden">
                <span className="min-w-0 pr-2">{item.q}</span>
                <svg
                  className="h-5 w-5 shrink-0 text-ink-soft transition-transform duration-200 group-open:rotate-180"
                  viewBox="0 0 20 20"
                  fill="none"
                  aria-hidden
                >
                  <path d="M5 8l5 5 5-5" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </summary>
              <div className="border-t border-ink/10 px-4 pb-4 pt-0 sm:px-5 sm:pb-5">
                <p className="pt-3 text-sm leading-relaxed text-ink-soft sm:text-base">{item.a}</p>
              </div>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

export function QuickStartSection() {
  const steps = [
    {
      n: "1",
      title: "Python environment",
      body: "From the repository root, install dependencies with pip so FastAPI, USD tooling, and pipeline modules resolve consistently across machines.",
      code: "python -m pip install -r requirements.txt",
    },
    {
      n: "2",
      title: "API process",
      body: "Launch the FastAPI application on a fixed port; the Vite dev server proxies API routes for local development.",
      code: "uvicorn api_app:app --reload --host 127.0.0.1 --port 8765",
    },
    {
      n: "3",
      title: "Web studio",
      body: "Install frontend packages once, then start the Vite server and open the studio in your browser.",
      code: "cd frontend && npm install && npm run dev",
    },
    {
      n: "4",
      title: "Optional Ollama",
      body: "Start the Ollama daemon and pull the models referenced by your environment variables before using AI scene mode or object explanations.",
      code: "ollama serve",
    },
  ];
  return (
    <section id="quick-start" className="scroll-mt-24 border-b border-ink/10 bg-white/40 py-14 backdrop-blur-[2px] sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center md:mx-0 md:max-w-none md:text-left">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">Run locally in four steps</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            These commands mirror <span className="font-medium text-ink">frontend/README.md</span>; adjust ports or profiles if your lab policy requires it. Streamlit remains available via{" "}
            <code className="rounded bg-canvas-muted px-1 py-0.5 text-xs text-ink">streamlit run app.py</code> when you prefer that surface.
          </p>
        </div>
        <ol className="mt-10 grid gap-5 lg:grid-cols-2">
          {steps.map((s) => (
            <li
              key={s.n}
              className="flex gap-4 rounded-2xl border border-ink/10 bg-white/65 p-5 shadow-sm"
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-neon font-display text-sm font-bold text-ink">
                {s.n}
              </span>
              <div className="min-w-0">
                <h3 className="font-display text-base font-semibold text-ink">{s.title}</h3>
                <p className="mt-1 text-sm text-ink-soft">{s.body}</p>
                <pre className="mt-3 overflow-x-auto rounded-lg border border-ink/10 bg-canvas-muted/80 p-3 font-mono text-[11px] text-ink-soft sm:text-xs">
                  {s.code}
                </pre>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

const steps = [
  {
    title: "Intent & placement",
    body: "Capture a scene description and, when needed, a color-coded blueprint so spatial constraints inform object placement before geometry is resolved.",
    icon: "◇",
  },
  {
    title: "Author & export",
    body: "Run the pipeline to score layout, retrieve or synthesize meshes, and emit USDA for review in Blender or downstream USD tooling.",
    icon: "◈",
  },
  {
    title: "Spatial QA",
    body: "Inspect authored prims in an interactive 3D view to validate coverage, relationships, and scale before sign-off or iteration.",
    icon: "◎",
  },
  {
    title: "Narrated review",
    body: "Optionally invoke Ollama on your workstation for concise, scene-grounded explanations of selected prims—ideal for walkthroughs and coursework.",
    icon: "✦",
  },
];

export function WorkflowSection() {
  return (
    <section id="workflow" className="scroll-mt-24 border-b border-ink/10 bg-white/40 py-14 backdrop-blur-[2px] sm:py-16">
      <div className="mx-auto max-w-7xl px-4 md:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center motion-safe:animate-fadeInUp md:mx-0 md:max-w-none md:text-left">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">End-to-end workflow</h2>
          <p className="mt-2 text-sm text-ink-soft sm:text-base">
            Each stage below maps to the same Python services: capture intent, author USD, validate in 3D, and document objects with local inference—whether you use this web studio or the Streamlit reference UI.
          </p>
        </div>
        <div className="mt-10 grid items-stretch gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => (
            <article
              key={s.title}
              className="group flex h-full flex-col rounded-2xl border border-ink/10 bg-white/50 p-5 shadow-sm backdrop-blur-sm transition duration-300 ease-out motion-safe:animate-fadeInUp hover:-translate-y-1 hover:border-ink/20 hover:shadow-md"
              style={{ animationDelay: `${140 + i * 90}ms` }}
            >
              <span className="font-display text-2xl text-ink/50 transition duration-300 group-hover:scale-110 group-hover:text-ink">
                {s.icon}
              </span>
              <h3 className="mt-3 font-display text-base font-semibold text-ink">{s.title}</h3>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-ink-soft text-balance">{s.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-ink/10 bg-canvas py-10 motion-safe:animate-fadeInUp">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 md:flex-row md:items-center md:justify-between md:px-6 lg:px-8">
        <div>
          <p className="font-display text-lg font-semibold text-ink">SceneForge</p>
          <p className="mt-1 max-w-md text-sm text-ink-faint">FastAPI · Vite · Plotly · Ollama</p>
        </div>
        <nav
          className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm text-ink-soft sm:flex sm:flex-wrap sm:gap-x-6 sm:gap-y-2"
          aria-label="On this page"
        >
          <a href="#capabilities" className="transition hover:text-ink">
            Capabilities
          </a>
          <a href="#architecture" className="transition hover:text-ink">
            Architecture
          </a>
          <a href="#interop" className="transition hover:text-ink">
            Interop
          </a>
          <a href="#research" className="transition hover:text-ink">
            Research
          </a>
          <a href="#observability" className="transition hover:text-ink">
            Observability
          </a>
          <a href="#positioning" className="transition hover:text-ink">
            Positioning
          </a>
          <a href="#sample-prompts" className="transition hover:text-ink">
            Prompts
          </a>
          <a href="#requirements" className="transition hover:text-ink">
            Requirements
          </a>
          <a href="#privacy" className="transition hover:text-ink">
            Privacy
          </a>
          <a href="#faq" className="transition hover:text-ink">
            FAQ
          </a>
          <a href="#quick-start" className="transition hover:text-ink">
            Quick start
          </a>
          <a href="#workflow" className="transition hover:text-ink">
            Workflow
          </a>
          <a href="#studio" className="transition hover:text-ink">
            Studio
          </a>
        </nav>
      </div>
    </footer>
  );
}
