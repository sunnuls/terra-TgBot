import React, { useCallback, useState } from "react";
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView, RefreshControl,
} from "react-native";
import { useNavigation, useFocusEffect } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { useAuthStore } from "../store/authStore";
import { reportsApi } from "../api/reports";
import { formsApi } from "../api/forms";
import { chatApi } from "../api/chat";
import { RootStackParamList } from "../navigation";
import { invalidateFormsAndDictionaries } from "../lib/syncDataCaches";

type Nav = NativeStackNavigationProp<RootStackParamList>;

function hasRole(userRole: string | undefined | null, ...roles: string[]): boolean {
  if (!userRole) return false;
  const userRoles = userRole.split(",").map((r) => r.trim());
  return roles.some((r) => userRoles.includes(r));
}

interface MenuItem {
  title: string;
  subtitle: string;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
  onPress: () => void;
}

export default function HomeScreen() {
  const nav = useNavigation<Nav>();
  const qc = useQueryClient();
  const { user, refreshUser } = useAuthStore();
  const [refreshing, setRefreshing] = useState(false);

  /** После правок в веб-админке: свайп вниз или возврат на вкладку «Главная» */
  useFocusEffect(
    useCallback(() => {
      void invalidateFormsAndDictionaries(qc);
      qc.invalidateQueries({ queryKey: ["stats"] });
      // Тихо обновляем данные пользователя (роли) без показа глобального спиннера
      void refreshUser();
    }, [qc, refreshUser])
  );

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await invalidateFormsAndDictionaries(qc);
    } finally {
      setRefreshing(false);
    }
  }, [qc]);

  const { data: statsToday } = useQuery({
    queryKey: ["stats", "today"],
    queryFn: () => reportsApi.getStats("today"),
  });

  const { data: statsWeek } = useQuery({
    queryKey: ["stats", "week"],
    queryFn: () => reportsApi.getStats("week"),
  });

  const { data: forms = [] } = useQuery({
    queryKey: ["forms"],
    queryFn: formsApi.listForms,
  });

  const { data: feedRoom } = useQuery({
    queryKey: ["feed_room"],
    queryFn: chatApi.getFeedRoom,
  });

  const role = user?.role || "user";

  // Format multi-role string into human-readable labels
  const roleLabel = role
    .split(",")
    .map((r) => ROLE_LABELS[r.trim()] ?? r.trim())
    .filter(Boolean)
    .join(", ");

  const FORM_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
    otd: "add-circle-outline",
    brig: "people-outline",
  };
  const FORM_COLORS: Record<string, string> = {
    otd: "#1a5c2e",
    brig: "#2d6a4f",
  };

  const menuItems: MenuItem[] = [];

  // Dynamic forms from API (based on user's role — backend filters automatically)
  forms
    .filter((f) => f.schema?.flow?.nodes?.length)  // only forms with a configured flow
    .forEach((form) => {
      menuItems.push({
        title: form.title,
        subtitle: "Заполнить форму",
        icon: FORM_ICONS[form.name] ?? "clipboard-outline",
        color: FORM_COLORS[form.name] ?? "#40916c",
        onPress: () => nav.navigate("FlowForm", { formName: form.name, title: form.title }),
      });
    });

  // Fallback: if no flow configured yet, keep old hardcoded screens
  if (!forms.some((f) => f.name === "otd" && f.schema?.flow?.nodes?.length)) {
    menuItems.unshift({
      title: "ОТД Отчёт",
      subtitle: "Подать рабочий отчёт",
      icon: "add-circle-outline",
      color: "#1a5c2e",
      onPress: () => nav.navigate("OtdForm"),
    });
  }
  if (
    hasRole(role, "brigadier", "admin") &&
    !forms.some((f) => f.name === "brig" && f.schema?.flow?.nodes?.length)
  ) {
    menuItems.push({
      title: "Отчёт бригадира",
      subtitle: "ОБ — отчёт бригадира",
      icon: "people-outline",
      color: "#2d6a4f",
      onPress: () => nav.navigate("BrigForm"),
    });
  }

  if (hasRole(role, "admin", "it")) {
    menuItems.push({
      title: "Пользователи",
      subtitle: "Управление аккаунтами",
      icon: "shield-outline",
      color: "#c0392b",
      onPress: () => nav.navigate("Admin"),
    });
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={["#1a5c2e"]} />}
    >
      <View style={styles.greeting}>
        <Text style={styles.greetText}>Привет, {user?.full_name?.split(" ")[0] || "—"}!</Text>
        <Text style={styles.roleText}>{roleLabel || role}</Text>
      </View>

      <View style={styles.statsRow}>
        <StatCard
          label="Часов за неделю"
          value={statsWeek ? statsWeek.total_hours.toFixed(1) : "—"}
          sub={statsToday && statsToday.total_hours > 0 ? `${statsToday.total_hours.toFixed(1)} сегодня` : undefined}
        />
        <StatCard
          label="Отчётов за неделю"
          value={statsWeek ? String(statsWeek.report_count) : "—"}
          sub={statsToday && statsToday.report_count > 0 ? `${statsToday.report_count} сегодня` : undefined}
        />
      </View>

      {feedRoom && (
        <TouchableOpacity
          style={styles.feedCard}
          onPress={() => nav.navigate("ChatRoom", { id: feedRoom.id, name: feedRoom.name || "Отчётность" })}
        >
          <View style={styles.feedCardLeft}>
            <Ionicons name="newspaper-outline" size={26} color="#fff" style={{ marginRight: 12 }} />
            <View>
              <Text style={styles.feedCardTitle}>Лента отчётов</Text>
              <Text style={styles.feedCardSub} numberOfLines={1}>
                {feedRoom.last_message || "Все отчёты команды в одном месте"}
              </Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color="rgba(255,255,255,0.7)" />
        </TouchableOpacity>
      )}

      <TouchableOpacity style={styles.fleetCard} onPress={() => nav.navigate("Fleet")} activeOpacity={0.9}>
        <View style={styles.feedCardLeft}>
          <Ionicons name="navigate-outline" size={26} color="#fff" style={{ marginRight: 12 }} />
          <View>
            <Text style={styles.feedCardTitle}>Мониторинг транспорта</Text>
            <Text style={styles.feedCardSub} numberOfLines={2}>
              Карта, объекты, геозоны — отдельный раздел приложения
            </Text>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={18} color="rgba(255,255,255,0.7)" />
      </TouchableOpacity>

      <Text style={styles.sectionTitle}>Действия</Text>
      <View style={styles.grid}>
        {menuItems.map((item, i) => (
          <TouchableOpacity key={i} style={[styles.card, { borderLeftColor: item.color }]} onPress={item.onPress}>
            <Ionicons name={item.icon} size={28} color={item.color} style={styles.cardIcon} />
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>{item.title}</Text>
              <Text style={styles.cardSub}>{item.subtitle}</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#aaa" />
          </TouchableOpacity>
        ))}
      </View>
    </ScrollView>
  );
}

