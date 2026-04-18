import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  View, Text, StyleSheet, FlatList, TextInput, TouchableOpacity,
  KeyboardAvoidingView, Platform, ActivityIndicator, ScrollView,
} from "react-native";
import { useRoute, RouteProp } from "@react-navigation/native";
import { useQuery } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { chatApi, ChatMessage } from "../api/chat";
import { useAuthStore } from "../store/authStore";
import { RootStackParamList } from "../navigation";

type Route = RouteProp<RootStackParamList, "ChatRoom">;

const FEED_ROOM_NAME = "Отчётность";

// ── Feed card helpers ────────────────────────────────────────────────────────

type MsgKind = "new" | "edited" | "deleted" | "other";

function getMsgKind(content: string): MsgKind {
  const head = content.trimStart().slice(0, 8);
  if (head.includes("✅")) return "new";
  if (head.includes("✏️") || content.startsWith("✏")) return "edited";
  if (head.includes("🗑️") || content.startsWith("🗑")) return "deleted";
  return "other";
}

const KIND_META: Record<MsgKind, { badge: string; border: string; bg: string; label: string }> = {
  new:     { badge: "#d1fae5", border: "#6ee7b7", bg: "#f0fdf4", label: "Новая запись" },
  edited:  { badge: "#fef3c7", border: "#fcd34d", bg: "#fffbeb", label: "Изменено" },
  deleted: { badge: "#fee2e2", border: "#fca5a5", bg: "#fff5f5", label: "Удалено" },
  other:   { badge: "#f3f4f6", border: "#e5e7eb", bg: "#ffffff", label: "Сообщение" },
};
const KIND_TEXT: Record<MsgKind, string> = {
  new: "#065f46", edited: "#92400e", deleted: "#991b1b", other: "#374151",
};

interface ParsedRow { key: string; val: string | null; isDiff: boolean; isId: boolean }

function parseMsgLines(content: string): { rows: ParsedRow[] } {
  const lines = content.split("\n").map((l) => l.trim()).filter(Boolean);
  const rows: ParsedRow[] = [];
  let inDiff = false;
  for (const line of lines.slice(1)) {
    if (line === "Изменения:") { inDiff = true; continue; }
    const colonIdx = line.indexOf(": ");
    const isEmoji = /^[📅📍🚜⏱👷🔧]/.test(line);
    const isId = line.startsWith("ID:");
    if (colonIdx > 0 && !isEmoji) {
      rows.push({ key: line.slice(0, colonIdx), val: line.slice(colonIdx + 2), isDiff: inDiff, isId });
    } else {
      rows.push({ key: line, val: null, isDiff: inDiff, isId });
    }
  }
  return { rows };
}

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

function FeedCard({ msg }: { msg: ChatMessage }) {
  const kind = getMsgKind(msg.content);
  const meta = KIND_META[kind];
  const textColor = KIND_TEXT[kind];
  const { rows } = parseMsgLines(msg.content);
  const actionDateTime = formatActionDateTime(msg.created_at);

  const mainRows = rows.filter((r) => !r.isDiff);
  const diffRows = rows.filter((r) => r.isDiff);
  // First non-emoji solo line is the sender name
  const nameIdx = mainRows.findIndex((r) => r.val === null && !r.isId && !isEmojiLine(r.key));

  return (
    <View style={[styles.feedCard, { borderColor: meta.border, backgroundColor: meta.bg }]}>
      {/* Header — badge only */}
      <View style={[styles.feedCardHeader, { backgroundColor: meta.badge }]}>
        <Text style={[styles.feedCardBadge, { color: textColor }]}>{meta.label}</Text>
      </View>

      {/* Body — compact inline lines */}
      <View style={styles.feedCardBody}>
        {mainRows.map((row, i) => {
          // Name row — show with action date/time
          if (i === nameIdx) {
            return (
              <View key={i} style={styles.feedNameRow}>
                <Text style={styles.feedNameText}>{row.key}</Text>
                <Text style={styles.feedNameTime}>{actionDateTime}</Text>
              </View>
            );
          }
          if (row.isId) {
            return (
              <Text key={i} style={styles.feedIdText}>
                {row.key}{row.val ? ` ${row.val}` : ""}
              </Text>
            );
          }
          // Solo emoji line (📅, 📍, 🚜, ⏱) — show as-is
          if (row.val === null) {
            return <Text key={i} style={styles.feedSoloLine}>{row.key}</Text>;
          }
          // key-value: show inline "Key: Value" — skip dashes
          if (!row.val || row.val === "—") return null;
          return (
            <Text key={i} style={styles.feedKvLine}>
              <Text style={styles.feedKvKey}>{row.key}: </Text>
              <Text style={styles.feedKvVal}>{row.val}</Text>
            </Text>
          );
        })}

        {diffRows.length > 0 && (
          <View style={styles.diffSection}>
            <Text style={styles.diffTitle}>ЧТО ИЗМЕНИЛОСЬ</Text>
            {diffRows.map((row, i) => {
              const fullVal = row.val ?? row.key;
              const arrowIdx = fullVal.indexOf(" → ");
              const hasArrow = arrowIdx > -1;
              const oldPart = hasArrow ? fullVal.slice(0, arrowIdx) : null;
              const newPart = hasArrow ? fullVal.slice(arrowIdx + 3) : fullVal;
              const label = row.val !== null ? row.key : null;
              return (
                <Text key={i} style={styles.diffRow}>
                  {label ? <Text style={styles.diffKey}>{label}: </Text> : null}
                  {hasArrow ? (
                    <>
                      <Text style={styles.diffOld}>{oldPart}</Text>
                      <Text style={styles.diffArrowSymbol}> → </Text>
                      <Text style={styles.diffNew}>{newPart}</Text>
                    </>
                  ) : (
                    <Text style={styles.diffArrow}>{newPart}</Text>
                  )}
                </Text>
              );
            })}
          </View>
        )}
      </View>
    </View>
  );
}

