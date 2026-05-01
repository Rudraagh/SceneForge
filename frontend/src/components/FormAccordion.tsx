/**
 * Accessible collapsible sections for dense studio controls (mobile-friendly).
 */

import type { ReactNode } from "react";

type Props = {
  id: string;
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: ReactNode;
};

export function FormAccordion({ id, title, subtitle, defaultOpen, children }: Props) {
  return (
    <details
      id={id}
      open={defaultOpen}
      className="group rounded-2xl border border-ink/10 bg-white/60 shadow-sm backdrop-blur-sm transition-all duration-300 open:border-ink/18 open:bg-white/85 open:shadow-md"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3.5 transition-colors hover:bg-canvas-muted/50 [&::-webkit-details-marker]:hidden">
        <div>
          <p className="font-display text-sm font-semibold text-ink">{title}</p>
          {subtitle ? <p className="mt-0.5 text-xs text-ink-faint">{subtitle}</p> : null}
        </div>
        <span
          className="shrink-0 text-ink-faint transition-transform duration-300 ease-out group-open:rotate-180"
          aria-hidden
        >
          <Chevron />
        </span>
      </summary>
      <div className="border-t border-ink/10 px-4 pb-4 pt-3 motion-safe:group-open:animate-fadeIn">{children}</div>
    </details>
  );
}

function Chevron() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className="opacity-80">
      <path d="M5 7.5L10 12.5L15 7.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
