"use client";

/**
 * Tiny event bus so the sidebar's chat list refreshes when something
 * elsewhere (the chat page auto-titling on first message, a rename, a
 * pin toggle, a delete) changes chat data — without pulling in a full
 * state-management library for what is, in this app, a handful of
 * call sites.
 */

const EVENT_NAME = "biorag:chats-changed";

export function emitChatsChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(EVENT_NAME));
  }
}

export function onChatsChanged(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(EVENT_NAME, callback);
  return () => window.removeEventListener(EVENT_NAME, callback);
}
