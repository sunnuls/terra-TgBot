import { Platform } from "react-native";
import { api, WS_URL } from "./client";

export interface ChatRoom {
  id: number;
  name: string | null;
  type: string;
  created_by: number | null;
  created_at: string;
  member_count: number;
  last_message: string | null;
  /** true для комнаты «Отчётность» (лента отчётов, без отправки сообщений) */
  is_reports_feed?: boolean;
}

export interface ChatMessage {
  id: number;
  room_id: number;
  sender_id: number | null;
  sender_name: string | null;
  content: string;
  created_at: string;
  is_deleted: boolean;
}

export interface ChatRoomMember {
  user_id: number;
  full_name: string | null;
  username: string | null;
}

export interface CreateRoomPayload {
  name?: string;
  type: "dm" | "group";
  member_ids: number[];
}

export const chatApi = {
  getFeedRoom: () =>
    api.get<ChatRoom | null>("/chat/feed-room").then((r) => r.data).catch(() => null),

  listRooms: () => api.get<ChatRoom[]>("/chat/rooms").then((r) => r.data),

  createRoom: (data: CreateRoomPayload) =>
    api.post<ChatRoom>("/chat/rooms", data).then((r) => r.data),

  getMessages: (room_id: number, before?: number, limit = 50) =>
    api
      .get<ChatMessage[]>(`/chat/rooms/${room_id}/messages`, {
        params: { before, limit },
      })
      .then((r) => r.data),

  listMembers: (room_id: number) =>
    api.get<ChatRoomMember[]>(`/chat/rooms/${room_id}/members`).then((r) => r.data),

  /** Только для администраторов (роль admin). */
  removeMember: (room_id: number, user_id: number) =>
    api.delete(`/chat/rooms/${room_id}/members/${user_id}`),

  connectWebSocket: async (room_id: number) => {
    let token: string | null = null;
    if (Platform.OS === "web") {
      token = localStorage.getItem("access_token");
    } else {
      const SecureStore = await import("expo-secure-store");
      token = await SecureStore.getItemAsync("access_token");
    }
    const url = `${WS_URL}/chat/ws/${room_id}?token=${token}`;
    return new WebSocket(url);
  },
};
