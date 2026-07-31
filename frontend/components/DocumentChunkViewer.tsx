"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { ChunkMetadata } from "@/lib/types";

export default function DocumentChunkViewer({ documentId }: { documentId: string }) {
  const [chunks, setChunks] = useState<ChunkMetadata[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getDocumentChunks(documentId)
      .then((data) => {
        if (!cancelled) setChunks(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load chunks.");
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  if (error) return <p className="text-xs text-contradict px-4 py-3">{error}</p>;
  if (!chunks) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 text-ink-soft text-xs">
        <Loader2 size={13} className="animate-spin" /> Loading chunks…
      </div>
    );
  }

  return (
    <div className="divide-y divide-line max-h-96 overflow-y-auto">
      {chunks.map((chunk) => (
        <div key={chunk.chunk_id} className="px-4 py-2.5">
          <div className="flex items-center gap-2 text-[11px] text-ink-soft mb-1">
            <span className="font-data">#{chunk.chunk_index}</span>
            {chunk.page_number != null && <span>p.{chunk.page_number}</span>}
            {chunk.section_heading && (
              <span className="bg-line/50 rounded px-1.5 py-0.5">{chunk.section_heading}</span>
            )}
            <span className="ml-auto font-data text-ink-soft/60">{chunk.chunking_strategy}</span>
          </div>
          <p className="text-xs text-ink-soft/80 line-clamp-2">{chunk.text}</p>
        </div>
      ))}
    </div>
  );
}
