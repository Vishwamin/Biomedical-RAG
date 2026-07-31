import { FileText } from "lucide-react";
import RankTrail from "./RankTrail";
import VerificationBadge from "./VerificationBadge";
import type { GenerationCitation, RerankedResult, VerificationLabel } from "@/lib/types";

interface EvidenceCardProps {
  citation: GenerationCitation;
  rerankedResult?: RerankedResult;
  verificationLabel?: VerificationLabel | null;
}

export default function EvidenceCard({ citation, rerankedResult, verificationLabel }: EvidenceCardProps) {
  return (
    <div className="border border-line rounded-lg bg-paper-raised p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 min-w-0">
          <span className="font-data text-xs text-accent bg-accent-soft rounded px-1.5 py-0.5 shrink-0 mt-0.5">
            [{citation.citation_number}]
          </span>
          <div className="min-w-0">
            <p className="text-sm font-medium text-ink truncate" title={citation.document_title ?? citation.source_filename}>
              {citation.document_title ?? citation.source_filename}
            </p>
            <p className="text-xs text-ink-soft flex items-center gap-1 mt-0.5">
              <FileText size={11} />
              {citation.source_filename}
              {citation.page_number != null && <span>· p.{citation.page_number}</span>}
              {citation.section_heading && <span>· {citation.section_heading}</span>}
            </p>
          </div>
        </div>
        {verificationLabel !== undefined && <VerificationBadge label={verificationLabel} />}
      </div>

      <p className="text-sm text-ink-soft leading-relaxed border-l-2 border-line pl-3">
        {citation.text_snippet}
        {citation.text_snippet.length >= 280 ? "…" : ""}
      </p>

      {rerankedResult && (
        <div className="pt-1 border-t border-line flex items-center justify-between">
          <RankTrail
            denseRank={rerankedResult.dense_rank}
            sparseRank={rerankedResult.sparse_rank}
            rrfRank={rerankedResult.rrf_rank}
            finalRank={rerankedResult.final_rank}
            compact
          />
          <span className="font-data text-[10px] text-ink-soft/60">
            reranker {rerankedResult.reranker_score.toFixed(2)}
          </span>
        </div>
      )}
    </div>
  );
}
