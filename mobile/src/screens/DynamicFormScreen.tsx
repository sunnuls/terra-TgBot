import React, { useState, useEffect } from "react";
import {
  View, Text, StyleSheet, ScrollView, TextInput, TouchableOpacity,
  Alert, ActivityIndicator,
} from "react-native";
import { useRoute, useNavigation, RouteProp } from "@react-navigation/native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formsApi, FormField } from "../api/forms";
import { reportsApi } from "../api/reports";
import { RootStackParamList } from "../navigation";
import { format } from "date-fns";

type Route = RouteProp<RootStackParamList, "DynamicForm">;

export default function DynamicFormScreen() {
  const route = useRoute<Route>();
  const nav = useNavigation();
  const qc = useQueryClient();
  const [values, setValues] = useState<Record<string, unknown>>({});

  const { data: form, isLoading } = useQuery({
    queryKey: ["form", route.params.formId],
    queryFn: () => formsApi.getForm(route.params.formId),
  });

  useEffect(() => {
    if (!form) return;
    const defaults: Record<string, unknown> = {};
    form.schema.fields.forEach((field) => {
      if (field.type === "date") defaults[field.id] = format(new Date(), "yyyy-MM-dd");
      if (field.type === "number") defaults[field.id] = "";
      if (field.type === "text") defaults[field.id] = "";
    });
    setValues(defaults);
  }, [form]);

  const { data: dicts } = useQuery({
    queryKey: ["dictionaries"],
    queryFn: reportsApi.getDictionaries,
  });

  const mutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => reportsApi.submitFormResponse(route.params.formId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["form-responses"] });
      Alert.alert("Отправлено!", "Форма успешно заполнена.", [
        { text: "OK", onPress: () => nav.goBack() },
      ]);
    },
    onError: (e: any) => Alert.alert("Ошибка", e?.response?.data?.detail || "Не удалось отправить"),
  });

  const handleSubmit = () => {
    if (!form) return;
    const missing = form.schema.fields.filter((f) => f.required && !values[f.id]);
    if (missing.length > 0) {
      Alert.alert("Заполните обязательные поля", missing.map((f) => f.label).join(", "));
      return;
    }
    mutation.mutate(values);
  };

  const setField = (id: string, value: unknown) => setValues((prev) => ({ ...prev, [id]: value }));

  if (isLoading || !form) {
    return <ActivityIndicator style={{ flex: 1 }} color="#1a5c2e" size="large" />;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.card}>
        <Text style={styles.formTitle}>{form.title}</Text>

        {form.schema.fields.map((field) => (
          <View key={field.id} style={styles.fieldGroup}>
            <Text style={styles.label}>
              {field.label} {field.required && <Text style={styles.required}>*</Text>}
            </Text>
            <FieldRenderer field={field} value={values[field.id]} onChange={(v) => setField(field.id, v)} dicts={dicts} />
          </View>
        ))}

        <TouchableOpacity style={styles.submitBtn} onPress={handleSubmit} disabled={mutation.isPending}>
          {mutation.isPending ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.submitText}>Отправить форму</Text>
          )}
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

function FieldRenderer({
  field, value, onChange, dicts,
}: {
  field: FormField;
  value: unknown;
  onChange: (v: unknown) => void;
  dicts: any;
}) {
  switch (field.type) {
    case "text":
      return (
        <TextInput
          style={styles.input}
          value={String(value || "")}
          onChangeText={onChange}
          placeholder={field.placeholder || ""}
        />
      );

    case "number":
      return (
        <TextInput
          style={styles.input}
          value={String(value || "")}
          onChangeText={(v) => onChange(v)}
          keyboardType="numeric"
          placeholder={field.placeholder || "0"}
        />
      );

    case "date":
      return (
        <TextInput
          style={styles.input}
          value={String(value || "")}
          onChangeText={onChange}
          placeholder="ГГГГ-ММ-ДД"
        />
      );

    case "select_one": {
      let options: string[] = field.options || [];
      if (field.source === "activities") options = dicts?.activities.map((a: any) => a.name) || [];
      if (field.source === "locations") options = dicts?.locations.map((l: any) => l.name) || [];
      if (field.source === "crops") options = dicts?.crops.map((c: any) => c.name) || [];
      return (
        <View>
          {options.map((opt) => (
            <TouchableOpacity
              key={opt}
              style={[styles.optBtn, value === opt && styles.optBtnActive]}
              onPress={() => onChange(opt)}
            >
              <Text style={[styles.optText, value === opt && styles.optTextActive]}>{opt}</Text>
            </TouchableOpacity>
          ))}
        </View>
      );
    }

    case "select_many": {
      const selected: string[] = Array.isArray(value) ? (value as string[]) : [];
      const options: string[] = field.options || [];
      return (
        <View>
          {options.map((opt) => (
            <TouchableOpacity
              key={opt}
              style={[styles.optBtn, selected.includes(opt) && styles.optBtnActive]}
              onPress={() => {
                if (selected.includes(opt)) onChange(selected.filter((s) => s !== opt));
                else onChange([...selected, opt]);
              }}
            >
              <Text style={[styles.optText, selected.includes(opt) && styles.optTextActive]}>{opt}</Text>
            </TouchableOpacity>
          ))}
        </View>
      );
    }

    default:
      return <TextInput style={styles.input} value={String(value || "")} onChangeText={onChange} />;
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  content: { padding: 16 },
  card: { backgroundColor: "#fff", borderRadius: 16, padding: 20, shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, elevation: 3 },
  formTitle: { fontSize: 20, fontWeight: "bold", color: "#1a5c2e", marginBottom: 20 },
  fieldGroup: { marginBottom: 16 },
  label: { fontSize: 13, color: "#888", fontWeight: "600", textTransform: "uppercase", marginBottom: 6 },
  required: { color: "#e74c3c" },
  input: { borderWidth: 1, borderColor: "#ddd", borderRadius: 10, padding: 14, fontSize: 15, backgroundColor: "#fafafa" },
  optBtn: { padding: 12, borderRadius: 10, borderWidth: 1.5, borderColor: "#ddd", marginBottom: 6, backgroundColor: "#fafafa" },
  optBtnActive: { borderColor: "#1a5c2e", backgroundColor: "#e8f5e9" },
  optText: { fontSize: 14, color: "#555", textAlign: "center" },
  optTextActive: { color: "#1a5c2e", fontWeight: "bold" },
  submitBtn: { backgroundColor: "#1a5c2e", borderRadius: 12, paddingVertical: 16, alignItems: "center", marginTop: 8 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "bold" },
});
