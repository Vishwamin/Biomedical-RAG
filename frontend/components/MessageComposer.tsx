"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";

interface MessageComposerProps {
  onSend: (content: string) => void;
  disabled: boolean;
  placeholder?: string;
}

/**
 * Fixed-bottom auto-expanding composer: Enter sends, Shift+Enter inserts
 * a newline, textarea grows with content up to a max height, disabled
 * while a response is in flight.
 */
export default function MessageComposer({ onSend, disabled, placeholder }: MessageComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  function handleSend() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  return (
    <div className="border-t border-line bg-paper px-6 py-4">
      <div className="max-w-3xl mx-auto">
        <div className="rule-field border border-line-strong rounded-lg bg-paper-raised p-3 flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={disabled}
            placeholder={placeholder ?? "Ask a follow-up…"}
            rows={1}
            className="flex-1 resize-none bg-transparent outline-none text-[15px] placeholder:text-ink-soft/50 leading-[24px] max-h-[200px] disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={disabled || !value.trim()}
            aria-label="Send message"
            className="shrink-0 w-8 h-8 flex items-center justify-center rounded-md bg-ink text-paper-raised disabled:opacity-30 hover:bg-accent transition-colors"
          >
            <ArrowUp size={16} />
          </button>
        </div>
        <p className="text-[11px] text-ink-soft/50 mt-1.5 text-center">
          Enter to send · Shift+Enter for a new line
        </p>
      </div>
    </div>
  );
}
