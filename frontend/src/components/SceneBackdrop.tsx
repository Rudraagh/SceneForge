/**
 * Light editorial backdrop: animated topo drift, rotating SVG orbit, slow conic wash,
 * optional looped video (hero-loop.mp4 or backdrop.mp4), blobs, grids, rings.
 */

import { useEffect, useState } from "react";

function resolvePublicUrl(path: string): string {
  const base = import.meta.env.BASE_URL || "/";
  const normalized = base.endsWith("/") ? base : `${base}/`;
  return `${normalized}${path.replace(/^\//, "")}`;
}

const VIDEO_CANDIDATES = ["hero-loop.mp4", "backdrop.mp4"] as const;

export function SceneBackdrop() {
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (const name of VIDEO_CANDIDATES) {
        const url = resolvePublicUrl(name);
        try {
          const res = await fetch(url, { method: "HEAD", mode: "same-origin" });
          if (!cancelled && res.ok) {
            setVideoUrl(url);
            return;
          }
        } catch {
          /* try next */
        }
      }
      if (!cancelled) setVideoUrl(null);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const topoSrc = resolvePublicUrl("bg-topo.svg");
  const orbitSrc = resolvePublicUrl("bg-orbit.svg");

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-canvas" aria-hidden>
      <div className="absolute -left-[20%] top-[-10%] h-[75vmin] w-[75vmin] rounded-full bg-canvas-muted blur-[90px] motion-safe:animate-blobDrift" />
      <div
        className="absolute -right-[18%] top-[15%] h-[65vmin] w-[65vmin] rounded-full bg-canvas-subtle blur-[85px] motion-safe:animate-blobDriftSlow"
        style={{ animationDelay: "-6s" }}
      />
      <div
        className="absolute bottom-[-22%] left-[10%] h-[70vmin] w-[70vmin] rounded-full bg-[#e0ddd6] blur-[100px] motion-safe:animate-blobDrift"
        style={{ animationDelay: "-14s" }}
      />
      <div className="absolute left-[35%] top-[40%] h-[40vmin] w-[40vmin] rounded-full bg-white/50 blur-[70px] motion-safe:animate-blobDriftSlow" />

      {/* Slow conic light wash (no raster image) */}
      <div
        className="absolute -left-[20%] top-[-30%] h-[160%] w-[160%] opacity-[0.07] motion-safe:animate-conicSpin motion-reduce:animate-none"
        style={{
          background:
            "conic-gradient(from 0deg, transparent 0deg, rgba(232,255,61,0.35) 45deg, transparent 90deg, rgba(91,140,255,0.2) 200deg, transparent 280deg)",
        }}
      />

      {/* SMIL-animated orbit (vector “motion graphics”) */}
      <object
        type="image/svg+xml"
        data={orbitSrc}
        className="absolute right-[-8%] top-[8%] h-[min(72vmin,560px)] w-[min(72vmin,560px)] border-0 opacity-[0.11] outline-none mix-blend-multiply motion-reduce:opacity-[0.08]"
        aria-hidden
      />

      {/* Large faint rings with slow opacity pulse */}
      <div className="motion-safe:animate-ringPulse absolute -left-[8%] top-[12%]" style={{ animationDelay: "0s" }}>
        <div className="h-[min(85vw,520px)] w-[min(85vw,520px)] rounded-full border border-ink/[0.06]" />
      </div>
      <div className="motion-safe:animate-ringPulse absolute left-[3%] top-[18%]" style={{ animationDelay: "-4s" }}>
        <div className="h-[min(70vw,420px)] w-[min(70vw,420px)] rounded-full border border-ink/[0.05]" />
      </div>
      <div className="motion-safe:animate-ringPulse absolute -right-[5%] bottom-[8%]" style={{ animationDelay: "-7s" }}>
        <div className="h-[min(75vw,480px)] w-[min(75vw,480px)] rounded-full border border-ink/[0.055]" />
      </div>

      {videoUrl ? (
        <div className="absolute left-1/2 top-1/2 flex h-[130%] w-[130%] -translate-x-1/2 -translate-y-1/2 items-center justify-center">
          <div className="h-full w-full origin-center motion-safe:animate-videoBloom motion-reduce:animate-none">
            <video
              className="h-full w-full object-cover opacity-[0.14] mix-blend-multiply grayscale contrast-90"
              autoPlay
              muted
              loop
              playsInline
              preload="metadata"
            >
              <source src={videoUrl} type="video/mp4" />
            </video>
          </div>
        </div>
      ) : null}

      <div className="scene-depth-grid absolute inset-0 opacity-[0.65]" />
      <div className="scene-diagonal-lines absolute inset-0 opacity-70" />

      <div
        className="absolute inset-0 opacity-[0.5] motion-safe:animate-topoDrift motion-reduce:animate-none"
        style={{
          backgroundImage: `url('${topoSrc}')`,
          backgroundSize: "min(900px, 120vw) auto",
          backgroundPosition: "38% 18%",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.28] motion-safe:animate-topoDrift motion-reduce:animate-none"
        style={{
          animationDelay: "-18s",
          backgroundImage: `url('${topoSrc}')`,
          backgroundSize: "min(700px, 95vw) auto",
          backgroundPosition: "82% 72%",
        }}
      />

      <div className="scene-noise-light absolute inset-0" />

      <div className="absolute inset-0 bg-[radial-gradient(ellipse_88%_78%_at_50%_38%,transparent_25%,rgba(244,243,239,0.82)_100%)]" />
    </div>
  );
}
