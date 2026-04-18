import React, { useState, useMemo } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, TextInput, Modal, FlatList, Platform, Alert,
} from "react-native";
import { useNavigation, useRoute, RouteProp } from "@react-navigation/native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { reportsApi, Dictionaries } from "../api/reports";
import { formsApi, FlowNode } from "../api/forms";
import { RootStackParamList } from "../navigation";
import DatePicker from "../components/DatePicker";

/** Возвращает опции выбора для ноды флоу по её source */
function getStepOptions(node: FlowNode, dicts: Dictionaries | undefined, fields: Record<string, string>): string[] {
  if (node.options && node.options.length > 0) return node.options;
  if (!node.source || !dicts) return [];
  const src = node.source;
  if (src.startsWith("machine_items:")) {
    const kindName = src.replace("machine_items:", "");
    const kind = dicts.machine_kinds.find((k) => k.title === kindName);
    return kind ? dicts.machine_items.filter((i) => i.kind_id === kind.id).map((i) => i.name) : [];
  }
  switch (src) {
    case "machine_kinds":      return dicts.machine_kinds.map((k) => k.title);
    case "machine_items": {
      const selKind = Object.values(fields).find((v) => dicts.machine_kinds.some((k) => k.title === v));
      const kind = dicts.machine_kinds.find((k) => k.title === selKind);
      return kind ? dicts.machine_items.filter((i) => i.kind_id === kind.id).map((i) => i.name) : dicts.machine_items.map((i) => i.name);
    }
    case "activities_tech":    return dicts.activities.filter((a) => a.grp === "техника").map((a) => a.name);
    case "activities_hand":    return dicts.activities.filter((a) => a.grp === "ручная").map((a) => a.name);
    case "locations":          return dicts.locations.map((l) => l.name);
    case "locations_field":    return dicts.locations.filter((l) => l.grp === "поля").map((l) => l.name);
    case "locations_store":    return dicts.locations.filter((l) => l.grp === "склад").map((l) => l.name);
    case "crops":              return dicts.crops.map((c) => c.name);
    default: {
      if (src.startsWith("custom:")) {
        const dictId = parseInt(src.replace("custom:", ""), 10);
        const cd = (dicts.custom_dicts ?? []).find((d) => d.id === dictId);
        return cd ? cd.items.map((i) => i.value) : [];
      }
      return [];
    }
  }
}

/** Normalize date value to YYYY-MM-DD (strips time, converts DD.MM.YYYY) */
function normDate(v: string): string {
  if (!v) return v;
  if (v.includes("T")) return v.split("T")[0];
  const dot = v.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (dot) return `${dot[3]}-${dot[2]}-${dot[1]}`;
  return v;
}

type Route = RouteProp<RootStackParamList, "EditFormResponse">;

function showAlert(title: string, message?: string) {
  if (Platform.OS === "web" && typeof window !== "undefined") {
    window.alert(message ? `${title}\n\n${message}` : title);
  } else {
    Alert.alert(title, message);
  }
}

const FIELD_LABELS: Record<string, string> = {
  date: "Дата работы",
  work_date: "Дата работы",
  hours: "Часы",
  work_type: "Тип работ",
  machine_type: "Тип техники",
  activity_tech: "Деятельность (техника)",
  activity_hand: "Деятельность (ручная)",
  location: "Место / поле",
  crop: "Культура",
};

