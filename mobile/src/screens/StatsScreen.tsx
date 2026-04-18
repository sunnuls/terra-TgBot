import React, { useState } from "react";
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { reportsApi } from "../api/reports";

type Period = "today" | "week" | "month";

export default function StatsScreen() {
  const [period, setPeriod] = useState<Period>("week");

  const { data, isLoading } = useQuery({
    queryKey: ["stats", period],
    queryFn: () => reportsApi.getStats(period),
  });

  const PERIOD_LABELS: Record<Period, string> = {
    today: "Сегодня",
    week: "Неделя",
    month: "Месяц",
  };

  return (
    <View style={styles.container}>
      <View style={styles.periodRow}>
        {(["today", "week", "month"] as Period[]).map((p) => (
          <TouchableOpacity key={p} style={[styles.periodBtn, period === p && styles.periodBtnActive]} onPress={() => setPeriod(p)}>
            <Text style={[styles.periodText, period === p && styles.periodTextActive]}>{PERIOD_LABELS[p]}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {isLoading ? (
        <ActivityIndicator style={{ marginTop: 60 }} color="#1a5c2e" size="large" />
      ) : data ? (
        <View style={styles.statsGrid}>
          <StatCard value={data.total_hours.toFixed(1)} unit="ч" label="Всего часов" color="#1a5c2e" />
          <StatCard value={String(data.report_count)} unit="шт" label="Отчётов" color="#2d6a4f" />
          <StatCard value={String(data.days_worked)} unit="дн" label="Рабочих дней" color="#40916c" />
          <StatCard
            value={data.days_worked > 0 ? (data.total_hours / data.days_worked).toFixed(1) : "0"}
            unit="ч/д"
            label="Среднее в день"
            color="#52b788"
          />
        </View>
      ) : null}
    </View>
  );
}

function StatCard({ value, unit, label, color }: { value: string; unit: string; label: string; color: string }) {
  return (
    <View style={[styles.statCard, { borderTopColor: color }]}>
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={[styles.statUnit, { color }]}>{unit}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  periodRow: { flexDirection: "row", padding: 16, gap: 10 },
  periodBtn: { flex: 1, paddingVertical: 10, borderRadius: 10, alignItems: "center", backgroundColor: "#fff", borderWidth: 1.5, borderColor: "#ddd" },
  periodBtnActive: { borderColor: "#1a5c2e", backgroundColor: "#e8f5e9" },
  periodText: { fontSize: 13, fontWeight: "600", color: "#888" },
  periodTextActive: { color: "#1a5c2e" },
  statsGrid: { flexDirection: "row", flexWrap: "wrap", padding: 8, gap: 12 },
  statCard: {
    width: "46%", backgroundColor: "#fff", borderRadius: 14, padding: 20,
    alignItems: "center", borderTopWidth: 4,
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, elevation: 3,
    marginHorizontal: "2%",
  },
  statValue: { fontSize: 34, fontWeight: "bold" },
  statUnit: { fontSize: 14, fontWeight: "600", marginTop: -4 },
  statLabel: { fontSize: 12, color: "#888", marginTop: 4, textAlign: "center" },
});
