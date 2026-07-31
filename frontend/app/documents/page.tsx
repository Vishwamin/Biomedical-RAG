"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronRight, FileText, Loader2, Trash2 } from "lucide-react";
import clsx from "clsx";
import { api, ApiError } from "@/lib/api";
import type { DocumentMetadata } from "@/lib/types";
import DocumentUpload from "@/components/DocumentUpload";
import DocumentStatusBadge from "@/components/DocumentStatusBadge";
import DocumentChunkViewer from "@/components/DocumentChunkViewer";
import ErrorBanner from "@/components/ErrorBanner";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentMetadata[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api
      .listDocuments()
      .then(setDocuments)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load documents."));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleDelete(documentId: string) {
    setDeletingId(documentId);
    try {
      await api.deleteDocument(documentId);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-8 py-10">
      <header className="mb-6">
        <h1 className="font-display text-[26px] text-ink">Documents</h1>
        <p className="text-sm text-ink-soft mt-1">
          Papers ingested into the research index. Each is parsed, chunked, embedded, and added to both the
          dense and keyword indexes before it becomes searchable.
        </p>
      </header>

      <div className="mb-8">
        <DocumentUpload onUploaded={refresh} />
      </div>

      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} />
        </div>
      )}

      {documents === null && !error && (
        <div className="flex items-center gap-2 text-ink-soft text-sm py-8 justify-center">
          <Loader2 size={16} className="animate-spin" /> Loading documents…
        </div>
      )}

      {documents?.length === 0 && (
        <div className="text-center py-12 border border-dashed border-line-strong rounded-lg">
          <FileText size={22} className="mx-auto text-ink-soft/50" />
          <p className="text-sm text-ink-soft mt-2">No documents yet. Upload one to get started.</p>
        </div>
      )}

      {documents && documents.length > 0 && (
        <div className="border border-line rounded-lg divide-y divide-line overflow-hidden bg-paper-raised">
          {documents.map((doc) => {
            const expanded = expandedId === doc.document_id;
            return (
              <div key={doc.document_id}>
                <div className="flex items-center gap-3 px-4 py-3">
                  <button
                    onClick={() => setExpandedId(expanded ? null : doc.document_id)}
                    className="flex items-center gap-3 min-w-0 flex-1 text-left"
                  >
                    <ChevronRight
                      size={15}
                      className={clsx("shrink-0 text-ink-soft transition-transform", expanded && "rotate-90")}
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ink truncate">
                        {doc.document_title ?? doc.source_filename}
                      </p>
                      <p className="text-xs text-ink-soft flex items-center gap-1.5 mt-0.5">
                        <span className="font-data">{doc.source_filename}</span>
                        {doc.page_count != null && <span>· {doc.page_count}p</span>}
                        <span>· {doc.chunk_count} chunks</span>
                      </p>
                    </div>
                  </button>
                  <DocumentStatusBadge status={doc.status} />
                  <button
                    onClick={() => handleDelete(doc.document_id)}
                    disabled={deletingId === doc.document_id}
                    className="text-ink-soft/50 hover:text-contradict transition-colors p-1 disabled:opacity-30"
                    aria-label={`Delete ${doc.source_filename}`}
                  >
                    {deletingId === doc.document_id ? (
                      <Loader2 size={15} className="animate-spin" />
                    ) : (
                      <Trash2 size={15} />
                    )}
                  </button>
                </div>
                {expanded && (
                  <div className="border-t border-line bg-paper">
                    <DocumentChunkViewer documentId={doc.document_id} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