export const ROLE_LABELS: Record<string, string> = {
  admin: "Администратор",
  brigadier: "Бригадир",
  accountant: "Бухгалтер",
  otd: "ОТД",
  it: "IT",
  tim: "ТИМ",
  user: "Сотрудник",
};

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <View style={styles.statCard}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
      {sub ? <Text style={styles.statSub}>{sub}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  greeting: { backgroundColor: "#1a5c2e", padding: 24, paddingBottom: 32 },
  greetText: { fontSize: 22, fontWeight: "bold", color: "#fff" },
  roleText: { fontSize: 14, color: "#a8d5b5", marginTop: 2 },
  statsRow: { flexDirection: "row", padding: 16, gap: 12, marginTop: -20 },
  statCard: {
    flex: 1, backgroundColor: "#fff", borderRadius: 12, padding: 16,
    alignItems: "center",
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, elevation: 3,
  },
  statValue: { fontSize: 26, fontWeight: "bold", color: "#1a5c2e" },
  statLabel: { fontSize: 12, color: "#888", marginTop: 2, textAlign: "center" },
  statSub: { fontSize: 11, color: "#b0c4b8", marginTop: 3, textAlign: "center" },
  feedCard: {
    marginHorizontal: 16,
    marginBottom: 12,
    backgroundColor: "#1a5c2e",
    borderRadius: 14,
    padding: 16,
    flexDirection: "row",
    alignItems: "center",
    shadowColor: "#1a5c2e",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    elevation: 5,
  },
  feedCardLeft: { flex: 1, flexDirection: "row", alignItems: "center" },
  feedCardTitle: { fontSize: 15, fontWeight: "700", color: "#fff" },
  feedCardSub: { fontSize: 12, color: "rgba(255,255,255,0.75)", marginTop: 2 },
  fleetCard: {
    marginHorizontal: 16,
    marginBottom: 12,
    backgroundColor: "#0f766e",
    borderRadius: 14,
    padding: 16,
    flexDirection: "row",
    alignItems: "center",
    shadowColor: "#0f766e",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    elevation: 4,
  },
  sectionTitle: { fontSize: 16, fontWeight: "bold", color: "#333", paddingHorizontal: 16, paddingTop: 8, paddingBottom: 4 },
  grid: { padding: 12 },
  card: {
    flexDirection: "row", alignItems: "center", backgroundColor: "#fff",
    borderRadius: 12, padding: 16, marginBottom: 10,
    borderLeftWidth: 4,
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.06, elevation: 2,
  },
  cardIcon: { marginRight: 14 },
  cardTitle: { fontSize: 15, fontWeight: "600", color: "#222" },
  cardSub: { fontSize: 12, color: "#888", marginTop: 2 },
});
