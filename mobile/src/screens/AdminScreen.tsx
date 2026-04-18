import React, { useState } from "react";
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity,
  ActivityIndicator, RefreshControl, Modal, Alert, ScrollView,
} from "react-native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../api/client";
import Avatar from "../components/Avatar";
import EmptyState from "../components/EmptyState";

interface UserAdmin {
  id: number;
  full_name: string | null;
  username: string | null;
  phone: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

const ROLES = ["user", "brigadier", "accountant", "it", "tim", "admin"] as const;
type Role = typeof ROLES[number];

const ROLE_LABELS: Record<Role, string> = {
  admin: "Администратор",
  brigadier: "Бригадир",
  accountant: "Бухгалтер",
  it: "IT",
  tim: "ТИМ",
  user: "Сотрудник",
};

const ROLE_COLORS: Record<Role, string> = {
  admin: "#c0392b",
  brigadier: "#2d6a4f",
  accountant: "#1b6ca8",
  it: "#6a3d9a",
  tim: "#e67e22",
  user: "#555",
};

export default function AdminScreen() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<UserAdmin | null>(null);

  const { data: users = [], isLoading, refetch, isRefetching } = useQuery<UserAdmin[]>({
    queryKey: ["admin_users"],
    queryFn: () => api.get("/users").then((r) => r.data),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { role?: string; is_active?: boolean; full_name?: string } }) =>
      api.patch(`/users/${id}`, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin_users"] });
      setSelected(null);
    },
    onError: (e: any) => {
      Alert.alert("Ошибка", e?.response?.data?.detail || "Не удалось обновить пользователя");
    },
  });

  const handleRoleChange = (user: UserAdmin, role: Role) => {
    Alert.alert(
      "Изменить роль",
      `Назначить ${user.full_name || user.username} роль "${ROLE_LABELS[role]}"?`,
      [
        { text: "Отмена", style: "cancel" },
        {
          text: "Подтвердить",
          onPress: () => updateMutation.mutate({ id: user.id, data: { role } }),
        },
      ]
    );
  };

  const handleToggleActive = (user: UserAdmin) => {
    const action = user.is_active ? "заблокировать" : "разблокировать";
    Alert.alert(
      `${user.is_active ? "Блокировка" : "Разблокировка"}`,
      `Вы хотите ${action} пользователя ${user.full_name || user.username}?`,
      [
        { text: "Отмена", style: "cancel" },
        {
          text: user.is_active ? "Заблокировать" : "Разблокировать",
          style: user.is_active ? "destructive" : "default",
          onPress: () =>
            updateMutation.mutate({ id: user.id, data: { is_active: !user.is_active } }),
        },
      ]
    );
  };

  const activeCount = users.filter((u) => u.is_active).length;

  return (
    <View style={styles.container}>
      <View style={styles.summaryBar}>
        <View style={styles.summaryItem}>
          <Text style={styles.summaryValue}>{users.length}</Text>
          <Text style={styles.summaryLabel}>Всего</Text>
        </View>
        <View style={styles.summaryDivider} />
        <View style={styles.summaryItem}>
          <Text style={[styles.summaryValue, { color: "#1a5c2e" }]}>{activeCount}</Text>
          <Text style={styles.summaryLabel}>Активных</Text>
        </View>
        <View style={styles.summaryDivider} />
        <View style={styles.summaryItem}>
          <Text style={[styles.summaryValue, { color: "#c0392b" }]}>{users.length - activeCount}</Text>
          <Text style={styles.summaryLabel}>Заблокировано</Text>
        </View>
      </View>

      {isLoading ? (
        <ActivityIndicator style={{ marginTop: 60 }} color="#1a5c2e" size="large" />
      ) : (
        <FlatList
          data={users}
          keyExtractor={(u) => String(u.id)}
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
          contentContainerStyle={{ padding: 12 }}
          ListEmptyComponent={
            <EmptyState icon="people-outline" message="Нет пользователей" />
          }
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[styles.userCard, !item.is_active && styles.userCardInactive]}
              onPress={() => setSelected(item)}
            >
              <View style={styles.userCardLeft}>
                <Avatar name={item.full_name || item.username || "?"} size={44} />
                {!item.is_active && (
                  <View style={styles.blockedBadge}>
                    <Ionicons name="ban" size={12} color="#fff" />
                  </View>
                )}
              </View>
              <View style={styles.userInfo}>
                <Text style={styles.userName}>{item.full_name || item.username || `#${item.id}`}</Text>
                {item.username && item.full_name && (
                  <Text style={styles.userLogin}>@{item.username}</Text>
                )}
                <View style={styles.rolePill}>
                  <Text style={[styles.roleText, { color: ROLE_COLORS[item.role as Role] || "#555" }]}>
                    {ROLE_LABELS[item.role as Role] || item.role}
                  </Text>
                </View>
              </View>
              <Ionicons name="chevron-forward" size={18} color="#ccc" />
            </TouchableOpacity>
          )}
        />
      )}

      <Modal visible={!!selected} animationType="slide" presentationStyle="pageSheet" transparent={false}>
        {selected && (
          <View style={styles.modal}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Управление</Text>
              <TouchableOpacity onPress={() => setSelected(null)}>
                <Ionicons name="close" size={24} color="#333" />
              </TouchableOpacity>
            </View>

            <ScrollView contentContainerStyle={styles.modalContent}>
              <View style={styles.userProfileCard}>
                <Avatar name={selected.full_name || selected.username || "?"} size={64} />
                <View style={{ marginLeft: 16 }}>
                  <Text style={styles.profileName}>{selected.full_name || "—"}</Text>
                  {selected.username && (
                    <Text style={styles.profileLogin}>@{selected.username}</Text>
                  )}
                  {selected.phone && (
                    <Text style={styles.profilePhone}>{selected.phone}</Text>
                  )}
                  <Text style={styles.profileDate}>
                    С {new Date(selected.created_at).toLocaleDateString("ru")}
                  </Text>
                </View>
              </View>

              <Text style={styles.sectionTitle}>Роль</Text>
              <View style={styles.rolesGrid}>
                {ROLES.map((role) => (
                  <TouchableOpacity
                    key={role}
                    style={[
                      styles.roleBtn,
                      selected.role === role && {
                        borderColor: ROLE_COLORS[role],
                        backgroundColor: ROLE_COLORS[role] + "18",
                      },
                    ]}
                    onPress={() => handleRoleChange(selected, role)}
                    disabled={updateMutation.isPending}
                  >
                    <Text
                      style={[
                        styles.roleBtnText,
                        selected.role === role && { color: ROLE_COLORS[role], fontWeight: "bold" },
                      ]}
                    >
                      {ROLE_LABELS[role]}
                    </Text>
                    {selected.role === role && (
                      <Ionicons name="checkmark" size={14} color={ROLE_COLORS[role]} />
                    )}
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={styles.sectionTitle}>Статус</Text>
              <TouchableOpacity
                style={[
                  styles.statusBtn,
                  selected.is_active ? styles.statusBtnBlock : styles.statusBtnUnblock,
                ]}
                onPress={() => handleToggleActive(selected)}
                disabled={updateMutation.isPending}
              >
                {updateMutation.isPending ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <>
                    <Ionicons
                      name={selected.is_active ? "ban-outline" : "checkmark-circle-outline"}
                      size={20}
                      color="#fff"
                    />
                    <Text style={styles.statusBtnText}>
                      {selected.is_active ? "Заблокировать пользователя" : "Разблокировать пользователя"}
                    </Text>
                  </>
                )}
              </TouchableOpacity>
            </ScrollView>
          </View>
        )}
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  summaryBar: {
    flexDirection: "row",
    backgroundColor: "#fff",
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
  },
  summaryItem: { flex: 1, alignItems: "center" },
  summaryValue: { fontSize: 22, fontWeight: "bold", color: "#222" },
  summaryLabel: { fontSize: 11, color: "#888", marginTop: 2 },
  summaryDivider: { width: 1, backgroundColor: "#eee" },
  userCard: {
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
  userCardInactive: { opacity: 0.55 },
  userCardLeft: { position: "relative" },
  blockedBadge: {
    position: "absolute",
    bottom: -2,
    right: -2,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: "#c0392b",
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1.5,
    borderColor: "#fff",
  },
  userInfo: { flex: 1, marginLeft: 12 },
  userName: { fontSize: 15, fontWeight: "600", color: "#222" },
  userLogin: { fontSize: 12, color: "#999", marginTop: 1 },
  rolePill: { marginTop: 4 },
  roleText: { fontSize: 12, fontWeight: "600" },
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
  modalContent: { padding: 16 },
  userProfileCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 20,
    marginBottom: 20,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    elevation: 3,
  },
  profileName: { fontSize: 18, fontWeight: "bold", color: "#222" },
  profileLogin: { fontSize: 13, color: "#888", marginTop: 2 },
  profilePhone: { fontSize: 13, color: "#666", marginTop: 2 },
  profileDate: { fontSize: 12, color: "#aaa", marginTop: 4 },
  sectionTitle: {
    fontSize: 13,
    fontWeight: "bold",
    color: "#888",
    textTransform: "uppercase",
    marginBottom: 10,
    marginTop: 4,
  },
  rolesGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 24,
  },
  roleBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: "#ddd",
    backgroundColor: "#fff",
  },
  roleBtnText: { fontSize: 14, color: "#555" },
  statusBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    borderRadius: 12,
    paddingVertical: 16,
    marginBottom: 20,
  },
  statusBtnBlock: { backgroundColor: "#c0392b" },
  statusBtnUnblock: { backgroundColor: "#1a5c2e" },
  statusBtnText: { color: "#fff", fontSize: 16, fontWeight: "bold" },
});
