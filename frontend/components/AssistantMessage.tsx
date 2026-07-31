"use client";

import { useRef, useState } from "react";
import { ChevronRight } from "lucide-react";
import clsx from "clsx";
import type { MessageSchema, VerificationLabel } from "@/lib/types";
import CitedAnswerText from "@/components/CitedAnswerText";
import ConfidenceBadge from "@/components/ConfidenceBadge";
import ConfidenceBreakdownPanel from "@/components/ConfidenceBreakdownPanel";
import EvidenceCard from "@/components/EvidenceCard";
import RetrievalInspector from "@/components/RetrievalInspector";
import { useInspectorState } from "@/lib/useSessionUiState";

/**
 * Renders one assistant message with every BioRAG evidence feature
 * intact: cited answer text, confidence badge + breakdown, evidence cards
 * with rank trails, and an optional retrieval inspector. This is the same
 * rendering that previously lived directly in the single-query page —
 * extracted here so both the chat page and (if ever needed) any other
 * surface can render an assistant response identically.
 */
export default function AssistantMessage({
  message,
  chatId,
}: {
  message: MessageSchema;
  chatId: string;
}) {
  const [showInspector, setShowInspector] = useState<boolean | null>(null);
  const evidenceRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const { getInitial, persist } = useInspectorState(chatId, message.id);

  const inspectorOpen = showInspector === null ? getInitial() : showInspector;

  function toggleInspector() {
    const next = !inspectorOpen;
    setShowInspector(next);
    persist(next);
  }

  function scrollToCitation(n: number) {
    const el = evidenceRefs.current[n];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("ring-2", "ring-accent");
      setTimeout(() => el.classList.remove("ring-2", "ring-accent"), 1200);
    }
  }

  const verificationByCitation: Record<number, VerificationLabel | null> = {};
  for (const claim of message.claims) {
    for (const n of claim.citation_numbers) {
      if (verificationByCitation[n] === undefined) {
        verificationByCitation[n] = claim.verification_label;
      }
    }
  }

  const rerankedByChunkId = new Map(
    (message.retrieval_debug?.reranked_results ?? []).map((r) => [r.chunk_id, r])
  );

  return (
    <div className="space-y-6">
      {message.insufficient_evidence && (
        <div className="border border-flag/30 bg-flag-soft text-flag rounded-lg px-4 py-3 text-sm">
          The available documents don&apos;t contain sufficient evidence to answer this reliably.
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-3">
          <span className="font-display text-[15px] text-ink-soft">BioRAG</span>
          {message.confidence != null && message.confidence_label && (
            <ConfidenceBadge score={message.confidence} label={message.confidence_label} />
          )}
        </div>

        <CitedAnswerText
          text={message.content}
          validCitationNumbers={new Set(message.citations.map((c) => c.citation_number))}
          onCitationClick={scrollToCitation}
        />

        {message.confidence_breakdown && (
          <div className="mt-4">
            <ConfidenceBreakdownPanel breakdown={message.confidence_breakdown} />
          </div>
        )}
      </div>

      {message.citations.length > 0 && (
        <div>
          <h3 className="font-display text-base mb-3">Evidence</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {message.citations.map((citation) => (
              <div
                key={citation.citation_number}
                ref={(el) => {
                  evidenceRefs.current[citation.citation_number] = el;
                }}
                className="rounded-lg transition-shadow"
              >
                <EvidenceCard
                  citation={citation}
                  rerankedResult={rerankedByChunkId.get(citation.chunk_id)}
                  verificationLabel={verificationByCitation[citation.citation_number]}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {message.retrieval_debug && (
        <div>
          <button
            onClick={toggleInspector}
            className={clsx(
              "text-sm font-medium flex items-center gap-1.5 mb-3",
              inspectorOpen ? "text-ink" : "text-ink-soft hover:text-ink"
            )}
          >
            <ChevronRight size={14} className={clsx("transition-transform", inspectorOpen && "rotate-90")} />
            Retrieval inspector
            <span className="text-ink-soft/50 font-normal">— see how each result ranked at every stage</span>
          </button>
          {inspectorOpen && <RetrievalInspector debug={message.retrieval_debug} />}
        </div>
      )}

      {message.processing_latency_ms && (
        <p className="font-data text-[11px] text-ink-soft/50 pt-2 border-t border-line">
          {Object.entries(message.processing_latency_ms)
            .map(([k, v]) => `${k.replace("_ms", "")} ${v.toFixed(0)}ms`)
            .join("  ·  ")}
        </p>
      )}
    </div>
  );
}
