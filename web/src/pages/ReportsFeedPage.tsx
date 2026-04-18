import React, { useEffect, useRef, useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Activity, Wifi, WifiOff, RefreshCw } from "lucide-react";
import { api } from "../api/client";
import { useAuthStore } from "../store/authStore";

interface ChatRoom {
  id: number;
  name: string | null;
  type: string;
  member_count: number;
  last_message: string | null;
}

interface FeedMessage {
  id: number;
  room_id: number;
  sender_id: number;
  sender_name: string | null;
  content: string;
  created_at: string;
  is_deleted: boolean;
}

type MsgKind = "new" | "edited" | "deleted" | "other";

function getMsgKind(content: string): MsgKind {
  const first = content.trimStart().slice(0, 6);
  if (first.includes("✅")) return "new";
  if (first.includes("✏️") || content.startsWith("✏")) return "edited";
  if (first.includes("🗑️") || content.startsWith("🗑")) return "deleted";
  return "other";
}

const KIND_STYLES: Record<MsgKind, { badge: string; border: string; bg: string; icon: string }> = {
  new:     { badge: "bg-green-100 text-green-800", border: "border-green-200", bg: "bg-green-50",   icon: "✅" },
  edited:  { badge: "bg-amber-100 text-amber-800",  border: "border-amber-200",  bg: "bg-amber-50",   icon: "✏️" },
  deleted: { badge: "bg-red-100   text-red-800",    border: "border-red-200",    bg: "bg-red-50",     icon: "🗑️" },
  other:   { badge: "bg-gray-100  text-gray-700",   border: "border-gray-200",   bg: "bg-white",      icon: "💬" },
};

const KIND_LABEL: Record<MsgKind, string> = {
  new:     "Новая запись",
  edited:  "Изменено",
  deleted: "Удалено",
  other:   "Сообщение",
};

interface ParsedRow { key: string; val: string | null; isDiff: boolean; isId: boolean }

function parseMsgLines(content: string): { header: string; rows: ParsedRow[] } {
  const lines = content.split("\n").map((l) => l.trim()).filter(Boolean);
  if (lines.length === 0) return { header: "", rows: [] };
  const header = lines[0];
  const rest = lines.slice(1);

  const rows: ParsedRow[] = [];
  let inDiff = false;
  for (const line of rest) {
    if (!line) continue;
    if (line === "Изменения:") { inDiff = true; continue; }
    const isId = line.startsWith("ID:");
    const colonIdx = line.indexOf(": ");
    const isEmoji = /^[📅📍🚜⏱👷🔧]/.test(line);
    if (colonIdx > 0 && !isEmoji) {
      rows.push({ key: line.slice(0, colonIdx), val: line.slice(colonIdx + 2), isDiff: inDiff, isId });
    } else {
      rows.push({ key: line, val: null, isDiff: inDiff, isId });
    }
  }
  return { header, rows };
}

function isSameDay(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
}

function formatDate(d: Date) {
  return d.toLocaleDateString("ru", { day: "numeric", month: "long", year: "numeric" });
}

// ── MessageCard ───────────────────────────────────────────────────────────────
function isEmojiLine(key: string) {
  return /^[📅📍🚜⏱👷🔧]/.test(key);
}

