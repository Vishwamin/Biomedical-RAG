"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import clsx from "clsx";

const STAGES = [
  "Searching semantic index",
  "Running keyword retrieval",
  "Fusing results",
  "Reranking evidence",
  "Generating answer",
  "Verifying citations",
  "Calculating confidence",
];

const STAGE_WEIGHTS = [1, 1, 0.4, 1.2, 3, 2.2, 0.6];

export default function PipelineStages() {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let i = 0;
    const totalWeight = STAGE_WEIGHTS.reduce((a, b) => a + b, 0);
    const baseDuration = 9000;

    function advance() {
      if (cancelled || i >= STAGES.length - 1) return;
      const delay = (STAGE_WEIGHTS[i] / totalWeight) * baseDuration;
      setTimeout(() => {
        if (cancelled) return;
        i += 1;
        setActiveIndex(i);
        advance();
      }, delay);
    }
    advance();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="border border-line rounded-lg bg-paper-raised px-5 py-4">
      <ol className="space-y-2">
        {STAGES.map((stage, i) => {
          const done = i < activeIndex;
          const active = i === activeIndex;
          return (
            <li key={stage} className="flex items-center gap-2.5 text-sm">
              <span
                className={clsx(
                  "flex items-center justify-center w-4 h-4 rounded-full shrink-0 border",
                  done && "bg-verify border-verify",
                  active && "border-data",
                  !done && !active && "border-line-strong"
                )}
              >
                {done && <Check size={10} strokeWidth={3} className="text-paper-raised" />}
                {active && <span className="w-1.5 h-1.5 rounded-full bg-data animate-pulse" />}
              </span>
              <span
                className={clsx(
                  done && "text-ink-soft/60 line-through decoration-line-strong",
                  active && "text-ink font-medium",
                  !done && !active && "text-ink-soft/40"
                )}
              >
                {stage}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
