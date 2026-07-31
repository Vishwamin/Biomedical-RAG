"use client";

import { useState } from "react";
import clsx from "clsx";
import type { RetrievalDebugResponse } from "@/lib/types";

type Tab = "dense" | "sparse" | "fused" | "reranked";

const TABS: { key: Tab; label: string }[] = [
  { key: "dense", label: "Dense search" },
  { key: "sparse", label: "BM25" },
  { key: "fused", label: "RRF fusion" },
  { key: "reranked", label: "Reranked" },
];

export default function RetrievalInspector({ debug }: { debug: RetrievalDebugResponse }) {
  const [tab, setTab] = useState<Tab>("reranked");

  const latencies: [string, number][] = [
    ["Dense", debug.dense_latency_ms],
    ["Sparse", debug.sparse_latency_ms],
    ["RRF", debug.rrf_latency_ms],
    ...(debug.rerank_latency_ms != null ? ([["Rerank", debug.rerank_latency_ms]] as [string, number][]) : []),
  ];

  return (
    <div className="border border-line rounded-lg bg-paper-raised overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <div className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={clsx(
                "px-2.5 py-1 rounded text-xs font-medium transition-colors",
                tab === t.key ? "bg-data text-paper-raised" : "text-ink-soft hover:bg-line/50"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="hidden sm:flex items-center gap-3 font-data text-[10px] text-ink-soft/60">
          {latencies.map(([label, ms]) => (
            <span key={label}>
              {label} {ms.toFixed(0)}ms
            </span>
          ))}
        </div>
      </div>

      <div className="max-h-[420px] overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-paper-raised border-b border-line text-ink-soft">
            <tr>
              <th className="text-left font-medium px-4 py-2 w-12">Rank</th>
              <th className="text-left font-medium px-4 py-2">Chunk</th>
              <th className="text-left font-medium px-4 py-2 w-24">Score</th>
              <th className="text-left font-medium px-4 py-2 w-28">Source</th>
            </tr>
          </thead>
          <tbody>
            {tab === "dense" &&
              debug.dense_results.map((r) => (
                <tr key={r.chunk_id} className="border-b border-line/60">
                  <td className="px-4 py-2 font-data">{r.dense_rank}</td>
                  <td className="px-4 py-2 text-ink-soft truncate max-w-xs">{r.text.slice(0, 80)}…</td>
                  <td className="px-4 py-2 font-data">{r.dense_score.toFixed(3)}</td>
                  <td className="px-4 py-2 text-ink-soft truncate">{r.source_filename}</td>
                </tr>
              ))}
            {tab === "sparse" &&
              debug.sparse_results.map((r) => (
                <tr key={r.chunk_id} className="border-b border-line/60">
                  <td className="px-4 py-2 font-data">{r.sparse_rank}</td>
                  <td className="px-4 py-2 text-ink-soft truncate max-w-xs">{r.text.slice(0, 80)}…</td>
                  <td className="px-4 py-2 font-data">{r.bm25_score.toFixed(3)}</td>
                  <td className="px-4 py-2 text-ink-soft truncate">{r.source_filename}</td>
                </tr>
              ))}
            {tab === "fused" &&
              debug.fused_results.map((r) => (
                <tr key={r.chunk_id} className="border-b border-line/60">
                  <td className="px-4 py-2 font-data">{r.fused_rank}</td>
                  <td className="px-4 py-2 text-ink-soft truncate max-w-xs">{r.text.slice(0, 80)}…</td>
                  <td className="px-4 py-2 font-data">{r.rrf_score.toFixed(4)}</td>
                  <td className="px-4 py-2 text-ink-soft truncate">{r.source_filename}</td>
                </tr>
              ))}
            {tab === "reranked" &&
              (debug.reranked_results ?? []).map((r) => (
                <tr key={r.chunk_id} className="border-b border-line/60">
                  <td className="px-4 py-2 font-data">{r.final_rank}</td>
                  <td className="px-4 py-2 text-ink-soft truncate max-w-xs">{r.text.slice(0, 80)}…</td>
                  <td className="px-4 py-2 font-data">{r.reranker_score.toFixed(3)}</td>
                  <td className="px-4 py-2 text-ink-soft truncate">{r.source_filename}</td>
                </tr>
              ))}
          </tbody>
        </table>
        {tab === "reranked" && !debug.reranked_results?.length && (
          <p className="px-4 py-6 text-center text-ink-soft/60 text-xs">No reranked results.</p>
        )}
      </div>
    </div>
  );
}
