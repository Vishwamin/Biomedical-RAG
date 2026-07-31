import clsx from "clsx";

const LABEL_STYLES: Record<string, string> = {
  High: "bg-verify-soft text-verify border-verify/30",
  Moderate: "bg-flag-soft text-flag border-flag/30",
  Low: "bg-contradict-soft text-contradict border-contradict/30",
};

export default function ConfidenceBadge({ score, label }: { score: number; label: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        LABEL_STYLES[label] || "bg-line/40 text-ink-soft border-line"
      )}
    >
      <span className="font-data tabular-nums">{score.toFixed(1)}</span>
      <span className="opacity-70">·</span>
      {label}
    </span>
  );
}
