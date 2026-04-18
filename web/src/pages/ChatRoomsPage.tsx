import React, { useState, useEffect, useRef, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus, MessageSquare, Users, Send, X, Loader2, ChevronLeft, UserPlus, Hammer, Settings2, UserMinus,
} from "lucide-react";
import { api } from "../api/client";
import { useAuthStore } from "../store/authStore";

interface ChatRoom {
  id: number;
  name: string | null;
  type: string;
  created_by: number | null;
  created_at: string;
  member_count: number;
  last_message: string | null;
  is_reports_feed?: boolean;
}

interface ChatMessage {
  id: number;
  room_id: number;
  sender_id: number;
  sender_name: string | null;
  content: string;
  created_at: string;
  is_deleted: boolean;
}

interface User {
  id: number;
  full_name: string | null;
  username: string | null;
}

interface RoomMember {
  user_id: number;
  full_name: string | null;
  username: string | null;
}

export default function ChatRoomsPage() {
  const qc = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);

  const [selectedRoom, setSelectedRoom] = useState<ChatRoom | null>(null);
  const [creating, setCreating] = useState(false);
  const [roomName, setRoomName] = useState("");
  const [selectedMembers, setSelectedMembers] = useState<number[]>([]);
  const [memberSearch, setMemberSearch] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [wsConnected, setWsConnected] = useState(false);
  const [wsError, setWsError] = useState(false);
  const [addMembersOpen, setAddMembersOpen] = useState(false);
  const [addMemberSearch, setAddMemberSearch] = useState("");
  const [pendingAddIds, setPendingAddIds] = useState<number[]>([]);
  const [groupManageOpen, setGroupManageOpen] = useState(false);
  const [groupNameDraft, setGroupNameDraft] = useState("");
  const [memberListSearch, setMemberListSearch] = useState("");
  const [hammerAnim, setHammerAnim] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const { data: rooms = [], isLoading } = useQuery<ChatRoom[]>({
    queryKey: ["chat-rooms-admin"],
    queryFn: () => api.get("/chat/rooms").then((r) => r.data),
    refetchInterval: 10000,
  });

  const { data: usersForCreate = [] } = useQuery<User[]>({
    queryKey: ["users-list-chat"],
    queryFn: () => api.get("/users?limit=500").then((r) => r.data),
    enabled: creating || addMembersOpen || groupManageOpen,
  });

  const { data: roomMembers = [], isLoading: roomMembersLoading } = useQuery<RoomMember[]>({
    queryKey: ["chat-room-members", selectedRoom?.id],
    queryFn: () =>
      selectedRoom
        ? api.get(`/chat/rooms/${selectedRoom.id}/members`).then((r) => r.data)
        : Promise.resolve([]),
    enabled: !!selectedRoom && (groupManageOpen || addMembersOpen),
  });

  const addMembersMutation = useMutation({
    mutationFn: ({ roomId, userIds }: { roomId: number; userIds: number[] }) =>
      api.post(`/chat/rooms/${roomId}/members`, { user_ids: userIds }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["chat-rooms-admin"] });
      qc.invalidateQueries({ queryKey: ["chat-room-members", selectedRoom?.id] });
      setSelectedRoom((prev) =>
        prev && prev.id === res.data.id
          ? { ...prev, member_count: res.data.member_count }
          : prev
      );
      setAddMembersOpen(false);
      setPendingAddIds([]);
      setAddMemberSearch("");
    },
    onError: (err: unknown) => {
      const d = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      window.alert(typeof d === "string" ? d : "Не удалось добавить участников");
    },
  });

  const { data: historyMessages = [], isLoading: historyLoading } = useQuery<ChatMessage[]>({
    queryKey: ["chat-messages", selectedRoom?.id],
    queryFn: () =>
      selectedRoom
        ? api.get(`/chat/rooms/${selectedRoom.id}/messages?limit=100`).then((r) => r.data)
        : Promise.resolve([]),
    enabled: !!selectedRoom,
  });

  const createMutation = useMutation({
    mutationFn: (data: unknown) => api.post("/chat/rooms", data),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["chat-rooms-admin"] });
      setCreating(false);
      setRoomName("");
      setSelectedMembers([]);
      setSelectedRoom(res.data);
    },
  });

  const updateRoomMutation = useMutation({
    mutationFn: ({ roomId, name }: { roomId: number; name: string }) =>
      api.patch(`/chat/rooms/${roomId}`, { name }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["chat-rooms-admin"] });
      setSelectedRoom((prev) => (prev && prev.id === res.data.id ? { ...prev, ...res.data } : prev));
    },
    onError: (err: unknown) => {
      const d = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      window.alert(typeof d === "string" ? d : "Не удалось сохранить");
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: ({ roomId, userId }: { roomId: number; userId: number }) =>
      api.delete(`/chat/rooms/${roomId}/members/${userId}`),
    onSuccess: (_, { userId }) => {
      qc.invalidateQueries({ queryKey: ["chat-room-members", selectedRoom?.id] });
      qc.invalidateQueries({ queryKey: ["chat-rooms-admin"] });
      if (user?.id === userId) {
        setSelectedRoom(null);
        setGroupManageOpen(false);
        setMemberListSearch("");
        return;
      }
      setSelectedRoom((prev) =>
        prev ? { ...prev, member_count: Math.max(0, prev.member_count - 1) } : prev
      );
    },
    onError: (err: unknown) => {
      const d = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      window.alert(typeof d === "string" ? d : "Не удалось удалить участника");
    },
  });

  // Sync history into messages when room changes
  useEffect(() => {
    if (historyMessages.length > 0) {
      setMessages(historyMessages);
    } else {
      setMessages([]);
    }
  }, [historyMessages, selectedRoom?.id]);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // WebSocket connection
  const connectWs = useCallback(
    (room: ChatRoom) => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (!accessToken) return;

      // Use current origin but with ws:// scheme — goes through Vite proxy
      const wsBase = window.location.origin.replace(/^http/, "ws");
      const url = `${wsBase}/api/v1/chat/ws/${room.id}?token=${accessToken}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;
      setWsConnected(false);
      setWsError(false);

      ws.onopen = () => {
        setWsConnected(true);
        setWsError(false);
        inputRef.current?.focus();
      };

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === "error" && typeof data.detail === "string") {
            window.alert(data.detail);
            return;
          }
          if (data.type === "message") {
            const msg: ChatMessage = {
              id: data.id,
              room_id: data.room_id,
              sender_id: data.sender_id,
              sender_name: data.sender_name,
              content: data.content,
              created_at: data.created_at,
              is_deleted: false,
            };
            setMessages((prev) => {
              if (prev.find((m) => m.id === msg.id)) return prev;
              return [...prev, msg];
            });
          }
        } catch {}
      };

      ws.onerror = () => {
        setWsError(true);
        setWsConnected(false);
      };

      ws.onclose = () => {
        setWsConnected(false);
        wsRef.current = null;
      };
    },
    [accessToken]
  );

  // Connect WS when room selected
  useEffect(() => {
    if (selectedRoom) {
      connectWs(selectedRoom);
    }
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [selectedRoom?.id]);

  const handleSend = () => {
    const text = inputText.trim();
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "message", content: text }));
    setInputText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const selectRoom = (room: ChatRoom) => {
    setSelectedRoom(room);
    setCreating(false);
    setAddMembersOpen(false);
    setPendingAddIds([]);
    setGroupManageOpen(false);
    setMemberListSearch("");
  };

  const isReportsFeedRoom = (r: ChatRoom | null) =>
    !!r && (r.is_reports_feed === true || r.name === "Отчётность");

  const onGroupHeaderClick = () => {
    if (!selectedRoom || selectedRoom.type !== "group") return;
    if (isReportsFeedRoom(selectedRoom)) {
      setHammerAnim(true);
      window.setTimeout(() => setHammerAnim(false), 750);
      return;
    }
    setGroupNameDraft(selectedRoom.name || "");
    setMemberListSearch("");
    setGroupManageOpen(true);
  };

  const openGroupMembersPanel = () => {
    if (!selectedRoom || selectedRoom.type !== "group") return;
    setGroupNameDraft(selectedRoom.name || "");
    setMemberListSearch("");
    setGroupManageOpen(true);
  };

  const memberIdSet = new Set(roomMembers.map((m) => m.user_id));
  const usersForAdd = usersForCreate.filter((u) => !memberIdSet.has(u.id));
  const filteredForAdd = usersForAdd.filter(
    (u) =>
      !addMemberSearch ||
      (u.full_name || "").toLowerCase().includes(addMemberSearch.toLowerCase()) ||
      String(u.id).includes(addMemberSearch) ||
      (u.username || "").toLowerCase().includes(addMemberSearch.toLowerCase())
  );

  const filteredUsers = usersForCreate.filter(
    (u) =>
      !memberSearch ||
      (u.full_name || "").toLowerCase().includes(memberSearch.toLowerCase()) ||
      String(u.id).includes(memberSearch)
  );

  const filteredRoomMembers = roomMembers.filter((m) => {
    if (!memberListSearch.trim()) return true;
    const q = memberListSearch.toLowerCase();
    return (
      (m.full_name || "").toLowerCase().includes(q) ||
      (m.username || "").toLowerCase().includes(q) ||
      String(m.user_id).includes(q)
    );
  });

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden">
      {/* Sidebar: rooms list */}
      <div className="w-72 flex-shrink-0 border-r border-gray-200 flex flex-col bg-white">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Чаты</h2>
          <button
            className="btn-primary py-1.5 px-3 text-sm flex items-center gap-1"
            onClick={() => { setCreating(true); setSelectedRoom(null); }}
          >
            <Plus size={14} />Новый
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 size={20} className="animate-spin text-gray-400" />
            </div>
          ) : rooms.length === 0 ? (
            <div className="text-center py-12 text-gray-400 text-sm px-4">
              <MessageSquare size={32} className="mx-auto mb-2 opacity-30" />
              Нет чатов. Создайте первый.
            </div>
          ) : (
            rooms.map((room) => (
              <button
                key={room.id}
                onClick={() => selectRoom(room)}
                className={`w-full text-left px-4 py-3 border-b hover:bg-gray-50 transition-colors flex items-start gap-3 ${
                  selectedRoom?.id === room.id ? "bg-primary-50 border-l-2 border-l-primary-700" : ""
                }`}
              >
                <div
                  className={`mt-0.5 p-1.5 rounded-lg flex-shrink-0 ${
                    room.type === "dm" ? "bg-blue-100" : "bg-green-100"
                  }`}
                >
                  {room.type === "dm" ? (
                    <MessageSquare size={14} className="text-blue-600" />
                  ) : (
                    <Users size={14} className="text-green-600" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm truncate">{room.name || `Чат #${room.id}`}</div>
                  <div className="text-xs text-gray-400 truncate mt-0.5">
                    {room.last_message || `${room.member_count} участников`}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Main area */}
      <div className="flex-1 flex flex-col overflow-hidden bg-gray-50">
        {creating ? (
          /* Create room form */
          <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-xl mx-auto">
              <div className="flex items-center gap-3 mb-6">
                <button onClick={() => setCreating(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                  <ChevronLeft size={18} />
                </button>
                <h2 className="text-xl font-bold">Создать групповой чат</h2>
              </div>

              <div className="card mb-4">
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Название чата</label>
                  <input
                    className="input"
                    value={roomName}
                    onChange={(e) => setRoomName(e.target.value)}
                    placeholder="Бригада №1"
                    autoFocus
                  />
                </div>

                {selectedMembers.length > 0 && (
                  <div className="mb-4">
                    <label className="block text-xs text-gray-500 mb-1">
                      Участники ({selectedMembers.length}):
                    </label>
                    <div className="flex flex-wrap gap-1">
                      {selectedMembers.map((id) => {
                        const u = usersForCreate.find((u) => u.id === id);
                        return (
                          <span
                            key={id}
                            className="bg-primary-100 text-primary-700 text-xs px-2 py-0.5 rounded-full flex items-center gap-1"
                          >
                            {u?.full_name || `#${id}`}
                            <button
                              onClick={() => setSelectedMembers(selectedMembers.filter((x) => x !== id))}
                              className="ml-0.5"
                            >
                              <X size={10} />
                            </button>
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Добавить участников</label>
                  <input
                    className="input mb-2"
                    placeholder="Поиск по имени..."
                    value={memberSearch}
                    onChange={(e) => setMemberSearch(e.target.value)}
                  />
                  <div className="border rounded-xl max-h-56 overflow-y-auto divide-y">
                    {filteredUsers.map((u) => (
                      <label
                        key={u.id}
                        className="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedMembers.includes(u.id)}
                          onChange={(e) => {
                            if (e.target.checked) setSelectedMembers([...selectedMembers, u.id]);
                            else setSelectedMembers(selectedMembers.filter((x) => x !== u.id));
                          }}
                          className="accent-primary-700"
                        />
                        <div>
                          <div className="text-sm font-medium">{u.full_name || `Пользователь #${u.id}`}</div>
                          {u.username && <div className="text-xs text-gray-400">@{u.username}</div>}
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="flex gap-2">
                  <button className="btn-secondary flex-1" onClick={() => setCreating(false)}>
                    Отмена
                  </button>
                  <button
                    className="btn-primary flex-1"
                    disabled={!roomName.trim() || createMutation.isPending}
                    onClick={() =>
                      createMutation.mutate({
                        name: roomName.trim(),
                        type: "group",
                        member_ids: selectedMembers,
                      })
                    }
                  >
                    {createMutation.isPending ? (
                      <Loader2 size={14} className="animate-spin inline mr-1" />
                    ) : null}
                    Создать чат
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : selectedRoom ? (
          /* Chat view */
          <>
            {/* Chat header */}
            <div className="bg-white border-b px-6 py-3 flex items-center gap-3 relative overflow-hidden">
              {hammerAnim && (
                <div
                  className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/90 pointer-events-none"
                  aria-hidden
                >
                  <Hammer
                    size={40}
                    className="text-amber-500 drop-shadow-sm origin-bottom animate-[hammer_0.75s_ease-in-out]"
                    strokeWidth={2}
                  />
                  <p className="text-xs text-gray-500 mt-2 font-medium">Ещё дорабатываем…</p>
                </div>
              )}
              <style>{`
                @keyframes hammer {
                  0%, 100% { transform: rotate(-18deg); }
                  25% { transform: rotate(28deg); }
                  50% { transform: rotate(-10deg); }
                  75% { transform: rotate(22deg); }
                }
              `}</style>
              <button
                type="button"
                className={`flex items-center gap-3 text-left min-w-0 flex-1 rounded-xl px-1 py-0.5 -ml-1 transition-colors ${
                  selectedRoom.type === "group"
                    ? "hover:bg-gray-50 cursor-pointer"
                    : "cursor-default"
                }`}
                onClick={onGroupHeaderClick}
                disabled={selectedRoom.type !== "group"}
                title={
                  selectedRoom.type !== "group"
                    ? undefined
                    : isReportsFeedRoom(selectedRoom)
                      ? "Лента отчётов (настройки недоступны)"
                      : "Настройки группы"
                }
              >
                <div
                  className={`p-2 rounded-xl flex-shrink-0 ${
                    selectedRoom.type === "dm" ? "bg-blue-100" : "bg-green-100"
                  }`}
                >
                  {selectedRoom.type === "dm" ? (
                    <MessageSquare size={16} className="text-blue-600" />
                  ) : (
                    <Users size={16} className="text-green-600" />
                  )}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold truncate">
                      {selectedRoom.name || `Чат #${selectedRoom.id}`}
                    </h3>
                    {selectedRoom.type === "group" && !isReportsFeedRoom(selectedRoom) && (
                      <Settings2 size={14} className="text-gray-400 flex-shrink-0" aria-hidden />
                    )}
                  </div>
                  <p className="text-xs text-gray-400">
                    {selectedRoom.member_count} участников
                    {isReportsFeedRoom(selectedRoom) && " · только лента отчётов"}
                  </p>
                </div>
              </button>
              {selectedRoom.type === "group" && (
                <>
                  <button
                    type="button"
                    onClick={openGroupMembersPanel}
                    className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 transition-colors"
                    title="Список участников и управление"
                  >
                    <Users size={16} />
                    Участники
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setAddMembersOpen(true);
                      setPendingAddIds([]);
                      setAddMemberSearch("");
                    }}
                    className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border border-primary-200 text-primary-700 hover:bg-primary-50 transition-colors"
                    title="Добавить участников"
                  >
                    <UserPlus size={16} />
                    Добавить
                  </button>
                </>
              )}
              <div className="ml-auto flex items-center gap-2">
                {wsConnected ? (
                  <span className="flex items-center gap-1 text-xs text-green-600">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                    Онлайн
                  </span>
                ) : wsError ? (
                  <span className="flex items-center gap-1 text-xs text-red-500">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400 inline-block" />
                    Ошибка подключения
                    <button
                      onClick={() => connectWs(selectedRoom)}
                      className="underline ml-1"
                    >
                      Переподключить
                    </button>
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-xs text-gray-400">
                    <Loader2 size={12} className="animate-spin" />
                    Подключение...
                  </span>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
              {historyLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 size={20} className="animate-spin text-gray-400" />
                </div>
              ) : messages.length === 0 ? (
                <div className="text-center py-16 text-gray-400">
                  <MessageSquare size={40} className="mx-auto mb-3 opacity-20" />
                  <p className="text-sm">Нет сообщений. Начните переписку!</p>
                </div>
              ) : (
                messages.map((msg) => {
                  const isOwn = msg.sender_id === user?.id;
                  return (
                    <div
                      key={msg.id}
                      className={`flex ${isOwn ? "justify-end" : "justify-start"}`}
                    >
                      <div className={`max-w-[70%] ${isOwn ? "items-end" : "items-start"} flex flex-col`}>
                        {!isOwn && (
                          <span className="text-xs text-gray-500 mb-1 ml-1">
                            {msg.sender_name || `#${msg.sender_id}`}
                          </span>
                        )}
                        <div
                          className={`px-4 py-2 rounded-2xl text-sm ${
                            isOwn
                              ? "bg-primary-700 text-white rounded-br-sm"
                              : "bg-white border border-gray-200 text-gray-800 rounded-bl-sm"
                          }`}
                        >
                          {msg.content}
                        </div>
                        <span className="text-xs text-gray-400 mt-1 px-1">
                          {new Date(msg.created_at).toLocaleTimeString("ru", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="bg-white border-t px-4 py-3">
              <div className="flex gap-2 items-center">
                <input
                  ref={inputRef}
                  className="input flex-1"
                  placeholder={
                    isReportsFeedRoom(selectedRoom)
                      ? "В этой комнате только лента отчётов — писать нельзя"
                      : wsConnected
                        ? "Написать сообщение... (Enter — отправить)"
                        : "Подключение к чату..."
                  }
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={!wsConnected || isReportsFeedRoom(selectedRoom)}
                />
                <button
                  className="btn-primary px-4 py-2.5 flex items-center gap-1.5 disabled:opacity-50"
                  onClick={handleSend}
                  disabled={!wsConnected || !inputText.trim() || isReportsFeedRoom(selectedRoom)}
                >
                  <Send size={15} />
                  Отправить
                </button>
              </div>
            </div>

            {groupManageOpen && selectedRoom?.type === "group" && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" role="dialog">
                <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] flex flex-col">
                  <div className="px-5 py-4 border-b flex items-center justify-between flex-shrink-0">
                    <h4 className="font-semibold text-gray-900">
                      {isReportsFeedRoom(selectedRoom) ? "Участники (лента отчётов)" : "Настройки группы"}
                    </h4>
                    <button
                      type="button"
                      onClick={() => {
                        setGroupManageOpen(false);
                        setMemberListSearch("");
                      }}
                      className="p-2 -m-1 rounded-lg hover:bg-gray-100"
                      aria-label="Закрыть"
                    >
                      <X size={18} />
                    </button>
                  </div>
                  <div className="px-5 py-4 overflow-y-auto flex-1 min-h-0 space-y-5">
                    {!isReportsFeedRoom(selectedRoom) && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Название чата</label>
                        <div className="flex gap-2 flex-wrap">
                          <input
                            className="input flex-1 min-w-[200px]"
                            value={groupNameDraft}
                            onChange={(e) => setGroupNameDraft(e.target.value)}
                            placeholder="Название"
                          />
                          <button
                            type="button"
                            className="btn-primary px-4"
                            disabled={!groupNameDraft.trim() || updateRoomMutation.isPending}
                            onClick={() =>
                              selectedRoom &&
                              updateRoomMutation.mutate({
                                roomId: selectedRoom.id,
                                name: groupNameDraft.trim(),
                              })
                            }
                          >
                            {updateRoomMutation.isPending ? (
                              <Loader2 size={14} className="animate-spin inline mr-1" />
                            ) : null}
                            Сохранить название
                          </button>
                        </div>
                      </div>
                    )}

                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <label className="text-sm font-medium text-gray-700">
                          Участники ({roomMembers.length})
                        </label>
                        <button
                          type="button"
                          className="text-sm text-primary-700 hover:underline flex items-center gap-1"
                          onClick={() => {
                            setAddMembersOpen(true);
                            setPendingAddIds([]);
                            setAddMemberSearch("");
                          }}
                        >
                          <UserPlus size={14} />
                          Добавить
                        </button>
                      </div>
                      <input
                        className="input w-full mb-2 text-sm"
                        placeholder="Поиск по имени или ID…"
                        value={memberListSearch}
                        onChange={(e) => setMemberListSearch(e.target.value)}
                      />
                      <div className="border rounded-xl divide-y max-h-56 overflow-y-auto">
                        {roomMembersLoading ? (
                          <div className="flex justify-center py-10">
                            <Loader2 size={22} className="animate-spin text-primary-600" />
                          </div>
                        ) : filteredRoomMembers.length === 0 ? (
                          <div className="p-4 text-center text-sm text-gray-400">
                            {roomMembers.length === 0 ? "Нет участников" : "Никого не найдено"}
                          </div>
                        ) : (
                          filteredRoomMembers.map((m) => {
                            const canRemove = roomMembers.length > 1;
                            return (
                              <div
                                key={m.user_id}
                                className="flex items-center justify-between gap-2 px-3 py-2.5 hover:bg-gray-50"
                              >
                                <div className="min-w-0">
                                  <div className="text-sm font-medium text-gray-800 truncate">
                                    {m.full_name || `Пользователь #${m.user_id}`}
                                    {user?.id === m.user_id && (
                                      <span className="text-xs text-primary-600 font-normal ml-1">(вы)</span>
                                    )}
                                  </div>
                                  {m.username && (
                                    <div className="text-xs text-gray-400 truncate">@{m.username}</div>
                                  )}
                                  <div className="text-[10px] text-gray-300 font-mono">id {m.user_id}</div>
                                </div>
                                <button
                                  type="button"
                                  disabled={!canRemove || removeMemberMutation.isPending}
                                  title={
                                    canRemove
                                      ? "Удалить из чата"
                                      : "Нельзя удалить последнего участника"
                                  }
                                  className="flex-shrink-0 p-2 rounded-lg border border-red-100 text-red-500 hover:bg-red-50 disabled:opacity-40 disabled:cursor-not-allowed"
                                  onClick={() => {
                                    if (!selectedRoom || !canRemove) return;
                                    const label = m.full_name || `#${m.user_id}`;
                                    if (
                                      !window.confirm(
                                        `Убрать ${label} из группы «${selectedRoom.name || "чат"}»?`
                                      )
                                    )
                                      return;
                                    removeMemberMutation.mutate({
                                      roomId: selectedRoom.id,
                                      userId: m.user_id,
                                    });
                                  }}
                                >
                                  <UserMinus size={16} />
                                </button>
                              </div>
                            );
                          })
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-2">
                        Удаление доступно только администраторам. В группе всегда должен остаться хотя бы один
                        участник.
                      </p>
                    </div>
                  </div>
                  <div className="px-5 py-3 border-t flex justify-end flex-shrink-0">
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => {
                        setGroupManageOpen(false);
                        setMemberListSearch("");
                      }}
                    >
                      Закрыть
                    </button>
                  </div>
                </div>
              </div>
            )}

            {addMembersOpen && selectedRoom?.type === "group" && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" role="dialog">
                <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[85vh] flex flex-col">
                  <div className="px-5 py-4 border-b flex items-center justify-between">
                    <h4 className="font-semibold text-gray-900">Добавить участников</h4>
                    <button
                      type="button"
                      onClick={() => {
                        setAddMembersOpen(false);
                        setPendingAddIds([]);
                      }}
                      className="p-2 -m-1 rounded-lg hover:bg-gray-100"
                      aria-label="Закрыть"
                    >
                      <X size={18} />
                    </button>
                  </div>
                  <div className="px-5 py-3 flex-1 overflow-y-auto min-h-0">
                    <p className="text-sm text-gray-500 mb-3">
                      Выберите сотрудников, которых ещё нет в этом чате.
                    </p>
                    <input
                      className="input mb-2"
                      placeholder="Поиск по имени..."
                      value={addMemberSearch}
                      onChange={(e) => setAddMemberSearch(e.target.value)}
                    />
                    <div className="border rounded-xl max-h-64 overflow-y-auto divide-y">
                      {roomMembersLoading ? (
                        <div className="flex justify-center py-8">
                          <Loader2 size={22} className="animate-spin text-primary-600" />
                        </div>
                      ) : filteredForAdd.length === 0 ? (
                        <div className="p-4 text-center text-sm text-gray-400">
                          {usersForCreate.length === 0 ? "Загрузка списка пользователей…" : "Все пользователи уже в чате"}
                        </div>
                      ) : (
                        filteredForAdd.map((u) => (
                          <label
                            key={u.id}
                            className="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={pendingAddIds.includes(u.id)}
                              onChange={(e) => {
                                if (e.target.checked) setPendingAddIds([...pendingAddIds, u.id]);
                                else setPendingAddIds(pendingAddIds.filter((x) => x !== u.id));
                              }}
                              className="accent-primary-700"
                            />
                            <div>
                              <div className="text-sm font-medium">{u.full_name || `Пользователь #${u.id}`}</div>
                              {u.username && <div className="text-xs text-gray-400">@{u.username}</div>}
                            </div>
                          </label>
                        ))
                      )}
                    </div>
                  </div>
                  <div className="px-5 py-4 border-t flex gap-2 justify-end">
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => {
                        setAddMembersOpen(false);
                        setPendingAddIds([]);
                      }}
                    >
                      Отмена
                    </button>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={pendingAddIds.length === 0 || addMembersMutation.isPending}
                      onClick={() =>
                        selectedRoom &&
                        addMembersMutation.mutate({ roomId: selectedRoom.id, userIds: pendingAddIds })
                      }
                    >
                      {addMembersMutation.isPending ? (
                        <Loader2 size={14} className="animate-spin inline mr-1" />
                      ) : null}
                      Добавить в чат
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        ) : (
          /* Empty state */
          <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
            <MessageSquare size={56} className="mb-4 opacity-20" />
            <p className="text-lg font-medium">Выберите чат</p>
            <p className="text-sm mt-1">или создайте новый</p>
          </div>
        )}
      </div>
    </div>
  );
}
