interface RankTrailProps {
  denseRank: number | null;
  sparseRank: number | null;
  rrfRank: number | null;
  finalRank: number | null;
  compact?: boolean;
}

const STAGES = [
  { key: "denseRank" as const, label: "Dense" },
  { key: "sparseRank" as const, label: "Sparse" },
  { key: "rrfRank" as const, label: "Fused" },
  { key: "finalRank" as const, label: "Reranked" },
];

export default function RankTrail({ denseRank, sparseRank, rrfRank, finalRank, compact }: RankTrailProps) {
  const values = { denseRank, sparseRank, rrfRank, finalRank };

  return (
    <div className="flex items-center gap-0" role="img" aria-label="Retrieval rank trail">
      {STAGES.map((stage, i) => {
        const rank = values[stage.key];
        const present = rank !== null;
        return (
          <div key={stage.key} className="flex items-center">
            <div className="flex flex-col items-center gap-1">
              <div
                className={
                  "flex items-center justify-center rounded-full border font-data " +
                  (compact ? "w-6 h-6 text-[9px]" : "w-7 h-7 text-[10px]") +
                  " " +
                  (present
                    ? "bg-data-soft border-data text-data"
                    : "bg-transparent border-line-strong text-ink-soft/40")
                }
                title={present ? `${stage.label} rank ${rank}` : `Not retrieved by ${stage.label.toLowerCase()} search`}
              >
                {present ? rank : "—"}
              </div>
              {!compact && (
                <span className="text-[9px] uppercase tracking-wide text-ink-soft/60">{stage.label}</span>
              )}
            </div>
            {i < STAGES.length - 1 && (
              <div className={"h-px w-4 sm:w-6 " + (present ? "bg-line-strong" : "bg-line")} aria-hidden />
            )}
          </div>
        );
      })}
    </div>
  );
}
