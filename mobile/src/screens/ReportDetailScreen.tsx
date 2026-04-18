import React, { useMemo } from "react";
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Alert, ActivityIndicator, Platform } from "react-native";
import { useRoute, useNavigation, RouteProp, NavigationProp } from "@react-navigation/native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { reportsApi } from "../api/reports";
import { formsApi } from "../api/forms";
import { RootStackParamList } from "../navigation";

function webConfirm(message: string): boolean {
  if (Platform.OS === "web" && typeof window !== "undefined") return window.confirm(message);
  return true;
}
function webAlert(title: string, message?: string) {
  if (Platform.OS === "web" && typeof window !== "undefined") {
    window.alert(message ? `${title}\n\n${message}` : title);
  } else {
    Alert.alert(title, message);
  }
}

type Route = RouteProp<RootStackParamList, "ReportDetail">;

const FORM_FIELD_LABELS: Record<string, string> = {
  date: "Дата работы",
  work_date: "Дата работы",
  hours: "Часы",
  work_type: "Тип работ",
  machine_type: "Тип техники",
  activity_tech: "Деятельность",
  activity_hand: "Деятельность",
  location: "Место / поле",
  crop: "Культура",
};

export default function ReportDetailScreen() {
  const route = useRoute<Route>();
  const nav = useNavigation<NavigationProp<RootStackParamList>>();
  const qc = useQueryClient();
  const id = route.params.id;
  const source = route.params.source ?? "otd";

  const { data: report, isLoading } = useQuery({
    queryKey: ["report", id, source],
    queryFn: () =>
      source === "form" ? reportsApi.getFormResponse(id) : reportsApi.getReport(id),
    enabled: source === "form" || source === "otd",
  });

  // Загружаем схему формы для получения лейблов нод (step_xxx)
  const formId = source === "form" && report && "form_id" in report
    ? (report as { form_id: number }).form_id
    : undefined;

  const { data: formTemplate } = useQuery({
    queryKey: ["form", formId],
    queryFn: () => formsApi.getForm(formId!),
    enabled: formId != null,
  });

  const nodeMap = useMemo(() => {
    const flow = formTemplate?.schema?.flow;
    if (!flow?.nodes) return {} as Record<string, { label: string }>;
    return Object.fromEntries(flow.nodes.map((n: { id: string; label: string }) => [n.id, n]));
  }, [formTemplate]);

  const deleteMutation = useMutation({
    mutationFn: () =>
      source === "form" ? reportsApi.deleteFormResponse(id) : reportsApi.deleteReport(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["otd-feed"] });
      qc.invalidateQueries({ queryKey: ["reports"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      nav.goBack();
    },
    onError: (e: any) => webAlert("Ошибка", e?.response?.data?.detail || "Не удалось удалить"),
  });

  const formRows = useMemo(() => {
    if (source !== "form" || !report || !("data" in report)) return [];
    const data = (report as { data: Record<string, string> }).data || {};
    const hasWorkDate = "work_date" in data;
    const rows: [string, string][] = [];

    for (const [k, v] of Object.entries(data)) {
      // Убираем дублирующуюся дату: если есть work_date — пропускаем date
      if (k === "date" && hasWorkDate) continue;

      // Пропускаем пустые поля деятельности (показываем только ту, у которой есть значение)
      if ((k === "activity_tech" || k === "activity_hand") && !v) continue;

      // step_xxx — берём лейбл из схемы формы
      if (k.startsWith("step_")) {
        const node = nodeMap[k];
        rows.push([node?.label ?? k, String(v)]);
        continue;
      }

      // __sub_xxx — подполя техники
      if (k.startsWith("__sub_")) {
        rows.push(["Техника (уточнение)", String(v)]);
        continue;
      }

      rows.push([FORM_FIELD_LABELS[k] ?? k, String(v)]);
    }

    return rows;
  }, [source, report, nodeMap]);

  if (isLoading) return <ActivityIndicator style={{ flex: 1 }} color="#1a5c2e" size="large" />;
  if (!report) return null;

  const handleDelete = () => {
    if (Platform.OS === "web") {
      if (webConfirm("Удалить отчёт?\n\nЭто действие нельзя отменить.")) {
        deleteMutation.mutate();
      }
    } else {
      Alert.alert("Удалить отчёт?", "Это действие нельзя отменить.", [
        { text: "Отмена", style: "cancel" },
        { text: "Удалить", style: "destructive", onPress: () => deleteMutation.mutate() },
      ]);
    }
  };

  const handleEdit = (r: import("../api/reports").Report) => {
    nav.navigate("EditReport", { id: r.id, report: r });
  };

  const handleEditForm = (fr: import("../api/reports").FormResponse) => {
    nav.navigate("EditFormResponse", { id: fr.id, formResponse: fr });
  };

  if (source === "form") {
    const fr = report as import("../api/reports").FormResponse;
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Ionicons name="document-text" size={32} color="#1a5c2e" />
          <Text style={styles.title}>Отчёт (форма) #{fr.id}</Text>
        </View>

        <View style={styles.card}>
          {[
            ["Отправлен", new Date(fr.submitted_at).toLocaleString("ru")],
            ...formRows,
          ].map(([label, value], idx) => (
            <View key={`${label}-${idx}`} style={styles.row}>
              <Text style={styles.rowLabel}>{label}</Text>
              <Text style={styles.rowValue}>{value || "—"}</Text>
            </View>
          ))}
        </View>

        <View style={styles.actionRow}>
          <TouchableOpacity style={styles.editBtn} onPress={() => handleEditForm(fr)}>
            <Ionicons name="pencil-outline" size={18} color="#fff" />
            <Text style={styles.actionBtnText}>Изменить</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.deleteBtn} onPress={handleDelete} disabled={deleteMutation.isPending}>
            {deleteMutation.isPending ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Ionicons name="trash-outline" size={18} color="#fff" />
                <Text style={styles.actionBtnText}>Удалить</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </ScrollView>
    );
  }

  const r = report as import("../api/reports").Report;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Ionicons name="document-text" size={32} color="#1a5c2e" />
        <Text style={styles.title}>Отчёт ОТД #{r.id}</Text>
      </View>

      <View style={styles.card}>
        {[
          ["Дата", r.work_date],
          ["Часы", r.hours != null ? `${r.hours} ч` : "—"],
          ["Тип работ", r.activity_grp === "техника" ? "Техника" : "Ручная"],
          ["Деятельность", r.activity],
          ["Техника", r.machine_type ? `${r.machine_type}${r.machine_name ? ` — ${r.machine_name}` : ""}` : "—"],
          ["Место", r.location],
          ["Культура", r.crop || "—"],
          ["Создан", new Date(r.created_at).toLocaleString("ru")],
        ].map(([label, value]) => (
          <View key={label} style={styles.row}>
            <Text style={styles.rowLabel}>{label}</Text>
            <Text style={styles.rowValue}>{value || "—"}</Text>
          </View>
        ))}
      </View>

      <View style={styles.actionRow}>
        <TouchableOpacity style={styles.editBtn} onPress={() => handleEdit(r)}>
          <Ionicons name="pencil-outline" size={18} color="#fff" />
          <Text style={styles.actionBtnText}>Изменить</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.deleteBtn} onPress={handleDelete} disabled={deleteMutation.isPending}>
          {deleteMutation.isPending ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <>
              <Ionicons name="trash-outline" size={18} color="#fff" />
              <Text style={styles.actionBtnText}>Удалить</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  content: { padding: 16 },
  header: { flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 16 },
  title: { fontSize: 20, fontWeight: "bold", color: "#1a5c2e" },
  card: { backgroundColor: "#fff", borderRadius: 16, padding: 20, shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, elevation: 3 },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: "#f5f5f5" },
  rowLabel: { fontSize: 14, color: "#888" },
  rowValue: { fontSize: 14, fontWeight: "600", color: "#222", maxWidth: "60%", textAlign: "right" },
  actionRow: { flexDirection: "row", gap: 12, marginTop: 20 },
  editBtn: { flex: 1, flexDirection: "row", gap: 8, backgroundColor: "#1a5c2e", borderRadius: 12, padding: 16, alignItems: "center", justifyContent: "center" },
  deleteBtn: { flex: 1, flexDirection: "row", gap: 8, backgroundColor: "#c0392b", borderRadius: 12, padding: 16, alignItems: "center", justifyContent: "center" },
  actionBtnText: { color: "#fff", fontWeight: "bold", fontSize: 15 },
  deleteBtnText: { color: "#fff", fontWeight: "bold", fontSize: 15 },
  hint: { fontSize: 13, color: "#888", marginTop: 16, textAlign: "center" },
});
