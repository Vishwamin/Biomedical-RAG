import clsx from "clsx";
import type { DocumentStatus } from "@/lib/types";

const CONFIG: Record<DocumentStatus, { text: string; className: string }> = {
  pending: { text: "Pending", className: "bg-line/50 text-ink-soft" },
  processing: { text: "Processing", className: "bg-flag-soft text-flag" },
  indexed: { text: "Indexed", className: "bg-verify-soft text-verify" },
  failed: { text: "Failed", className: "bg-contradict-soft text-contradict" },
};

export default function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const config = CONFIG[status];
  return (
    <span className={clsx("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium", config.className)}>
      {config.text}
    </span>
  );
}
