"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, X } from "lucide-react";
import type { ChatSummary } from "@/lib/types";

export default function ChatSearchModal({
  chats,
  onClose,
}: {
  chats: ChatSummary[];
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return chats;
    return chats.filter((c) => c.title.toLowerCase().includes(q));
  }, [chats, query]);

  return (
    <div
      className="fixed inset-0 z-50 bg-ink/40 flex items-start justify-center pt-24"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-paper-raised border border-line rounded-lg shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-4 py-3 border-b border-line">
          <Search size={15} className="text-ink-soft shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              if (e.key === "Enter" && filtered[0]) {
                router.push(`/chat/${filtered[0].id}`);
                onClose();
              }
            }}
            placeholder="Search chats…"
            className="flex-1 bg-transparent outline-none text-sm"
          />
          <button onClick={onClose} className="text-ink-soft/50 hover:text-ink shrink-0" aria-label="Close search">
            <X size={15} />
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto py-1">
          {filtered.length === 0 && (
            <p className="px-4 py-6 text-center text-xs text-ink-soft/60">No chats found.</p>
          )}
          {filtered.map((chat) => (
            <button
              key={chat.id}
              onClick={() => {
                router.push(`/chat/${chat.id}`);
                onClose();
              }}
              className="w-full text-left px-4 py-2 text-sm hover:bg-line/40 flex items-center gap-2"
            >
              {chat.pinned && <span className="text-[10px]">📌</span>}
              <span className="truncate">{chat.title}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
