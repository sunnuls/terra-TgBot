import React, { useState } from "react";
import {
  View, Text, StyleSheet, FlatList, TouchableOpacity, ActivityIndicator, RefreshControl,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useQuery } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { reportsApi, ReportFeedItem } from "../api/reports";
import { RootStackParamList } from "../navigation";
import { useAuthStore } from "../store/authStore";

type Nav = NativeStackNavigationProp<RootStackParamList>;

function hasRole(userRole: string | undefined | null, role: string): boolean {
  if (!userRole) return false;
  return userRole.split(",").map((r) => r.trim()).includes(role);
}

export default function ReportsScreen() {
  const nav = useNavigation<Nav>();
  const user = useAuthStore((s) => s.user);
  const isBrigadier = hasRole(user?.role, "brigadier");
  const [tab, setTab] = useState<"otd" | "brig">("otd");

  const {
    data: reports = [], isLoading, refetch, isRefetching,
  } = useQuery({
    queryKey: ["otd-feed"],
    queryFn: () => reportsApi.listOtdFeed({ limit: 100 }),
  });

  const {
    data: brigReports = [], isLoading: brigLoading, refetch: brigRefetch,
  } = useQuery({
    queryKey: ["brig_reports"],
    queryFn: reportsApi.listBrigReports,
  });

  return (
    <View style={styles.container}>
      <View style={styles.tabs}>
        <TouchableOpacity style={[styles.tab, tab === "otd" && styles.tabActive]} onPress={() => setTab("otd")}>
          <Text style={[styles.tabText, tab === "otd" && styles.tabTextActive]}>ОТД</Text>
        </TouchableOpacity>
        {isBrigadier && (
          <TouchableOpacity style={[styles.tab, tab === "brig" && styles.tabActive]} onPress={() => setTab("brig")}>
            <Text style={[styles.tabText, tab === "brig" && styles.tabTextActive]}>Бригадир</Text>
          </TouchableOpacity>
        )}
      </View>

      {tab === "otd" ? (
        isLoading ? (
          <ActivityIndicator style={styles.center} color="#1a5c2e" size="large" />
        ) : (
          <FlatList
            data={reports}
            keyExtractor={(r: ReportFeedItem) => `${r.source}-${r.id}`}
            refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />}
            contentContainerStyle={{ padding: 12 }}
            ListEmptyComponent={<EmptyState message="Нет отчётов" />}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={styles.card}
                onPress={() => nav.navigate("ReportDetail", { id: item.id, source: item.source })}
              >
                <View style={styles.cardLeft}>
                  <Text style={styles.cardDate}>{item.work_date}</Text>
                  <Text style={styles.cardActivity}>{item.activity || "—"}</Text>
                  <Text style={styles.cardLocation}>{item.location || "—"}</Text>
                  {item.source === "form" && item.form_title ? (
                    <Text style={styles.cardFormTag}>{item.form_title}</Text>
                  ) : null}
                </View>
                <View style={styles.cardRight}>
                  <Text style={styles.cardHours}>{item.hours != null ? `${item.hours} ч` : "—"}</Text>
                  <Text style={styles.cardGrp}>{item.activity_grp === "техника" ? "Техника" : "Ручная"}</Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color="#aaa" />
              </TouchableOpacity>
            )}
          />
        )
      ) : (
        brigLoading ? (
          <ActivityIndicator style={styles.center} color="#1a5c2e" size="large" />
        ) : (
          <FlatList
            data={brigReports}
            keyExtractor={(r) => String(r.id)}
            refreshControl={<RefreshControl refreshing={false} onRefresh={brigRefetch} />}
            contentContainerStyle={{ padding: 12 }}
            ListEmptyComponent={<EmptyState message="Нет отчётов бригадира" />}
            renderItem={({ item }) => (
              <View style={styles.card}>
                <View style={styles.cardLeft}>
                  <Text style={styles.cardDate}>{item.work_date}</Text>
                  <Text style={styles.cardActivity}>{item.work_type}</Text>
                  <Text style={styles.cardLocation}>{item.field}</Text>
                </View>
                <View style={styles.cardRight}>
                  <Text style={styles.cardHours}>{item.workers} чел</Text>
                  <Text style={styles.cardGrp}>{item.shift === "day" ? "День" : "Ночь"}</Text>
                </View>
              </View>
            )}
          />
        )
      )}
    </View>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <View style={{ alignItems: "center", paddingTop: 60 }}>
      <Ionicons name="document-text-outline" size={48} color="#ccc" />
      <Text style={{ color: "#aaa", marginTop: 8, fontSize: 16 }}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  center: { flex: 1 },
  tabs: { flexDirection: "row", backgroundColor: "#fff", borderBottomWidth: 1, borderBottomColor: "#eee" },
  tab: { flex: 1, paddingVertical: 14, alignItems: "center" },
  tabActive: { borderBottomWidth: 2, borderBottomColor: "#1a5c2e" },
  tabText: { fontSize: 14, color: "#888", fontWeight: "600" },
  tabTextActive: { color: "#1a5c2e" },
  card: {
    flexDirection: "row", alignItems: "center", backgroundColor: "#fff",
    borderRadius: 12, padding: 16, marginBottom: 8,
    shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, elevation: 2,
  },
  cardLeft: { flex: 1 },
  cardDate: { fontSize: 12, color: "#888" },
  cardActivity: { fontSize: 15, fontWeight: "600", color: "#222", marginTop: 2 },
  cardLocation: { fontSize: 13, color: "#666", marginTop: 1 },
  cardFormTag: { fontSize: 11, color: "#1a5c2e", marginTop: 4 },
  cardRight: { alignItems: "flex-end", marginRight: 8 },
  cardHours: { fontSize: 18, fontWeight: "bold", color: "#1a5c2e" },
  cardGrp: { fontSize: 11, color: "#888", marginTop: 2 },
});
