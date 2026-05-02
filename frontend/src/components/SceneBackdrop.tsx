/**
 * Pastel dream backdrop: periwinkle base, soft yellow-green light (left), lavender-pink
 * glow (right), paper grain, and slow floating orbs — palette stays in those shades only.
 * Scroll nudges hue/lightness slightly so long pages still feel alive without harsh overlays.
 */

import { useEffect, useState } from "react";

function clamp01(n: number): number {
  return Math.min(1, Math.max(0, n));
}

function readScrollProgress(): number {
  if (typeof document === "undefined") return 0;
  const el = document.documentElement;
  const max = Math.max(1, el.scrollHeight - window.innerHeight);
  return clamp01(window.scrollY / max);
}

function resolvePublicUrl(path: string): string {
  const base = import.meta.env.BASE_URL || "/";
  const normalized = base.endsWith("/") ? base : `${base}/`;
  return `${normalized}${path.replace(/^\//, "")}`;
}

const VIDEO_CANDIDATES = ["hero-loop.mp4", "backdrop.mp4"] as const;

/** Soft floating props — only mint, periwinkle, and lavender-pink tones */
const FLOAT_ORBS: {
  top: string;
  left: string;
  size: string;
  blur: string;
  bg: string;
  delay: string;
  anim: "dreamFloat" | "dreamDrift";
}[] = [
  { top: "10%", left: "6%", size: "min(16vmin,120px)", blur: "40px", bg: "rgba(236, 252, 226, 0.5)", delay: "0s", anim: "dreamFloat" },
  { top: "22%", left: "18%", size: "min(10vmin,88px)", blur: "28px", bg: "rgba(220, 232, 255, 0.55)", delay: "-4s", anim: "dreamDrift" },
  { top: "58%", left: "4%", size: "min(12vmin,96px)", blur: "32px", bg: "rgba(232, 240, 255, 0.45)", delay: "-9s", anim: "dreamFloat" },
  { top: "72%", left: "22%", size: "min(9vmin,72px)", blur: "24px", bg: "rgba(245, 226, 240, 0.5)", delay: "-2s", anim: "dreamDrift" },
  { top: "14%", left: "72%", size: "min(14vmin,108px)", blur: "36px", bg: "rgba(238, 218, 245, 0.48)", delay: "-6s", anim: "dreamFloat" },
  { top: "38%", left: "84%", size: "min(11vmin,84px)", blur: "30px", bg: "rgba(225, 235, 255, 0.5)", delay: "-11s", anim: "dreamDrift" },
  { top: "68%", left: "78%", size: "min(18vmin,130px)", blur: "44px", bg: "rgba(242, 228, 246, 0.42)", delay: "-3s", anim: "dreamFloat" },
  { top: "48%", left: "48%", size: "min(8vmin,64px)", blur: "22px", bg: "rgba(248, 252, 235, 0.4)", delay: "-7s", anim: "dreamDrift" },
  { top: "30%", left: "42%", size: "min(6vmin,52px)", blur: "18px", bg: "rgba(216, 228, 255, 0.45)", delay: "-14s", anim: "dreamFloat" },
];

