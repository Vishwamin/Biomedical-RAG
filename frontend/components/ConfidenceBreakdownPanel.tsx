"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import clsx from "clsx";
import type { ConfidenceBreakdown } from "@/lib/types";

const COMPONENTS: { key: keyof ConfidenceBreakdown; label: string; weight: string }[] = [
  { key: "retrieval_confidence", label: "Retrieval relevance", weight: "30%" },
  { key: "citation_validity", label: "Citation validity", weight: "30%" },
  { key: "citation_coverage", label: "Citation coverage", weight: "20%" },
  { key: "evidence_agreement", label: "Evidence agreement", weight: "10%" },
  { key: "answer_completeness", label: "Answer completeness", weight: "10%" },
];

export default function ConfidenceBreakdownPanel({ breakdown }: { breakdown: ConfidenceBreakdown }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-line rounded-lg bg-paper-raised">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left"
      >
        <span className="text-xs text-ink-soft">
          An engineering heuristic combining five measured signals — not a calibrated probability of factual accuracy
        </span>
        <ChevronDown
          size={15}
          className={clsx("shrink-0 ml-2 text-ink-soft transition-transform", open && "rotate-180")}
        />
      </button>

      {open && (
        <div className="px-4 pb-4 pt-1 space-y-2.5 border-t border-line">
          {COMPONENTS.map((c) => {
            const value = breakdown[c.key] as number;
            const pct = Math.round(value * 100);
            return (
              <div key={c.key}>
                <div className="flex items-baseline justify-between text-xs mb-1">
                  <span className="text-ink-soft">
                    {c.label} <span className="text-ink-soft/50">({c.weight} weight)</span>
                  </span>
                  <span className="font-data tabular-nums text-ink">{pct}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-line overflow-hidden">
                  <div className="h-full bg-data rounded-full" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
          <p className="text-[11px] text-ink-soft/70 pt-1 leading-relaxed">{breakdown.explanation}</p>
        </div>
      )}
    </div>
  );
}