// ─── PickerModal ─────────────────────────────────────────────────────────────
function PickerModal({
  visible, title, options, value, onSelect, onClose,
}: {
  visible: boolean;
  title: string;
  options: string[];
  value: string;
  onSelect: (v: string) => void;
  onClose: () => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          <View style={styles.sheetHeader}>
            <Text style={styles.sheetTitle}>{title}</Text>
            <TouchableOpacity onPress={onClose}>
              <Ionicons name="close" size={24} color="#444" />
            </TouchableOpacity>
          </View>
          <FlatList
            data={options}
            keyExtractor={(item) => item}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={[styles.optRow, item === value && styles.optRowActive]}
                onPress={() => { onSelect(item); onClose(); }}
              >
                <Text style={[styles.optText, item === value && styles.optTextActive]}>{item}</Text>
                {item === value && <Ionicons name="checkmark" size={20} color="#1a5c2e" />}
              </TouchableOpacity>
            )}
          />
        </View>
      </View>
    </Modal>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function EditFormResponseScreen() {
  const nav = useNavigation();
  const route = useRoute<Route>();
  const qc = useQueryClient();
  const { id, formResponse } = route.params;

  const [fields, setFields] = useState<Record<string, string>>(
    Object.fromEntries(
      Object.entries(formResponse.data).map(([k, v]) => {
        const s = String(v ?? "");
        const isDateKey = k === "work_date" || k === "date" || k.startsWith("step_");
        return [k, isDateKey ? normDate(s) : s];
      })
    )
  );
  const [picker, setPicker] = useState<{ key: string; title: string; options: string[] } | null>(null);

  const { data: dicts } = useQuery({
    queryKey: ["dictionaries"],
    queryFn: reportsApi.getDictionaries,
  });

  const { data: formTemplate } = useQuery({
    queryKey: ["form", formResponse.form_id],
    queryFn: () => formsApi.getForm(formResponse.form_id),
  });

  // Карта нод флоу: {nodeId → FlowNode}
  const nodeMap = useMemo<Record<string, FlowNode>>(() => {
    const flow = formTemplate?.schema?.flow;
    if (!flow?.nodes) return {};
    return Object.fromEntries(flow.nodes.map((n) => [n.id, n]));
  }, [formTemplate]);

  // Есть ли в данных именованное поле даты (work_date/date)
  const hasNamedDate = "work_date" in fields || "date" in fields;

  const mutation = useMutation({
    mutationFn: () => reportsApi.updateFormResponse(id, fields),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["report", id, "form"] });
      qc.invalidateQueries({ queryKey: ["otd-feed"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      showAlert("Сохранено!", "Ответ формы обновлён.");
      nav.goBack();
    },
    onError: (e: any) => showAlert("Ошибка", e?.response?.data?.detail || "Не удалось сохранить"),
  });

  const set = (key: string, value: string) => setFields((f) => ({ ...f, [key]: value }));

  // При смене work_type НЕ удаляем ключи — просто меняем значение.
  // Добавляем нужные поля если их ещё нет.
  const setWorkType = (value: string) => {
    setFields((f) => {
      const updated = { ...f, work_type: value };
      if (value === "Техника") {
        if (!("machine_type" in updated)) updated.machine_type = "";
        if (!("activity_tech" in updated)) updated.activity_tech = "";
      }
      if (value === "Ручная") {
        if (!("activity_hand" in updated)) updated.activity_hand = "";
      }
      return updated;
    });
  };

  const isTech = fields.work_type === "Техника";
  const isHand = fields.work_type === "Ручная";

  // Набор значений машин для определения machine-related step-полей
  const machineValues = useMemo(() => {
    if (!dicts) return new Set<string>();
    return new Set([
      ...dicts.machine_kinds.map((k) => k.title),
      ...dicts.machine_items.map((i) => i.name),
    ]);
  }, [dicts]);

  const techActivityOptions = useMemo(
    () => dicts?.activities.filter((a) => a.grp === "техника").map((a) => a.name) ?? [],
    [dicts]
  );
  const handActivityOptions = useMemo(
    () => dicts?.activities.filter((a) => a.grp === "ручная").map((a) => a.name) ?? [],
    [dicts]
  );
  const locationOptions = useMemo(
    () => dicts?.locations.map((l) => l.name) ?? [],
    [dicts]
  );
  const machineOptions = useMemo(
    () => dicts?.machine_kinds.map((k) => k.title) ?? [],
    [dicts]
  );
  const cropOptions = useMemo(
    () => dicts?.crops.map((c) => c.name) ?? [],
    [dicts]
  );

  const openPicker = (key: string, title: string, options: string[]) =>
    setPicker({ key, title, options });

  // Рендер поля по ключу
  const renderField = (key: string) => {
    const value = fields[key] ?? "";

    // ── Именованные поля: скрываем по work_type ─────────────────────────────
    if (key === "machine_type" && isHand) return null;
    if (key === "activity_tech" && isHand) return null;
    if (key === "activity_hand" && isTech) return null;

    // ── __sub_xxx — подполя техники, скрываем при «Ручная» ──────────────────
    if (key.startsWith("__sub_") && isHand) return null;

    // ── step_xxx — ноды FlowForm ─────────────────────────────────────────────
    if (key.startsWith("step_")) {
      const node = nodeMap[key];
      if (!node) return null; // нода не найдена в схеме — скрываем

      // Скрываем машинные ноды при «Ручная»
      if (isHand && machineValues.has(value)) return null;

      // Дата-нода: пропускаем если уже есть именованный work_date/date (дубликат)
      if (node.type === "date" && hasNamedDate) return null;

      const nodeLabel = node.label;

      // Дата-нода
      if (node.type === "date") {
        return (
          <View key={key} style={styles.fieldGroup}>
            <Text style={styles.label}>{nodeLabel}</Text>
            <DatePicker value={normDate(value) || new Date().toISOString().slice(0, 10)} onChange={(v) => set(key, v)} />
          </View>
        );
      }

      // Числовая нода
      if (node.type === "number") {
        return (
          <View key={key} style={styles.fieldGroup}>
            <Text style={styles.label}>{nodeLabel}</Text>
            <TextInput style={styles.input} value={value} onChangeText={(v) => set(key, v)} placeholder={nodeLabel} keyboardType="numeric" />
          </View>
        );
      }

      // Нода с выбором (choice / source) — пикер
      if (node.type === "choice" || node.source) {
        const opts = getStepOptions(node, dicts, fields);
        if (opts.length > 0) {
          return (
            <View key={key} style={styles.fieldGroup}>
              <Text style={styles.label}>{nodeLabel}</Text>
              <TouchableOpacity style={styles.selectRow} onPress={() => openPicker(key, nodeLabel, opts)}>
                <Text style={[styles.selectText, !value && styles.selectPlaceholder]}>{value || "Выбрать..."}</Text>
                <Ionicons name="chevron-down" size={18} color="#888" />
              </TouchableOpacity>
            </View>
          );
        }
      }

      // Текстовая нода
      return (
        <View key={key} style={styles.fieldGroup}>
          <Text style={styles.label}>{nodeLabel}</Text>
          <TextInput style={styles.input} value={value} onChangeText={(v) => set(key, v)} placeholder={nodeLabel} />
        </View>
      );
    }

    // ── __sub_xxx — «Техника (уточнение)» ───────────────────────────────────
    if (key.startsWith("__sub_")) {
      const subLabel = "Техника (уточнение)";
      const allMachineItems = dicts?.machine_items.map((i) => i.name) ?? [];
      return (
        <View key={key} style={styles.fieldGroup}>
          <Text style={styles.label}>{subLabel}</Text>
          <TouchableOpacity style={styles.selectRow} onPress={() => openPicker(key, subLabel, allMachineItems)}>
            <Text style={[styles.selectText, !value && styles.selectPlaceholder]}>{value || "Выбрать..."}</Text>
            <Ionicons name="chevron-down" size={18} color="#888" />
          </TouchableOpacity>
        </View>
      );
    }

    const label = FIELD_LABELS[key] || key;

    // Дата: рендерим только одно из полей work_date / date (приоритет у work_date)
    if (key === "work_date" || key === "date") {
      if (key === "date" && "work_date" in fields) return null; // пропускаем дублирующий ключ
      return (
        <View key={key} style={styles.fieldGroup}>
          <Text style={styles.label}>{label}</Text>
          <DatePicker
            value={normDate(value) || new Date().toISOString().slice(0, 10)}
            onChange={(v) => set(key, v)}
          />
        </View>
      );
    }

    // Часы — чипы + ручной ввод
    if (key === "hours") {
      return (
        <View key={key} style={styles.fieldGroup}>
          <Text style={styles.label}>{label}</Text>
          <View style={styles.chips}>
            {[2, 4, 6, 8, 10, 12].map((h) => (
              <TouchableOpacity
                key={h}
                style={[styles.chip, value === String(h) && styles.chipActive]}
                onPress={() => set(key, String(h))}
              >
                <Text style={[styles.chipText, value === String(h) && styles.chipTextActive]}>{h}ч</Text>
              </TouchableOpacity>
            ))}
          </View>
          <TextInput
            style={styles.input}
            value={value}
            onChangeText={(v) => set(key, v)}
            placeholder="Другое..."
            keyboardType="numeric"
          />
        </View>
      );
    }

    // Тип работ — 2 кнопки
    if (key === "work_type") {
      return (
        <View key={key} style={styles.fieldGroup}>
          <Text style={styles.label}>{label}</Text>
          <View style={styles.chips}>
            {["Техника", "Ручная"].map((opt) => (
              <TouchableOpacity
                key={opt}
                style={[styles.wideChip, value === opt && styles.chipActive]}
                onPress={() => setWorkType(opt)}
              >
                <Text style={[styles.chipText, value === opt && styles.chipTextActive]}>{opt}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      );
    }

    // Тип техники
    if (key === "machine_type") {
      return (
        <View key={key} style={styles.fieldGroup}>
          <Text style={styles.label}>{label}</Text>
          <TouchableOpacity style={styles.selectRow} onPress={() => openPicker(key, label, machineOptions)}>
            <Text style={[styles.selectText, !value && styles.selectPlaceholder]}>{value || "Выбрать..."}</Text>
            <Ionicons name="chevron-down" size={18} color="#888" />
          </TouchableOpacity>
        </View>
      );
    }

    // Деятельность техника
    if (key === "activity_tech") {
      return (
        <View key={key} style={styles.fieldGroup}>
          <Text style={styles.label}>{label}</Text>
          <TouchableOpacity style={styles.selectRow} onPress={() => openPicker(key, label, techActivityOptions)}>
            <Text style={[styles.selectText, !value && styles.selectPlaceholder]}>{value || "Выбрать..."}</Text>
            <Ionicons name="chevron-down" size={18} color="#888" />
          </TouchableOpacity>
        </View>
      );
    }

    // Деятельность ручная
    if (key === "activity_hand") {
      return (
        <View key={key} style={styles.fieldGroup}>
          <Text style={styles.label}>{label}</Text>
          <TouchableOpacity style={styles.selectRow} onPress={() => openPicker(key, label, handActivityOptions)}>
            <Text style={[styles.selectText, !value && styles.selectPlaceholder]}>{value || "Выбрать..."}</Text>
            <Ionicons name="chevron-down" size={18} color="#888" />
          </TouchableOpacity>
        </View>
      );
    }

    // Место/поле
    if (key === "location") {
      return (
        <View key={key} style={styles.fieldGroup}>
          <Text style={styles.label}>{label}</Text>
          <TouchableOpacity style={styles.selectRow} onPress={() => openPicker(key, label, locationOptions)}>
            <Text style={[styles.selectText, !value && styles.selectPlaceholder]}>{value || "Выбрать..."}</Text>
            <Ionicons name="chevron-down" size={18} color="#888" />
          </TouchableOpacity>
        </View>
      );
    }

    // Культура
    if (key === "crop") {
      return (
        <View key={key} style={styles.fieldGroup}>
          <Text style={styles.label}>{label}</Text>
          <TouchableOpacity style={styles.selectRow} onPress={() => openPicker(key, label, cropOptions)}>
            <Text style={[styles.selectText, !value && styles.selectPlaceholder]}>{value || "Выбрать..."}</Text>
            <Ionicons name="chevron-down" size={18} color="#888" />
          </TouchableOpacity>
        </View>
      );
    }

    // Прочие именованные поля — текст
    return (
      <View key={key} style={styles.fieldGroup}>
        <Text style={styles.label}>{label}</Text>
        <TextInput style={styles.input} value={value} onChangeText={(v) => set(key, v)} placeholder={label} />
      </View>
    );
  };

  return (
    <View style={{ flex: 1 }}>
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.card}>
          {Object.keys(fields).map(renderField)}
        </View>

        <TouchableOpacity
          style={[styles.saveBtn, mutation.isPending && styles.saveBtnOff]}
          onPress={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <>
              <Ionicons name="checkmark-circle-outline" size={20} color="#fff" />
              <Text style={styles.saveBtnText}>Сохранить</Text>
            </>
          )}
        </TouchableOpacity>
      </ScrollView>

      {picker && (
        <PickerModal
          visible
          title={picker.title}
          options={picker.options}
          value={fields[picker.key] ?? ""}
          onSelect={(v) => set(picker.key, v)}
          onClose={() => setPicker(null)}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  content: { padding: 16, paddingBottom: 32 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 20,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    elevation: 3,
    marginBottom: 16,
  },
  fieldGroup: { marginBottom: 18 },
  label: { fontSize: 13, color: "#888", marginBottom: 6 },
  input: {
    borderWidth: 1.5,
    borderColor: "#ddd",
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    backgroundColor: "#fafafa",
    color: "#222",
  },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 8 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: "#ddd",
    backgroundColor: "#fafafa",
  },
  wideChip: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: "#ddd",
    backgroundColor: "#fafafa",
    alignItems: "center",
  },
  chipActive: { borderColor: "#1a5c2e", backgroundColor: "#e8f5e9" },
  chipText: { fontSize: 14, color: "#444", textAlign: "center" },
  chipTextActive: { color: "#1a5c2e", fontWeight: "bold" },
  selectRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderWidth: 1.5,
    borderColor: "#ddd",
    borderRadius: 10,
    padding: 12,
    backgroundColor: "#fafafa",
  },
  selectText: { fontSize: 15, color: "#222" },
  selectPlaceholder: { color: "#aaa" },
  saveBtn: {
    flexDirection: "row",
    gap: 8,
    backgroundColor: "#1a5c2e",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  saveBtnOff: { backgroundColor: "#b0bdb1" },
  saveBtnText: { color: "#fff", fontWeight: "bold", fontSize: 16 },
  // Modal
  overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "flex-end" },
  sheet: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: "70%",
    paddingBottom: 32,
  },
  sheetHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: "#f0f0f0",
  },
  sheetTitle: { fontSize: 17, fontWeight: "bold", color: "#1a5c2e" },
  optRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: "#f5f5f5",
  },
  optRowActive: { backgroundColor: "#f0faf2" },
  optText: { fontSize: 15, color: "#333" },
  optTextActive: { color: "#1a5c2e", fontWeight: "bold" },
});