function formatActionDateTime(iso: string) {
  const d = new Date(iso);
  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${day}.${month} ${hh}:${mm}`;
}

function MessageCard({ msg }: { msg: FeedMessage }) {
  const kind = getMsgKind(msg.content);
  const s = KIND_STYLES[kind];
  const { header, rows } = parseMsgLines(msg.content);
  const actionDateTime = formatActionDateTime(msg.created_at);

  const mainRows = rows.filter((r) => !r.isDiff);
  // First non-emoji solo line is the sender name
  const nameIdx = mainRows.findIndex((r) => r.val === null && !r.isId && !isEmojiLine(r.key));

  return (
    <div className={`rounded-xl border ${s.border} ${s.bg} overflow-hidden shadow-sm`}>
      {/* Header badge — type + action date/time (always visible) */}
      <div className={`px-4 py-1.5 ${s.badge} flex items-center justify-between`}>
        <span className="font-semibold text-sm">{KIND_LABEL[kind]}</span>
        <span className="text-xs font-normal opacity-75 ml-2 whitespace-nowrap">{actionDateTime}</span>
      </div>

      {/* Body */}
      <div className="px-4 py-2.5 space-y-1">
        {mainRows.map((row, i) => {
          // Name row — highlight without duplicating the date
          if (i === nameIdx) {
            return (
              <div key={i} className="mb-0.5">
                <span className="text-sm font-semibold text-gray-800">{row.key}</span>
              </div>
            );
          }
          // Solo line: emoji rows
          if (row.val === null) {
            return (
              <div key={i} className={row.isId
                ? "text-xs text-gray-400 pt-1.5 mt-0.5 border-t border-gray-100"
                : "text-sm text-gray-700"
              }>
                {row.key}
              </div>
            );
          }
          // Skip empty values (—) to save space
          if (!row.val || row.val === "—") return null;
          // Inline "Key: Value"
          return (
            <div key={i} className={row.isId ? "pt-1.5 mt-0.5 border-t border-gray-100" : ""}>
              <span className={`text-xs ${row.isId ? "text-gray-400" : "text-gray-500"}`}>{row.key}: </span>
              <span className={`${row.isId ? "text-xs text-gray-400" : "text-sm font-semibold text-gray-800"}`}>{row.val}</span>
            </div>
          );
        })}
        {rows.length === 0 && (
          <p className="text-sm text-gray-600">{header}</p>
        )}

        {/* Diff section — shows old → new */}
        {rows.some((r) => r.isDiff) && (
          <div className="mt-3 pt-2.5 border-t border-gray-200 space-y-1.5">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Что изменилось</p>
            {rows.filter((r) => r.isDiff).map((row, i) => {
              const fullVal = row.val ?? row.key;
              const arrowIdx = fullVal.indexOf(" → ");
              const hasArrow = arrowIdx > -1;
              const oldPart = hasArrow ? fullVal.slice(0, arrowIdx) : null;
              const newPart = hasArrow ? fullVal.slice(arrowIdx + 3) : fullVal;
              const label = row.val !== null ? row.key : null;
              return (
                <div key={i} className="flex flex-wrap items-center gap-1 text-xs">
                  {label && <span className="text-gray-500 whitespace-nowrap font-medium">{label}:</span>}
                  {hasArrow ? (
                    <>
                      <span className="text-red-400 line-through">{oldPart}</span>
                      <span className="text-gray-400">→</span>
                      <span className="text-green-700 font-semibold">{newPart}</span>
                    </>
                  ) : (
                    <span className="text-gray-700">{newPart}</span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function ReportsFeedPage() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [messages, setMessages] = useState<FeedMessage[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [wsError, setWsError] = useState(false);
  const [feedRoom, setFeedRoom] = useState<ChatRoom | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // 1. Получить/создать комнату «Отчётность» через специальный эндпоинт
  const { data: roomData, isLoading: roomsLoading, refetch: refetchRooms } = useQuery<ChatRoom | null>({
    queryKey: ["feed-room"],
    queryFn: () => api.get("/chat/feed-room").then((r) => r.data),
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (roomData && roomData.id !== feedRoom?.id) setFeedRoom(roomData);
  }, [roomData]);

  // 2. История сообщений
  const { data: history = [], isLoading: histLoading, refetch: refetchHistory } = useQuery<FeedMessage[]>({
    queryKey: ["feed-messages", feedRoom?.id],
    queryFn: () =>
      feedRoom
        ? api.get(`/chat/rooms/${feedRoom.id}/messages?limit=100`).then((r) => r.data as FeedMessage[]).then((msgs) => [...msgs].reverse())
        : Promise.resolve([]),
    enabled: !!feedRoom,
  });

  useEffect(() => {
    if (history.length > 0) setMessages(history);
    else setMessages([]);
  }, [history, feedRoom?.id]);

  // 3. WebSocket
  const connectWs = useCallback(
    (room: ChatRoom) => {
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
      if (!accessToken) return;
      const wsBase = window.location.origin.replace(/^http/, "ws");
      const ws = new WebSocket(`${wsBase}/api/v1/chat/ws/${room.id}?token=${accessToken}`);
      wsRef.current = ws;
      setWsConnected(false); setWsError(false);

      ws.onopen = () => { setWsConnected(true); setWsError(false); };
      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === "message") {
            const msg: FeedMessage = {
              id: data.id, room_id: data.room_id, sender_id: data.sender_id,
              sender_name: data.sender_name, content: data.content,
              created_at: data.created_at, is_deleted: false,
            };
            setMessages((prev) => prev.find((m) => m.id === msg.id) ? prev : [...prev, msg]);
          }
        } catch {}
      };
      ws.onerror = () => { setWsError(true); setWsConnected(false); };
      ws.onclose = () => { setWsConnected(false); wsRef.current = null; };
    },
    [accessToken]
  );

  useEffect(() => {
    if (feedRoom) connectWs(feedRoom);
    return () => { wsRef.current?.close(); wsRef.current = null; };
  }, [feedRoom?.id]);

  // 4. Auto-scroll
  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Group messages by date
  const grouped: { date: Date; msgs: FeedMessage[] }[] = [];
  for (const msg of messages) {
    const d = new Date(msg.created_at);
    const last = grouped[grouped.length - 1];
    if (last && isSameDay(last.date, d)) {
      last.msgs.push(msg);
    } else {
      grouped.push({ date: d, msgs: [msg] });
    }
  }

  const isLoading = roomsLoading || histLoading;

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* Header */}
      <div className="bg-white border-b px-6 py-3 flex items-center gap-3 flex-shrink-0">
        <div className="p-2 rounded-xl bg-primary-100">
          <Activity size={18} className="text-primary-700" />
        </div>
        <div>
          <h2 className="font-semibold text-gray-900">Лента отчётов</h2>
          <p className="text-xs text-gray-400">
            {feedRoom ? `${feedRoom.member_count} участников` : "Поиск комнаты…"}
          </p>
        </div>

        <div className="ml-auto flex items-center gap-3">
          {/* WS status */}
          {feedRoom && (
            wsConnected ? (
              <span className="flex items-center gap-1.5 text-xs text-green-600">
                <Wifi size={13} /> В сети
              </span>
            ) : wsError ? (
              <button
                onClick={() => feedRoom && connectWs(feedRoom)}
                className="flex items-center gap-1.5 text-xs text-red-500 hover:underline"
              >
                <WifiOff size={13} /> Ошибка · Переподключить
              </button>
            ) : (
              <span className="flex items-center gap-1.5 text-xs text-gray-400">
                <Loader2 size={13} className="animate-spin" /> Подключение…
              </span>
            )
          )}

          <button
            onClick={async () => { await refetchRooms(); refetchHistory(); }}
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
            title="Обновить"
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      {/* Feed */}
      <div
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4"
        onScroll={(e) => {
          const el = e.currentTarget;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
          setAutoScroll(atBottom);
        }}
      >
        {isLoading ? (
          <div className="flex justify-center py-16">
            <Loader2 size={28} className="animate-spin text-gray-300" />
          </div>
        ) : !feedRoom ? (
          <div className="flex flex-col items-center py-20 text-gray-400">
            <Activity size={48} className="mb-4 opacity-20" />
            <p className="font-medium">Лента не найдена</p>
            <p className="text-sm mt-1 text-center max-w-xs">
              Комната «Отчётность» будет создана автоматически при первом добавлении отчёта.
            </p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center py-20 text-gray-400">
            <Activity size={48} className="mb-4 opacity-20" />
            <p className="font-medium">Пока нет записей</p>
            <p className="text-sm mt-1">Отчёты появятся здесь автоматически</p>
          </div>
        ) : (
          <>
            {grouped.map(({ date, msgs }) => (
              <div key={date.toISOString()}>
                {/* Date separator */}
                <div className="flex items-center gap-3 my-4">
                  <div className="flex-1 h-px bg-gray-200" />
                  <span className="text-xs text-gray-400 font-medium px-2">{formatDate(date)}</span>
                  <div className="flex-1 h-px bg-gray-200" />
                </div>

                <div className="space-y-3 max-w-2xl mx-auto">
                  {msgs.map((msg) => (
                    <MessageCard key={msg.id} msg={msg} />
                  ))}
                </div>
              </div>
            ))}
            {!autoScroll && (
              <button
                onClick={() => { setAutoScroll(true); bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }}
                className="fixed bottom-8 right-8 bg-primary-700 text-white text-xs px-4 py-2 rounded-full shadow-lg hover:bg-primary-800 transition-colors"
              >
                ↓ К последним
              </button>
            )}
            <div ref={bottomRef} />
          </>
        )}
      </div>
    </div>
  );
}
