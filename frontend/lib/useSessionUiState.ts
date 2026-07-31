"use client";

import { useCallback, useEffect, useRef } from "react";

/**
 * Persists small bits of ephemeral per-chat UI state (scroll position,
 * whether the retrieval inspector is expanded) to sessionStorage, keyed
 * by chat id. This is what makes "navigate to Documents, come back, the
 * conversation looks exactly like you left it" actually true for things
 * that aren't part of the persisted message data itself — Next.js
 * unmounts the chat page component on navigation, so without this any
 * scroll position or open/closed accordion state would reset.
 */

function storageKey(chatId: string, field: string) {
  return `biorag:chat-ui:${chatId}:${field}`;
}

export function useScrollRestoration(chatId: string | null) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!chatId || !containerRef.current) return;
    const saved = sessionStorage.getItem(storageKey(chatId, "scrollTop"));
    if (saved) {
      containerRef.current.scrollTop = parseInt(saved, 10);
    } else {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [chatId]);

  const handleScroll = useCallback(() => {
    if (!chatId || !containerRef.current) return;
    sessionStorage.setItem(storageKey(chatId, "scrollTop"), String(containerRef.current.scrollTop));
  }, [chatId]);

  return { containerRef, handleScroll };
}

export function useInspectorState(chatId: string | null, messageId: string) {
  const key = chatId ? storageKey(chatId, `inspector:${messageId}`) : null;

  const getInitial = useCallback((): boolean => {
    if (!key || typeof window === "undefined") return false;
    return sessionStorage.getItem(key) === "1";
  }, [key]);

  const persist = useCallback(
    (open: boolean) => {
      if (!key) return;
      sessionStorage.setItem(key, open ? "1" : "0");
    },
    [key]
  );

  return { getInitial, persist };
}
