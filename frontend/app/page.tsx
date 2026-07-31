"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { emitChatsChanged } from "@/lib/chatEvents";

/**
 * Root route: creates a fresh chat and redirects into it, mirroring the
 * "New Chat" sidebar button exactly (see Sidebar.tsx's handleNewChat) —
 * landing on "/" behaves the same as clicking New Chat.
 */
export default function RootPage() {
  const router = useRouter();
  const firedRef = useRef(false);

  useEffect(() => {
    if (firedRef.current) return;
    firedRef.current = true;

    api
      .createChat()
      .then((chat) => {
        emitChatsChanged();
        router.replace(`/chat/${chat.id}`);
      })
      .catch((err) => {
        console.error("Failed to create a new chat", err);
      });
  }, [router]);

  return (
    <div className="flex items-center justify-center h-screen">
      <Loader2 size={18} className="animate-spin text-ink-soft" />
    </div>
  );
}
