"use client";

import { useRef, useState } from "react";
import { UploadCloud, Loader2 } from "lucide-react";
import clsx from "clsx";
import { api, ApiError } from "@/lib/api";

export default function DocumentUpload({ onUploaded }: { onUploaded: () => void }) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setUploading(true);
    setError(null);
    try {
      await api.uploadDocument(file);
      onUploaded();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Upload failed.");
      }
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) handleFile(file);
        }}
        onClick={() => inputRef.current?.click()}
        className={clsx(
          "border-2 border-dashed rounded-lg px-6 py-8 text-center cursor-pointer transition-colors",
          dragging ? "border-accent bg-accent-soft" : "border-line-strong hover:border-ink-soft bg-paper-raised"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,.md"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
            e.target.value = "";
          }}
        />
        {uploading ? (
          <Loader2 size={22} className="mx-auto animate-spin text-ink-soft" />
        ) : (
          <UploadCloud size={22} className="mx-auto text-ink-soft" />
        )}
        <p className="text-sm text-ink-soft mt-2">
          {uploading ? "Uploading and indexing…" : "Drop a PDF, TXT, or MD file, or click to browse"}
        </p>
      </div>
      {error && <p className="text-xs text-contradict mt-2">{error}</p>}
    </div>
  );
}
