"use client";

import { useEffect, useRef, useState } from "react";
import { Copy, MoreHorizontal, Pencil, Pin, PinOff, Trash2 } from "lucide-react";
import type { ChatSummary } from "@/lib/types";

interface ChatMenuProps {
  chat: ChatSummary;
  onRename: () => void;
  onDuplicate: () => void;
  onTogglePin: () => void;
  onDelete: () => void;
}

export default function ChatMenu({ chat, onRename, onDuplicate, onTogglePin, onDelete }: ChatMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(!open);
        }}
        className="p-1 rounded text-spine-text/50 hover:text-paper-raised hover:bg-spine-line transition-colors"
        aria-label="Chat options"
      >
        <MoreHorizontal size={14} />
      </button>

      {open && (
        <div className="absolute right-0 top-7 z-20 w-40 bg-paper-raised border border-line rounded-md shadow-lg py-1 text-ink">
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setOpen(false);
              onTogglePin();
            }}
            className="w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 hover:bg-line/40"
          >
            {chat.pinned ? <PinOff size={13} /> : <Pin size={13} />}
            {chat.pinned ? "Unpin" : "Pin"}
          </button>
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setOpen(false);
              onRename();
            }}
            className="w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 hover:bg-line/40"
          >
            <Pencil size={13} />
            Rename
          </button>
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setOpen(false);
              onDuplicate();
            }}
            className="w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 hover:bg-line/40"
          >
            <Copy size={13} />
            Duplicate
          </button>
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setOpen(false);
              onDelete();
            }}
            className="w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 text-contradict hover:bg-contradict-soft"
          >
            <Trash2 size={13} />
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
