import React, { useState } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  Alert, ActivityIndicator, TextInput,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reportsApi } from "../api/reports";
import { format } from "date-fns";
import DatePicker from "../components/DatePicker";

export default function BrigFormScreen() {
  const nav = useNavigation();
  const qc = useQueryClient();

  const [form, setForm] = useState({
    work_date: format(new Date(), "yyyy-MM-dd"),
    work_type: "",
    field: "",
    shift: "day",
    rows: "",
    bags: "",
    workers: "",
  });

  const mutation = useMutation({
    mutationFn: reportsApi.createBrigReport,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["brig_reports"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      Alert.alert("Готово", "Отчёт бригадира сохранён.", [
        { text: "OK", onPress: () => nav.goBack() },
      ]);
    },
    onError: (e: any) => {
      Alert.alert("Ошибка", e?.response?.data?.detail || "Ошибка сохранения");
    },
  });

  const handleSubmit = () => {
    if (!form.work_type || !form.field || !form.rows || !form.bags || !form.workers) {
      Alert.alert("Заполните все поля");
      return;
    }
    mutation.mutate({
      work_date: form.work_date,
      work_type: form.work_type,
      field: form.field,
      shift: form.shift,
      rows: parseInt(form.rows),
      bags: parseInt(form.bags),
      workers: parseInt(form.workers),
    });
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.card}>
        <Text style={styles.title}>Отчёт бригадира</Text>

        <Label>Дата</Label>
        <DatePicker
          value={form.work_date}
          onChange={(v) => setForm({ ...form, work_date: v })}
        />

        <Label>Вид работы (культура)</Label>
        <TextInput
          style={styles.input}
          value={form.work_type}
          onChangeText={(v) => setForm({ ...form, work_type: v })}
          placeholder="Пшеница, кукуруза..."
        />

        <Label>Поле</Label>
        <TextInput
          style={styles.input}
          value={form.field}
          onChangeText={(v) => setForm({ ...form, field: v })}
          placeholder="Название поля"
        />

        <Label>Смена</Label>
        <View style={styles.shiftRow}>
          {([["day", "☀️ День"], ["night", "🌙 Ночь"]] as [string, string][]).map(([val, label]) => (
            <TouchableOpacity
              key={val}
              style={[styles.shiftBtn, form.shift === val && styles.shiftBtnActive]}
              onPress={() => setForm({ ...form, shift: val })}
            >
              <Text style={[styles.shiftBtnText, form.shift === val && styles.shiftBtnTextActive]}>
                {label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Label>Рядов</Label>
        <TextInput
          style={styles.input}
          value={form.rows}
          onChangeText={(v) => setForm({ ...form, rows: v })}
          keyboardType="numeric"
          placeholder="0"
        />

        <Label>Мешков</Label>
        <TextInput
          style={styles.input}
          value={form.bags}
          onChangeText={(v) => setForm({ ...form, bags: v })}
          keyboardType="numeric"
          placeholder="0"
        />

        <Label>Рабочих</Label>
        <TextInput
          style={styles.input}
          value={form.workers}
          onChangeText={(v) => setForm({ ...form, workers: v })}
          keyboardType="numeric"
          placeholder="0"
        />

        <TouchableOpacity
          style={styles.submitBtn}
          onPress={handleSubmit}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.submitText}>Отправить отчёт</Text>
          )}
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <Text style={styles.label}>{children}</Text>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  content: { padding: 16 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 20,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    elevation: 3,
  },
  title: { fontSize: 20, fontWeight: "bold", color: "#1a5c2e", marginBottom: 4 },
  label: {
    fontSize: 13,
    color: "#888",
    marginBottom: 4,
    marginTop: 12,
    textTransform: "uppercase",
    fontWeight: "600",
  },
  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    backgroundColor: "#fafafa",
  },
  shiftRow: { flexDirection: "row", gap: 10 },
  shiftBtn: {
    flex: 1,
    padding: 14,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: "#ddd",
    alignItems: "center",
  },
  shiftBtnActive: { borderColor: "#1a5c2e", backgroundColor: "#e8f5e9" },
  shiftBtnText: { fontSize: 14, color: "#555" },
  shiftBtnTextActive: { color: "#1a5c2e", fontWeight: "bold" },
  submitBtn: {
    backgroundColor: "#1a5c2e",
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 24,
  },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "bold" },
});