// ── Main ─────────────────────────────────────────────────────────────────────

export default function ChatRoomScreen() {
  const route = useRoute<Route>();
  const { user } = useAuthStore();
  const isFeedRoom = route.params.name === FEED_ROOM_NAME;
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const listRef = useRef<FlatList>(null);

  const { isLoading, data: initialMessages } = useQuery({
    queryKey: ["messages", route.params.id],
    queryFn: () => chatApi.getMessages(route.params.id),
  });

  useEffect(() => {
    if (initialMessages) setMessages(initialMessages);
  }, [initialMessages]);

  useEffect(() => {
    let ws: WebSocket;
    chatApi.connectWebSocket(route.params.id).then((socket) => {
      ws = socket;
      wsRef.current = socket;
      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "message") {
          setMessages((prev) => [...prev, {
            id: data.id, room_id: data.room_id, sender_id: data.sender_id,
            sender_name: data.sender_name, content: data.content,
            created_at: data.created_at, is_deleted: false,
          }]);
        }
      };
      socket.onerror = () => {};
      socket.onclose = () => {};
    });
    return () => { ws?.close(); };
  }, [route.params.id]);

  const sendMessage = useCallback(() => {
    if (!text.trim() || !wsRef.current) return;
    wsRef.current.send(JSON.stringify({ type: "message", content: text.trim() }));
    setText("");
  }, [text]);

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={88}
    >
      {isLoading ? (
        <ActivityIndicator style={styles.center} color="#1a5c2e" size="large" />
      ) : isFeedRoom ? (
        /* ── Feed view ─────────────────────────────────────── */
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(m) => String(m.id)}
          contentContainerStyle={styles.feedList}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
          ListEmptyComponent={
            <View style={styles.feedEmpty}>
              <Ionicons name="newspaper-outline" size={40} color="#ccc" />
              <Text style={styles.feedEmptyText}>Пока нет записей</Text>
              <Text style={styles.feedEmptySubText}>Отчёты появятся здесь автоматически</Text>
            </View>
          }
          renderItem={({ item }) => <FeedCard msg={item} />}
        />
      ) : (
        /* ── Chat view ─────────────────────────────────────── */
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(m) => String(m.id)}
          contentContainerStyle={{ padding: 12 }}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: false })}
          renderItem={({ item }) => {
            const isMe = item.sender_id === user?.id;
            return (
              <View style={[styles.msgRow, isMe && styles.msgRowMe]}>
                {!isMe && (
                  <View style={styles.avatar}>
                    <Text style={styles.avatarText}>{(item.sender_name || "?")[0].toUpperCase()}</Text>
                  </View>
                )}
                <View style={[styles.bubble, isMe && styles.bubbleMe]}>
                  {!isMe && <Text style={styles.senderName}>{item.sender_name}</Text>}
                  <Text style={[styles.msgText, isMe && styles.msgTextMe]}>{item.content}</Text>
                  <Text style={[styles.msgTime, isMe && styles.msgTimeMe]}>
                    {new Date(item.created_at).toLocaleTimeString("ru", { hour: "2-digit", minute: "2-digit" })}
                  </Text>
                </View>
              </View>
            );
          }}
        />
      )}

      {isFeedRoom ? (
        <View style={styles.feedBanner}>
          <Ionicons name="newspaper-outline" size={15} color="#888" />
          <Text style={styles.feedBannerText}>Только лента отчётов — отправка сообщений недоступна</Text>
        </View>
      ) : (
        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            value={text}
            onChangeText={setText}
            placeholder="Сообщение..."
            multiline
            maxLength={2000}
          />
          <TouchableOpacity style={styles.sendBtn} onPress={sendMessage} disabled={!text.trim()}>
            <Ionicons name="send" size={20} color="#fff" />
          </TouchableOpacity>
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f0f4f0" },
  center: { flex: 1 },

  // Feed card
  feedList: { padding: 8, gap: 6, paddingBottom: 12 },
  feedCard: {
    borderWidth: 1, borderRadius: 10, overflow: "hidden",
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.04, elevation: 1,
  },
  feedCardHeader: {
    paddingHorizontal: 9, paddingVertical: 4,
  },
  feedCardBadge: { fontSize: 11, fontWeight: "700" },
  feedCardBody: { paddingHorizontal: 9, paddingTop: 5, paddingBottom: 7 },
  // Name + action time row
  feedNameRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 3 },
  feedNameText: { fontSize: 12, fontWeight: "700", color: "#111827", flex: 1 },
  feedNameTime: { fontSize: 10, color: "#9ca3af", marginLeft: 6 },
  // Emoji lines (📅 …, 📍 …, 🚜 …, ⏱ …) — shown as single text line
  feedSoloLine: { fontSize: 12, color: "#374151", lineHeight: 18 },
  // Key-value inline: "Техника: Трактор"
  feedKvLine: { fontSize: 12, color: "#374151", lineHeight: 18 },
  feedKvKey: { fontSize: 11, color: "#6b7280" },
  feedKvVal: { fontSize: 12, fontWeight: "600", color: "#1f2937" },
  // ID line
  feedIdText: { fontSize: 10, color: "#9ca3af", marginTop: 4, paddingTop: 4, borderTopWidth: 1, borderTopColor: "#f3f4f6" },
  diffSection: { marginTop: 5, paddingTop: 5, borderTopWidth: 1, borderTopColor: "#e5e7eb" },
  diffTitle: { fontSize: 9, color: "#9ca3af", fontWeight: "700", marginBottom: 3, letterSpacing: 0.5 },
  diffRow: { fontSize: 11, lineHeight: 17 },
  diffKey: { fontSize: 11, color: "#6b7280", fontWeight: "600" },
  diffArrow: { fontSize: 11, color: "#374151" },
  diffOld: { fontSize: 11, color: "#f87171", textDecorationLine: "line-through" },
  diffArrowSymbol: { fontSize: 11, color: "#9ca3af" },
  diffNew: { fontSize: 11, color: "#16a34a", fontWeight: "700" },
  feedEmpty: { alignItems: "center", paddingTop: 80 },
  feedEmptyText: { fontSize: 15, color: "#aaa", marginTop: 10, fontWeight: "600" },
  feedEmptySubText: { fontSize: 12, color: "#c4c4c4", marginTop: 4 },

  // Regular chat
  msgRow: { flexDirection: "row", marginBottom: 10, alignItems: "flex-end" },
  msgRowMe: { flexDirection: "row-reverse" },
  avatar: { width: 32, height: 32, borderRadius: 16, backgroundColor: "#2d6a4f", justifyContent: "center", alignItems: "center", marginRight: 8, marginBottom: 4 },
  avatarText: { color: "#fff", fontSize: 13, fontWeight: "bold" },
  bubble: { maxWidth: "75%", backgroundColor: "#fff", borderRadius: 16, borderBottomLeftRadius: 4, padding: 12, shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, elevation: 1 },
  bubbleMe: { backgroundColor: "#1a5c2e", borderBottomLeftRadius: 16, borderBottomRightRadius: 4 },
  senderName: { fontSize: 11, color: "#1a5c2e", fontWeight: "bold", marginBottom: 3 },
  msgText: { fontSize: 15, color: "#222", lineHeight: 20 },
  msgTextMe: { color: "#fff" },
  msgTime: { fontSize: 10, color: "#aaa", marginTop: 4, textAlign: "right" },
  msgTimeMe: { color: "rgba(255,255,255,0.7)" },
  inputRow: { flexDirection: "row", alignItems: "flex-end", padding: 12, backgroundColor: "#fff", borderTopWidth: 1, borderTopColor: "#eee", gap: 10 },
  input: { flex: 1, borderWidth: 1, borderColor: "#ddd", borderRadius: 20, paddingHorizontal: 16, paddingVertical: 10, fontSize: 15, maxHeight: 100, backgroundColor: "#fafafa" },
  sendBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: "#1a5c2e", justifyContent: "center", alignItems: "center" },
  feedBanner: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 16, paddingVertical: 10, backgroundColor: "#f9fafb", borderTopWidth: 1, borderTopColor: "#eee" },
  feedBannerText: { fontSize: 12, color: "#9ca3af", flex: 1 },
});
