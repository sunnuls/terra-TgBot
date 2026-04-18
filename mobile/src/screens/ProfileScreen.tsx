import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
  ScrollView,
  Modal,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useAuthStore } from "../store/authStore";
import { api } from "../api/client";
import { authApi } from "../api/auth";

const ROLE_LABELS: Record<string, string> = {
  admin: "Администратор",
  brigadier: "Бригадир",
  accountant: "Бухгалтер",
  it: "IT",
  tim: "ТИМ",
  user: "Сотрудник",
};

export default function ProfileScreen() {
  const { user, logout, loadUser } = useAuthStore();
  const [editName, setEditName] = useState(false);
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [changePw, setChangePw] = useState(false);
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [savingName, setSavingName] = useState(false);
  const [logoutModalVisible, setLogoutModalVisible] = useState(false);

  const handleSaveName = async () => {
    if (!fullName.trim()) return;
    setSavingName(true);
    try {
      await api.patch("/users/me", { full_name: fullName.trim() });
      await loadUser();
      setEditName(false);
    } catch {
      Alert.alert("Ошибка", "Не удалось сохранить имя");
    } finally {
      setSavingName(false);
    }
  };

  const handleChangePw = async () => {
    if (!oldPw || !newPw || newPw.length < 6) {
      Alert.alert("Ошибка", "Новый пароль минимум 6 символов");
      return;
    }
    try {
      await authApi.changePassword(oldPw, newPw);
      Alert.alert("Готово", "Пароль изменён");
      setChangePw(false);
      setOldPw(""); setNewPw("");
    } catch (e: any) {
      Alert.alert("Ошибка", e?.response?.data?.detail || "Неверный текущий пароль");
    }
  };

  const handleConfirmLogout = () => {
    setLogoutModalVisible(false);
    void logout();
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>{(user?.full_name || "?")[0].toUpperCase()}</Text>
      </View>

      <Text style={styles.name}>{user?.full_name || "—"}</Text>
      <View style={styles.roleBadge}>
        <Text style={styles.roleText}>{ROLE_LABELS[user?.role || "user"]}</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Данные профиля</Text>

        <View style={styles.infoRow}>
          <Ionicons name="person-outline" size={18} color="#888" />
          <Text style={styles.infoLabel}>Имя:</Text>
          {editName ? (
            <TextInput style={styles.inlineInput} value={fullName} onChangeText={setFullName} autoFocus />
          ) : (
            <Text style={styles.infoValue}>{user?.full_name || "—"}</Text>
          )}
          {editName ? (
            <TouchableOpacity onPress={handleSaveName} disabled={savingName}>
              {savingName ? <ActivityIndicator size="small" color="#1a5c2e" /> : <Ionicons name="checkmark" size={20} color="#1a5c2e" />}
            </TouchableOpacity>
          ) : (
            <TouchableOpacity onPress={() => { setFullName(user?.full_name || ""); setEditName(true); }}>
              <Ionicons name="pencil-outline" size={18} color="#aaa" />
            </TouchableOpacity>
          )}
        </View>

        <View style={styles.infoRow}>
          <Ionicons name="phone-portrait-outline" size={18} color="#888" />
          <Text style={styles.infoLabel}>Телефон:</Text>
          <Text style={styles.infoValue}>{user?.phone || "—"}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Безопасность</Text>
        {!changePw ? (
          <TouchableOpacity style={styles.actionBtn} onPress={() => setChangePw(true)}>
            <Ionicons name="lock-closed-outline" size={18} color="#1a5c2e" />
            <Text style={styles.actionBtnText}>Сменить пароль</Text>
          </TouchableOpacity>
        ) : (
          <View>
            <TextInput style={styles.input} placeholder="Текущий пароль" secureTextEntry value={oldPw} onChangeText={setOldPw} />
            <TextInput style={styles.input} placeholder="Новый пароль (мин. 6 символов)" secureTextEntry value={newPw} onChangeText={setNewPw} />
            <View style={{ flexDirection: "row", gap: 10 }}>
              <TouchableOpacity style={[styles.btn, { flex: 1, backgroundColor: "#eee" }]} onPress={() => setChangePw(false)}>
                <Text style={[styles.btnText, { color: "#555" }]}>Отмена</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.btn, { flex: 2 }]} onPress={handleChangePw}>
                <Text style={styles.btnText}>Сохранить</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
      </View>

      <TouchableOpacity
        style={styles.logoutBtn}
        onPress={() => setLogoutModalVisible(true)}
        accessibilityRole="button"
        accessibilityLabel="Выйти из аккаунта"
      >
        <Ionicons name="log-out-outline" size={20} color="#c0392b" />
        <Text style={styles.logoutText}>Выйти</Text>
      </TouchableOpacity>

      <Modal
        visible={logoutModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setLogoutModalVisible(false)}
      >
        <View style={styles.logoutModalOverlay}>
          <View style={styles.logoutModalCard}>
            <Text style={styles.logoutModalTitle}>Выйти?</Text>
            <Text style={styles.logoutModalHint}>Вы уверены, что хотите выйти?</Text>
            <View style={styles.logoutModalActions}>
              <TouchableOpacity
                style={[styles.logoutModalBtn, styles.logoutModalBtnCancel]}
                onPress={() => setLogoutModalVisible(false)}
              >
                <Text style={styles.logoutModalBtnCancelText}>Отмена</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.logoutModalBtn, styles.logoutModalBtnDanger]}
                onPress={handleConfirmLogout}
              >
                <Text style={styles.logoutModalBtnDangerText}>Выйти</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  content: { alignItems: "center", padding: 24 },
  avatar: { width: 80, height: 80, borderRadius: 40, backgroundColor: "#1a5c2e", justifyContent: "center", alignItems: "center", marginBottom: 12 },
  avatarText: { fontSize: 32, fontWeight: "bold", color: "#fff" },
  name: { fontSize: 22, fontWeight: "bold", color: "#222" },
  roleBadge: { backgroundColor: "#e8f5e9", borderRadius: 20, paddingHorizontal: 16, paddingVertical: 4, marginTop: 6, marginBottom: 24 },
  roleText: { color: "#1a5c2e", fontWeight: "600", fontSize: 13 },
  section: { width: "100%", backgroundColor: "#fff", borderRadius: 16, padding: 20, marginBottom: 16, shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, elevation: 2 },
  sectionTitle: { fontSize: 13, fontWeight: "bold", color: "#888", textTransform: "uppercase", marginBottom: 12 },
  infoRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#f5f5f5" },
  infoLabel: { fontSize: 14, color: "#888", width: 80 },
  infoValue: { flex: 1, fontSize: 14, color: "#222" },
  inlineInput: { flex: 1, fontSize: 14, borderBottomWidth: 1, borderBottomColor: "#1a5c2e", paddingBottom: 2 },
  actionBtn: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 12 },
  actionBtnText: { fontSize: 15, color: "#1a5c2e", fontWeight: "600" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 10, padding: 12, marginBottom: 10, fontSize: 15 },
  btn: { backgroundColor: "#1a5c2e", borderRadius: 10, padding: 14, alignItems: "center" },
  btnText: { color: "#fff", fontWeight: "bold" },
  logoutBtn: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 8, paddingVertical: 12, paddingHorizontal: 8 },
  logoutText: { color: "#c0392b", fontSize: 16, fontWeight: "600" },
  logoutModalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.45)",
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  logoutModalCard: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 20,
    width: "100%",
    maxWidth: 340,
  },
  logoutModalTitle: { fontSize: 18, fontWeight: "bold", color: "#222", marginBottom: 8 },
  logoutModalHint: { fontSize: 15, color: "#666", marginBottom: 20 },
  logoutModalActions: { flexDirection: "row", gap: 12 },
  logoutModalBtn: { flex: 1, paddingVertical: 14, borderRadius: 10, alignItems: "center" },
  logoutModalBtnCancel: { backgroundColor: "#eee" },
  logoutModalBtnCancelText: { fontSize: 16, fontWeight: "600", color: "#555" },
  logoutModalBtnDanger: { backgroundColor: "#c0392b" },
  logoutModalBtnDangerText: { fontSize: 16, fontWeight: "600", color: "#fff" },
});
