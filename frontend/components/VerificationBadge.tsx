import { CircleCheck, CircleDashed, CircleAlert, CircleX } from "lucide-react";
import type { VerificationLabel } from "@/lib/types";

const CONFIG: Record<
  VerificationLabel,
  { text: string; icon: typeof CircleCheck; className: string }
> = {
  fully_supports: { text: "Supported", icon: CircleCheck, className: "text-verify bg-verify-soft" },
  partially_supports: { text: "Partially supported", icon: CircleAlert, className: "text-flag bg-flag-soft" },
  does_not_support: { text: "Not supported", icon: CircleX, className: "text-contradict bg-contradict-soft" },
  contradicts: { text: "Contradicted", icon: CircleX, className: "text-contradict bg-contradict-soft" },
};

export default function VerificationBadge({ label }: { label: VerificationLabel | null }) {
  if (!label) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-line/50 text-ink-soft/70 px-2 py-0.5 text-[11px]">
        <CircleDashed size={11} />
        No citation
      </span>
    );
  }

  const { text, icon: Icon, className } = CONFIG[label];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] ${className}`}>
      <Icon size={11} />
      {text}
    </span>
  );
}
