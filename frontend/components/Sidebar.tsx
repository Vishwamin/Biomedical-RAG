"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { FlaskConical, FileStack, LineChart, Pin, Search, SquarePen } from "lucide-react";
import clsx from "clsx";
import { api, ApiError } from "@/lib/api";
import type { ChatSummary } from "@/lib/types";
import { emitChatsChanged, onChatsChanged } from "@/lib/chatEvents";
import ChatMenu from "@/components/ChatMenu";
import ChatSearchModal from "@/components/ChatSearchModal";

const NAV_ITEMS = [
  { href: "/documents", label: "Documents", icon: FileStack },
  { href: "/evaluation", label: "Evaluation", icon: LineChart },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const params = useParams<{ chatId?: string }>();
  const activeChatId = params?.chatId;

  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const refresh = useCallback(() => {
    api.listChats().then(setChats).catch(() => {
      // Sidebar chat list failing to load shouldn't break the rest of the app;
      // it will retry on the next chats-changed event or navigation.
    });
  }, []);

  useEffect(() => {
    refresh();
    return onChatsChanged(refresh);
  }, [refresh]);

  useEffect(() => {
    function handleKeydown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        handleNewChat();
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "o") {
        e.preventDefault();
        setSearchOpen(true);
      }
    }
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleNewChat() {
    try {
      const chat = await api.createChat();
      emitChatsChanged();
      router.push(`/chat/${chat.id}`);
    } catch (err) {
      console.error("Failed to create chat", err);
    }
  }

  async function handleTogglePin(chat: ChatSummary) {
    try {
      await api.setChatPinned(chat.id, !chat.pinned);
      refresh();
    } catch (err) {
      console.error("Failed to toggle pin", err);
    }
  }

  function startRename(chat: ChatSummary) {
    setRenamingId(chat.id);
    setRenameValue(chat.title);
  }

  async function commitRename(chatId: string) {
    const title = renameValue.trim();
    setRenamingId(null);
    if (!title) return;
    try {
      await api.renameChat(chatId, title);
      refresh();
    } catch (err) {
      console.error("Failed to rename chat", err);
    }
  }

  async function handleDuplicate(chat: ChatSummary) {
    try {
      const copy = await api.duplicateChat(chat.id);
      refresh();
      router.push(`/chat/${copy.id}`);
    } catch (err) {
      console.error("Failed to duplicate chat", err);
    }
  }

  async function handleDelete(chat: ChatSummary) {
    if (!window.confirm(`Delete "${chat.title}"? This cannot be undone.`)) return;
    try {
      await api.deleteChat(chat.id);
      refresh();
      if (activeChatId === chat.id) router.push("/");
    } catch (err) {
      if (err instanceof ApiError) console.error(err.message);
    }
  }

  const pinned = chats.filter((c) => c.pinned);
  const recent = chats.filter((c) => !c.pinned);

  function ChatRow(chat: ChatSummary) {
    const active = activeChatId === chat.id;
    const isRenaming = renamingId === chat.id;
    return (
      <div
        key={chat.id}
        className={clsx(
          "group flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[13px]",
          active ? "bg-spine-line text-paper-raised" : "text-spine-text/80 hover:bg-spine-line/60 hover:text-paper-raised"
        )}
      >
        {isRenaming ? (
          <input
            autoFocus
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onBlur={() => commitRename(chat.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitRename(chat.id);
              if (e.key === "Escape") setRenamingId(null);
            }}
            className="flex-1 min-w-0 bg-spine-line/80 rounded px-1.5 py-0.5 text-[13px] outline-none"
          />
        ) : (
          <Link href={`/chat/${chat.id}`} className="flex-1 min-w-0 truncate">
            {chat.title}
          </Link>
        )}
        {!isRenaming && (
          <ChatMenu
            chat={chat}
            onRename={() => startRename(chat)}
            onDuplicate={() => handleDuplicate(chat)}
            onTogglePin={() => handleTogglePin(chat)}
            onDelete={() => handleDelete(chat)}
          />
        )}
      </div>
    );
  }

  return (
    <aside className="w-[220px] shrink-0 bg-spine text-spine-text flex flex-col h-screen sticky top-0">
      <div className="px-5 pt-6 pb-4 border-b border-spine-line">
        <Link href="/" className="flex items-center gap-2 text-paper-raised">
          <FlaskConical size={20} strokeWidth={1.75} />
          <span className="font-display text-lg tracking-tight">BioRAG</span>
        </Link>
        <p className="mt-1.5 text-[11px] leading-snug text-spine-text/70">
          Biomedical research intelligence
        </p>
      </div>

      <div className="px-3 pt-3 space-y-1">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-[13.5px] text-paper-raised bg-spine-line/70 hover:bg-spine-line transition-colors"
        >
          <SquarePen size={16} strokeWidth={1.75} />
          New Chat
        </button>
        <button
          onClick={() => setSearchOpen(true)}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-[13.5px] text-spine-text/80 hover:bg-spine-line/60 hover:text-paper-raised transition-colors"
        >
          <Search size={16} strokeWidth={1.75} />
          Search chats
          <span className="ml-auto text-[10px] text-spine-text/40 font-data">⌃⇧O</span>
        </button>
      </div>

      <nav className="flex-1 min-h-0 overflow-y-auto px-3 py-3 space-y-4">
        {pinned.length > 0 && (
          <div>
            <p className="px-2.5 text-[10px] uppercase tracking-wide text-spine-text/40 flex items-center gap-1 mb-1">
              <Pin size={9} /> Pinned
            </p>
            <div className="space-y-0.5">{pinned.map(ChatRow)}</div>
          </div>
        )}
        <div>
          {recent.length > 0 && (
            <p className="px-2.5 text-[10px] uppercase tracking-wide text-spine-text/40 mb-1">Recent</p>
          )}
          <div className="space-y-0.5">{recent.map(ChatRow)}</div>
          {chats.length === 0 && (
            <p className="px-2.5 text-[12px] text-spine-text/40 py-2">No chats yet — start one above.</p>
          )}
        </div>
      </nav>

      <div className="px-3 py-3 border-t border-spine-line space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-2.5 px-3 py-2 rounded-md text-[13.5px] transition-colors",
                active
                  ? "bg-spine-line text-paper-raised"
                  : "text-spine-text/80 hover:bg-spine-line/60 hover:text-paper-raised"
              )}
            >
              <Icon size={16} strokeWidth={1.75} />
              {item.label}
            </Link>
          );
        })}
      </div>

      <div className="px-5 py-4 border-t border-spine-line text-[11px] text-spine-text/50 leading-relaxed">
        Research &amp; education use only.
        <br />
        Not for clinical decisions.
      </div>

      {searchOpen && <ChatSearchModal chats={chats} onClose={() => setSearchOpen(false)} />}
    </aside>
  );
}