export function SceneBackdrop() {
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [scrollP, setScrollP] = useState(0);

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      raf = 0;
      setScrollP(readScrollProgress());
    };
    const onScroll = () => {
      if (raf) return;
      raf = window.requestAnimationFrame(tick);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    tick();
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) window.cancelAnimationFrame(raf);
    };
  }, []);

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
  const p = scrollP;

  /* Periwinkle field + scroll-nudged pastels only */
  const mintL = 92 - p * 2.5;
  const periS = 48 + p * 6;
  const periL = 88 - p * 4;
  const lavL = 90 - p * 3;

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden>
      {/* Base: cornflower / periwinkle with mint–lavender corners */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            linear-gradient(
              118deg,
              hsl(78, 55%, ${mintL}%) 0%,
              hsl(224, ${periS}%, ${periL}%) 38%,
              hsl(308, 38%, ${lavL}%) 100%
            )
          `,
        }}
      />

      {/* Soft yellow-green “beam” from the left (reference glow) */}
      <div
        className="absolute inset-0"
        style={{
          background: `radial-gradient(ellipse 95% 120% at 0% 42%, rgba(244, 252, 228, 0.72) 0%, rgba(236, 248, 220, 0.35) 28%, transparent 58%)`,
        }}
      />

      {/* Large lavender–pink disc on the right */}
      <div
        className="absolute -right-[12%] top-[0%] h-[min(92vmin,720px)] w-[min(92vmin,720px)] will-change-transform"
        style={{ transform: `translate3d(${-p * 1.5}vw, ${p * 2}vh, 0)` }}
      >
        <div
          className="h-full w-full rounded-full motion-safe:animate-blobDriftSlow"
          style={{
            background: "radial-gradient(circle, rgba(240, 214, 232, 0.62) 0%, rgba(235, 208, 228, 0.28) 55%, transparent 72%)",
            filter: "blur(4px)",
          }}
        />
      </div>

      {/* Mid periwinkle veil for even wash */}
      <div
        className="absolute inset-0"
        style={{
          background: `linear-gradient(180deg, transparent 0%, rgba(210, 224, 252, ${0.25 + p * 0.12}) 50%, rgba(228, 218, 246, ${0.15 + p * 0.1}) 100%)`,
        }}
      />

      {/* Floating pastel orbs */}
      {FLOAT_ORBS.map((orb, i) => (
        <div
          key={i}
          className={`absolute rounded-full motion-reduce:animate-none ${orb.anim === "dreamFloat" ? "motion-safe:animate-dreamFloat" : "motion-safe:animate-dreamDrift"}`}
          style={{
            top: orb.top,
            left: orb.left,
            width: orb.size,
            height: orb.size,
            backgroundColor: orb.bg,
            filter: `blur(${orb.blur})`,
            animationDelay: orb.delay,
            mixBlendMode: "soft-light",
            opacity: 0.88,
          }}
        />
      ))}

      {/* Extra ring “objects” */}
      <div
        className="motion-safe:animate-dreamDrift absolute left-[12%] top-[52%] motion-reduce:animate-none motion-reduce:opacity-40"
        style={{ animationDelay: "-5s" }}
      >
        <div
          className="h-[min(28vmin,220px)] w-[min(28vmin,220px)] rounded-full border-2 border-[rgba(200,218,255,0.35)]"
          style={{ filter: "blur(0.5px)" }}
        />
      </div>
      <div
        className="motion-safe:animate-dreamFloat absolute right-[18%] top-[58%] motion-reduce:animate-none motion-reduce:opacity-35"
        style={{ animationDelay: "-8s" }}
      >
        <div className="h-[min(20vmin,160px)] w-[min(20vmin,160px)] rounded-full border border-[rgba(236,214,232,0.45)]" />
      </div>

      {/* Very soft light wash (same family) */}
      <div
        className="absolute -left-[15%] top-[-25%] h-[140%] w-[140%] motion-safe:animate-conicSpin motion-reduce:animate-none"
        style={{
          opacity: 0.045 + p * 0.04,
          background:
            "conic-gradient(from 40deg, transparent 0deg, rgba(255,252,230,0.5) 70deg, transparent 130deg, rgba(200,218,255,0.45) 220deg, transparent 300deg)",
        }}
      />

      <object
        type="image/svg+xml"
        data={orbitSrc}
        className="absolute right-[-6%] top-[10%] h-[min(58vmin,420px)] w-[min(58vmin,420px)] border-0 opacity-[0.06] outline-none motion-reduce:opacity-[0.04]"
        aria-hidden
      />

      <div className="motion-safe:animate-ringPulse absolute -right-[4%] top-[20%]" style={{ animationDelay: "-3s" }}>
        <div className="h-[min(55vw,380px)] w-[min(55vw,380px)] rounded-full border border-[rgba(180,198,240,0.2)]" />
      </div>

      {videoUrl ? (
        <div className="absolute left-1/2 top-1/2 flex h-[130%] w-[130%] -translate-x-1/2 -translate-y-1/2 items-center justify-center">
          <div className="h-full w-full origin-center motion-safe:animate-videoBloom motion-reduce:animate-none">
            <video
              className="h-full w-full object-cover opacity-[0.08] mix-blend-soft-light grayscale contrast-90"
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

      <div className="scene-depth-grid absolute inset-0 opacity-[0.35]" />
      <div className="scene-diagonal-lines absolute inset-0 opacity-40" />

      <div
        className="absolute inset-0 opacity-[0.22] motion-safe:animate-topoDrift motion-reduce:animate-none"
        style={{
          backgroundImage: `url('${topoSrc}')`,
          backgroundSize: "min(820px, 110vw) auto",
          backgroundPosition: "40% 22%",
        }}
      />

      <div className="scene-noise-light absolute inset-0" />

      <div
        className="absolute inset-0"
        style={{
          background: `radial-gradient(ellipse 90% 80% at 50% 35%, transparent 30%, rgba(255,255,255,${0.35 - p * 0.12}) 100%)`,
        }}
      />
    </div>
  );
}
