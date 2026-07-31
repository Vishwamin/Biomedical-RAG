"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ChevronRight, CircleHelp, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { ChatDetail, MessageSchema } from "@/lib/types";
import { emitChatsChanged } from "@/lib/chatEvents";
import { useScrollRestoration } from "@/lib/useSessionUiState";
import UserMessage from "@/components/UserMessage";
import AssistantMessage from "@/components/AssistantMessage";
import MessageComposer from "@/components/MessageComposer";
import PipelineStages from "@/components/PipelineStages";
import ErrorBanner from "@/components/ErrorBanner";

const EXAMPLE_QUESTIONS = [
  "How do checkpoint inhibitors help the immune system fight tumor cells?",
  "What evidence exists for a link between IL-6 and treatment response?",
  "What methods were used to validate the primary biomarker in this study?",
];

export default function ChatPage() {
  const params = useParams<{ chatId: string }>();
  const chatId = params.chatId;
  const router = useRouter();

  const [chat, setChat] = useState<ChatDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { containerRef, handleScroll } = useScrollRestoration(chatId ?? null);

  useEffect(() => {
    setChat(null);
    setNotFound(false);
    api
      .getChat(chatId)
      .then(setChat)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        } else {
          setError(err instanceof ApiError ? err.message : "Could not load this chat.");
        }
      });
  }, [chatId]);

  useEffect(() => {
    if (chat) {
      // restore/scroll to bottom after messages render
      requestAnimationFrame(() => {
        if (containerRef.current) {
          const saved = sessionStorage.getItem(`biorag:chat-ui:${chatId}:scrollTop`);
          if (!saved) containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat?.messages.length]);

  async function handleSend(content: string) {
    if (!chat) return;
    setError(null);
    setSending(true);

    const optimisticUser: MessageSchema = {
      id: `optimistic_${Date.now()}`,
      chat_id: chatId,
      role: "user",
      content,
      confidence: null,
      confidence_label: null,
      confidence_breakdown: null,
      insufficient_evidence: false,
      citations: [],
      claims: [],
      sources: [],
      retrieval_debug: null,
      processing_latency_ms: null,
      created_at: new Date().toISOString(),
    };
    setChat({ ...chat, messages: [...chat.messages, optimisticUser] });

    try {
      const response = await api.sendChatMessage(chatId, content);
      setChat((prev) =>
        prev
          ? {
              ...prev,
              title: response.chat.title,
              updated_at: response.chat.updated_at,
              messages: [
                ...prev.messages.filter((m) => m.id !== optimisticUser.id),
                response.user_message,
                response.assistant_message,
              ],
            }
          : prev
      );
      emitChatsChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong sending that message.");
      // Roll back the optimistic user message so the composer content isn't silently lost from view.
      setChat((prev) => (prev ? { ...prev, messages: prev.messages.filter((m) => m.id !== optimisticUser.id) } : prev));
    } finally {
      setSending(false);
    }
  }

  if (notFound) {
    return (
      <div className="max-w-lg mx-auto px-8 py-16 text-center">
        <p className="text-sm text-ink-soft">This chat doesn&apos;t exist or was deleted.</p>
        <button onClick={() => router.push("/")} className="mt-3 text-sm text-accent hover:underline">
          Start a new chat
        </button>
      </div>
    );
  }

  if (!chat) {
    return (
      <div className="flex items-center justify-center h-full py-24">
        <Loader2 size={18} className="animate-spin text-ink-soft" />
      </div>
    );
  }

  const isEmpty = chat.messages.length === 0;

  return (
    <div className="flex flex-col h-screen">
      <div ref={containerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 py-10">
          {isEmpty && (
            <div className="mb-8">
              <h1 className="font-display text-[26px] text-ink mb-1">Research question</h1>
              <p className="text-sm text-ink-soft mb-6">
                Ask about the biomedical literature you&apos;ve ingested. Answers are grounded in retrieved
                evidence, with every claim traced back to its source.
              </p>
              <p className="text-xs text-ink-soft/70 mb-2 flex items-center gap-1.5">
                <CircleHelp size={12} /> Example questions
              </p>
              <div className="flex flex-col gap-1.5">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    className="text-left text-sm text-ink-soft hover:text-accent flex items-center gap-1.5 group"
                  >
                    <ChevronRight size={13} className="shrink-0 text-line-strong group-hover:text-accent" />
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-10">
            {chat.messages.map((message) =>
              message.role === "user" ? (
                <UserMessage key={message.id} content={message.content} />
              ) : (
                <AssistantMessage key={message.id} message={message} chatId={chatId} />
              )
            )}
          </div>

          {sending && (
            <div className="mt-8">
              <PipelineStages />
            </div>
          )}

          {error && (
            <div className="mt-6">
              <ErrorBanner message={error} />
            </div>
          )}
        </div>
      </div>

      <MessageComposer onSend={handleSend} disabled={sending} />
    </div>
  );
}
