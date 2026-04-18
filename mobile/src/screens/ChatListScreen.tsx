import React, { useState } from "react";
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator,
  RefreshControl, Modal, Alert, ScrollView,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { chatApi, ChatRoom } from "../api/chat";
import { api } from "../api/client";
import { RootStackParamList } from "../navigation";
import EmptyState from "../components/EmptyState";
import Avatar from "../components/Avatar";

type Nav = NativeStackNavigationProp<RootStackParamList>;

interface UserListItem {
  id: number;
  full_name: string | null;
  username: string | null;
  role: string;
}

export default function ChatListScreen() {
  const nav = useNavigation<Nav>();
  const qc = useQueryClient();
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedUsers, setSelectedUsers] = useState<number[]>([]);
  const [chatType, setChatType] = useState<"dm" | "group">("dm");

  const { data: feedRoom } = useQuery({
    queryKey: ["feed_room"],
    queryFn: chatApi.getFeedRoom,
  });

  const { data: rawRooms = [], isLoading, refetch, isRefetching } = useQuery({
    queryKey: ["chat_rooms"],
    queryFn: chatApi.listRooms,
  });

  const rooms: ChatRoom[] = rawRooms.filter((r) => r.name !== "Отчётность");

  const { data: users = [] } = useQuery<UserListItem[]>({
    queryKey: ["users_list"],
    queryFn: () => api.get("/users").then((r) => r.data),
    enabled: modalVisible,
  });

  const createMutation = useMutation({
    mutationFn: chatApi.createRoom,
    onSuccess: (room) => {
      qc.invalidateQueries({ queryKey: ["chat_rooms"] });
      setModalVisible(false);
      setSelectedUsers([]);
      nav.navigate("ChatRoom", { id: room.id, name: room.name || `Чат #${room.id}` });
    },
    onError: (e: any) => {
      Alert.alert("Ошибка", e?.response?.data?.detail || "Не удалось создать чат");
    },
  });

  const toggleUser = (id: number) => {
    if (chatType === "dm") {
      setSelectedUsers([id]);
    } else {
      setSelectedUsers((prev) =>
        prev.includes(id) ? prev.filter((u) => u !== id) : [...prev, id]
      );
    }
  };

  const handleCreate = () => {
    if (selectedUsers.length === 0) {
      Alert.alert("Выберите участников");
      return;
    }
    createMutation.mutate({
      type: chatType,
      member_ids: selectedUsers,
    });
  };

  return (
    <View style={styles.container}>
      {feedRoom && (
        <TouchableOpacity
          style={styles.feedBanner}
          onPress={() => nav.navigate("ChatRoom", { id: feedRoom.id, name: feedRoom.name || "Отчётность" })}
        >
          <View style={styles.feedBannerLeft}>
            <View style={styles.feedIconWrap}>
              <Ionicons name="newspaper-outline" size={22} color="#fff" />
            </View>
            <View style={{ flex: 1 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                <Text style={styles.feedBannerTitle}>Отчётность</Text>
                <View style={styles.feedPinBadge}>
                  <Text style={styles.feedPinText}>лента</Text>
                </View>
              </View>
              <Text style={styles.feedBannerSub} numberOfLines={1}>
                {feedRoom.last_message || "Здесь появляются все отчёты"}
              </Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color="#1a5c2e" />
        </TouchableOpacity>
      )}

      {isLoading ? (
        <ActivityIndicator style={styles.center} color="#1a5c2e" size="large" />
      ) : (
        <FlatList
          data={rooms}
          keyExtractor={(r) => String(r.id)}
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
          contentContainerStyle={{ padding: 12, paddingBottom: 80 }}
          ListEmptyComponent={
            <EmptyState
              icon="chatbubbles-outline"
              message="Нет чатов"
              subtitle="Нажмите + чтобы создать новый чат"
            />
          }
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.roomCard}
              onPress={() => nav.navigate("ChatRoom", { id: item.id, name: item.name || `Чат ${item.id}` })}
            >
              <Avatar name={item.name || `Чат ${item.id}`} size={44} />
              <View style={styles.roomInfo}>
                <Text style={styles.roomName}>{item.name || `Чат #${item.id}`}</Text>
                <Text style={styles.roomLast} numberOfLines={1}>
                  {item.last_message || "Нет сообщений"}
                </Text>
              </View>
              <View style={styles.roomMeta}>
                <Ionicons
                  name={item.type === "dm" ? "person-outline" : "people-outline"}
                  size={14}
                  color="#aaa"
                />
                <Text style={styles.memberCount}>{item.member_count} чел</Text>
              </View>
            </TouchableOpacity>
          )}
        />
      )}

      <TouchableOpacity style={styles.fab} onPress={() => setModalVisible(true)}>
        <Ionicons name="add" size={28} color="#fff" />
      </TouchableOpacity>

      <Modal visible={modalVisible} animationType="slide" presentationStyle="pageSheet">
        <View style={styles.modal}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Новый чат</Text>
            <TouchableOpacity onPress={() => { setModalVisible(false); setSelectedUsers([]); }}>
              <Ionicons name="close" size={24} color="#333" />
            </TouchableOpacity>
          </View>

          <View style={styles.typeRow}>
            {([["dm", "Личный"], ["group", "Групповой"]] as ["dm" | "group", string][]).map(([t, label]) => (
              <TouchableOpacity
                key={t}
                style={[styles.typeBtn, chatType === t && styles.typeBtnActive]}
                onPress={() => { setChatType(t); setSelectedUsers([]); }}
              >
                <Text style={[styles.typeBtnText, chatType === t && styles.typeBtnTextActive]}>
                  {label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.sectionLabel}>
            {chatType === "dm" ? "Выберите собеседника:" : "Выберите участников:"}
          </Text>

          <ScrollView style={styles.userList}>
            {users.map((u) => {
              const selected = selectedUsers.includes(u.id);
              return (
                <TouchableOpacity
                  key={u.id}
                  style={[styles.userRow, selected && styles.userRowSelected]}
                  onPress={() => toggleUser(u.id)}
                >
                  <Avatar name={u.full_name || u.username || "?"} size={36} />
                  <View style={styles.userInfo}>
                    <Text style={styles.userName}>{u.full_name || u.username || `#${u.id}`}</Text>
                    <Text style={styles.userRole}>{ROLE_LABELS[u.role] || u.role}</Text>
                  </View>
                  {selected && <Ionicons name="checkmark-circle" size={22} color="#1a5c2e" />}
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          <TouchableOpacity
            style={[styles.createBtn, selectedUsers.length === 0 && styles.createBtnDisabled]}
            onPress={handleCreate}
            disabled={selectedUsers.length === 0 || createMutation.isPending}
          >
            {createMutation.isPending ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.createBtnText}>
                Создать чат{selectedUsers.length > 0 ? ` (${selectedUsers.length})` : ""}
              </Text>
            )}
          </TouchableOpacity>
        </View>
      </Modal>
    </View>
  );
}

const ROLE_LABELS: Record<string, string> = {
  admin: "Администратор",
  brigadier: "Бригадир",
  accountant: "Бухгалтер",
  it: "IT",
  tim: "ТИМ",
  user: "Сотрудник",
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  center: { flex: 1 },
  feedBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    marginHorizontal: 12,
    marginTop: 12,
    marginBottom: 4,
    borderRadius: 14,
    padding: 14,
    borderWidth: 1.5,
    borderColor: "#1a5c2e",
    shadowColor: "#1a5c2e",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    elevation: 3,
  },
  feedBannerLeft: { flex: 1, flexDirection: "row", alignItems: "center", gap: 12 },
  feedIconWrap: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: "#1a5c2e", justifyContent: "center", alignItems: "center",
  },
  feedBannerTitle: { fontSize: 15, fontWeight: "700", color: "#1a5c2e" },
  feedPinBadge: {
    backgroundColor: "#e8f5e9", borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2,
  },
  feedPinText: { fontSize: 10, fontWeight: "700", color: "#1a5c2e", textTransform: "uppercase" },
  feedBannerSub: { fontSize: 12, color: "#666", marginTop: 2 },
  roomCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    elevation: 2,
  },
  roomInfo: { flex: 1, marginLeft: 12 },
  roomName: { fontSize: 15, fontWeight: "600", color: "#222" },
  roomLast: { fontSize: 13, color: "#888", marginTop: 2 },
  roomMeta: { alignItems: "flex-end", gap: 2 },
  memberCount: { fontSize: 11, color: "#aaa" },
  fab: {
    position: "absolute",
    right: 20,
    bottom: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "#1a5c2e",
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    elevation: 6,
  },
  modal: { flex: 1, backgroundColor: "#f5f7f5" },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 20,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
  },
  modalTitle: { fontSize: 18, fontWeight: "bold", color: "#222" },
  typeRow: { flexDirection: "row", padding: 16, gap: 10 },
  typeBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    alignItems: "center",
    backgroundColor: "#fff",
    borderWidth: 1.5,
    borderColor: "#ddd",
  },
  typeBtnActive: { borderColor: "#1a5c2e", backgroundColor: "#e8f5e9" },
  typeBtnText: { fontSize: 14, fontWeight: "600", color: "#888" },
  typeBtnTextActive: { color: "#1a5c2e" },
  sectionLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: "#888",
    textTransform: "uppercase",
    paddingHorizontal: 16,
    marginBottom: 8,
  },
  userList: { flex: 1, paddingHorizontal: 12 },
  userRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 12,
    marginBottom: 6,
    borderWidth: 1.5,
    borderColor: "transparent",
  },
  userRowSelected: { borderColor: "#1a5c2e", backgroundColor: "#f0faf3" },
  userInfo: { flex: 1, marginLeft: 12 },
  userName: { fontSize: 15, fontWeight: "600", color: "#222" },
  userRole: { fontSize: 12, color: "#888", marginTop: 1 },
  createBtn: {
    margin: 16,
    backgroundColor: "#1a5c2e",
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
  },
  createBtnDisabled: { backgroundColor: "#b0bdb1" },
  createBtnText: { color: "#fff", fontSize: 16, fontWeight: "bold" },
});
