"use client";

import { useEffect, useState } from "react";
import { ChartNoAxesColumn, Loader2, Play } from "lucide-react";
import clsx from "clsx";
import { api, ApiError } from "@/lib/api";
import type { EvaluationResultRow, RetrievalMode } from "@/lib/types";
import ErrorBanner from "@/components/ErrorBanner";

const MODES: { key: RetrievalMode; label: string }[] = [
  { key: "dense_only", label: "Dense only" },
  { key: "sparse_only", label: "BM25 only" },
  { key: "hybrid_rrf", label: "Hybrid + RRF" },
  { key: "hybrid_rrf_rerank", label: "Hybrid + RRF + Reranking" },
];

const METRIC_ORDER = [
  "precision_at_k", "recall_at_k", "mrr", "citation_coverage", "citation_validity",
  "faithfulness", "relevance", "correctness", "correct_refusal_rate", "false_refusal_rate", "hallucination_rate",
];

const METRIC_LABELS: Record<string, string> = {
  precision_at_k: "Precision@K", recall_at_k: "Recall@K", mrr: "MRR",
  citation_coverage: "Citation coverage", citation_validity: "Citation validity",
  faithfulness: "Faithfulness", relevance: "Relevance", correctness: "Correctness",
  correct_refusal_rate: "Correct refusal rate", false_refusal_rate: "False refusal rate",
  hallucination_rate: "Hallucination rate",
};

export default function EvaluationPage() {
  const [results, setResults] = useState<EvaluationResultRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [ablationMode, setAblationMode] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  function refresh() {
    api
      .listEvaluationResults()
      .then((r) => setResults(r.results))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load results."));
  }

  useEffect(refresh, []);

  async function runEval() {
    setRunning(true);
    setError(null);
    try {
      const response = await api.runEvaluation(ablationMode ? MODES.map((m) => m.key) : undefined);
      setNote(response.note);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Evaluation run failed.");
    } finally {
      setRunning(false);
    }
  }

  const latestRunByMode = new Map<string, string>();
  const runTimestamps = new Map<string, string>();
  if (results) {
    for (const row of results) {
      runTimestamps.set(row.run_id, row.created_at);
      const existingRunId = latestRunByMode.get(row.retrieval_mode);
      if (!existingRunId || row.created_at > (runTimestamps.get(existingRunId) ?? "")) {
        latestRunByMode.set(row.retrieval_mode, row.run_id);
      }
    }
  }

  const valueFor = (mode: string, metric: string): number | null => {
    const runId = latestRunByMode.get(mode);
    if (!runId || !results) return null;
    const row = results.find((r) => r.run_id === runId && r.metric_name === metric);
    return row ? row.metric_value : null;
  };

  const hasAnyResults = (results?.length ?? 0) > 0;
  const modesWithResults = MODES.filter((m) => latestRunByMode.has(m.key));

  return (
    <div className="max-w-4xl mx-auto px-8 py-10">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-[26px] text-ink">Evaluation</h1>
          <p className="text-sm text-ink-soft mt-1 max-w-xl">
            Runs the golden Q&amp;A dataset through the pipeline and measures retrieval, citation, and
            answer-quality metrics. Nothing here is fabricated — until a run completes, there are no numbers
            to show.
          </p>
        </div>
      </header>

      <div className="border border-line rounded-lg bg-paper-raised p-4 mb-8">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <label className="flex items-center gap-2 text-sm text-ink-soft">
            <input
              type="checkbox"
              checked={ablationMode}
              onChange={(e) => setAblationMode(e.target.checked)}
              className="accent-accent"
            />
            Full ablation comparison (all 4 retrieval modes — costs 4x the LLM calls)
          </label>
          <button
            onClick={runEval}
            disabled={running}
            className="inline-flex items-center gap-2 bg-ink text-paper-raised px-4 py-2 rounded-md text-sm font-medium disabled:opacity-40 hover:bg-accent transition-colors"
          >
            {running ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
            {running ? "Running…" : "Run evaluation"}
          </button>
        </div>
        {note && <p className="text-xs text-flag bg-flag-soft rounded px-3 py-2 mt-3">{note}</p>}
      </div>

      {error && (
        <div className="mb-6">
          <ErrorBanner message={error} />
        </div>
      )}

      {results === null && !error && (
        <div className="flex items-center gap-2 text-ink-soft text-sm py-8 justify-center">
          <Loader2 size={16} className="animate-spin" /> Loading results…
        </div>
      )}

      {results !== null && !hasAnyResults && (
        <div className="text-center py-16 border border-dashed border-line-strong rounded-lg">
          <ChartNoAxesColumn size={22} className="mx-auto text-ink-soft/50" />
          <p className="text-sm text-ink-soft mt-2">No evaluation run yet.</p>
          <p className="text-xs text-ink-soft/60 mt-1">Run one above to see real metrics here.</p>
        </div>
      )}

      {hasAnyResults && (
        <div className="border border-line rounded-lg bg-paper-raised overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line">
              <tr>
                <th className="text-left font-medium px-4 py-2.5 text-ink-soft text-xs">Metric</th>
                {modesWithResults.map((m) => (
                  <th key={m.key} className="text-right font-medium px-4 py-2.5 text-ink-soft text-xs">
                    {m.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {METRIC_ORDER.map((metric, i) => (
                <tr key={metric} className={clsx(i % 2 === 1 && "bg-paper/60")}>
                  <td className="px-4 py-2 text-ink-soft">{METRIC_LABELS[metric] ?? metric}</td>
                  {modesWithResults.map((m) => {
                    const value = valueFor(m.key, metric);
                    return (
                      <td key={m.key} className="px-4 py-2 text-right font-data tabular-nums">
                        {value != null ? value.toFixed(3) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {modesWithResults.length === 1 && (
            <p className="text-xs text-ink-soft/60 px-4 py-3 border-t border-line">
              Only one retrieval mode has been run so far. Run the full ablation comparison above to see how
              hybrid retrieval and reranking compare against dense-only or BM25-only search.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
