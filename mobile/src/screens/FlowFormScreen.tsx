import React, { useState, useMemo, useEffect } from "react";
import {
  View, Text, StyleSheet, ScrollView, TextInput,
  TouchableOpacity, Alert, ActivityIndicator, Platform,
} from "react-native";
import { useRoute, useNavigation, RouteProp } from "@react-navigation/native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { Ionicons } from "@expo/vector-icons";
import { formsApi, FlowNode, FormFlow } from "../api/forms";
import { reportsApi, Dictionaries } from "../api/reports";
import DatePicker from "../components/DatePicker";
import { RootStackParamList } from "../navigation";

type Route = RouteProp<RootStackParamList, "FlowForm">;

/** На вебе Alert.alert часто не виден — используем window.alert */
function showAppAlert(title: string, message?: string) {
  if (Platform.OS === "web" && typeof window !== "undefined") {
    window.alert(message ? `${title}\n\n${message}` : title);
  } else {
    Alert.alert(title, message);
  }
}

function formatApiError(e: unknown): string {
  const err = e as { response?: { data?: { detail?: unknown } }; message?: string };
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d.map((x: { msg?: string }) => x.msg || "").filter(Boolean).join("; ") || "Ошибка валидации";
  }
  if (d && typeof d === "object") return JSON.stringify(d);
  return err?.message === "Network Error"
    ? "Нет связи с сервером (проверьте, что API на http://localhost:8000 запущен)"
    : err?.message || "Не удалось отправить";
}

// ─── Dict option resolver ────────────────────────────────────────────────────
function getOptionsForNode(
  node: FlowNode,
  dicts: Dictionaries | undefined,
  formData: Record<string, string>
): string[] {
  if (node.options && node.options.length > 0) return node.options;
  if (!node.source || !dicts) return [];

  const src = node.source;

  // Handle "machine_items:KindName" — specific kind filter set at design time
  if (src.startsWith("machine_items:")) {
    const kindName = src.replace("machine_items:", "");
    const kind = dicts.machine_kinds.find((k) => k.title === kindName);
    return kind
      ? dicts.machine_items.filter((i) => i.kind_id === kind.id).map((i) => i.name)
      : [];
  }

  switch (src) {
    case "machine_kinds":
      return dicts.machine_kinds.map((k) => k.title);
    case "machine_items": {
      // Dynamic: filter by previously selected machine kind in formData
      const selectedKind = Object.values(formData).find((v) =>
        dicts.machine_kinds.some((k) => k.title === v)
      );
      const kind = dicts.machine_kinds.find((k) => k.title === selectedKind);
      return kind
        ? dicts.machine_items.filter((i) => i.kind_id === kind.id).map((i) => i.name)
        : dicts.machine_items.map((i) => i.name);
    }
    case "activities_tech":
      return dicts.activities.filter((a) => a.grp === "техника").map((a) => a.name);
    case "activities_hand":
      return dicts.activities.filter((a) => a.grp === "ручная").map((a) => a.name);
    case "locations":
      return dicts.locations.map((l) => l.name);
    case "locations_field":
      return dicts.locations.filter((l) => l.grp === "поля").map((l) => l.name);
    case "locations_store":
      return dicts.locations.filter((l) => l.grp === "склад").map((l) => l.name);
    case "crops":
      return dicts.crops.map((c) => c.name);
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

// ─── Build node map and find next node ──────────────────────────────────────
function getNextNodeId(node: FlowNode, selectedValue: string | undefined): string | null {
  if (node.type === "confirm") return null;
  if (node.type === "choice" && node.conditionalNext?.length) {
    const match = node.conditionalNext.find((c) => c.option === selectedValue);
    if (match?.nextId) return match.nextId;
  }
  return node.defaultNextId ?? null;
}

// ─── Step progress bar ───────────────────────────────────────────────────────
function ProgressBar({ history, flow }: { history: string[]; flow: FormFlow }) {
  // Count non-start, non-confirm nodes for estimation
  const totalSteps = flow.nodes.filter((n) => n.type !== "start").length;
  const progress = Math.min(history.length / Math.max(totalSteps, 1), 1);
  return (
    <View style={styles.progressWrap}>
      <View style={[styles.progressBar, { width: `${Math.round(progress * 100)}%` as any }]} />
    </View>
  );
}

// ─── Step Card ───────────────────────────────────────────────────────────────
function StepCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.card}>
      <Text style={styles.stepTitle}>{title}</Text>
      {children}
    </View>
  );
}

// ─── Nav buttons ─────────────────────────────────────────────────────────────
function NavRow({
  onBack,
  onNext,
  nextLabel,
  nextDisabled,
}: {
  onBack?: () => void;
  onNext: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
}) {
  return (
    <View style={styles.navRow}>
      {onBack ? (
        <TouchableOpacity style={styles.backBtn} onPress={onBack}>
          <Ionicons name="arrow-back" size={18} color="#1a5c2e" />
          <Text style={styles.backText}>Назад</Text>
        </TouchableOpacity>
      ) : (
        <View />
      )}
      <TouchableOpacity
        style={[styles.nextBtn, nextDisabled && styles.nextBtnDisabled]}
        onPress={onNext}
        disabled={nextDisabled}
      >
        <Text style={styles.nextText}>{nextLabel || "Далее"}</Text>
        <Ionicons name="arrow-forward" size={18} color="#fff" />
      </TouchableOpacity>
    </View>
  );
}

// ─── Virtual sub-step (auto-injected from kind mode) ─────────────────────────
interface VirtualStep {
  kindId: number;
  kindTitle: string;
  mode: "list" | "choices" | "message";
  options?: string[];   // for mode="choices"
  message?: string;     // for mode="message"
  parentNodeId: string;
  nextId: string | null;
}

// ─── Main Screen ─────────────────────────────────────────────────────────────
export default function FlowFormScreen() {
  const route = useRoute<Route>();
  const nav = useNavigation();
  const qc = useQueryClient();

  const { formName, title } = route.params;

  const [currentNodeId, setCurrentNodeId] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]); // stack of visited node IDs
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [virtualStep, setVirtualStep] = useState<VirtualStep | null>(null);
  const [submitError, setSubmitError] = useState("");

  const { data: form, isLoading: formLoading } = useQuery({
    queryKey: ["flow-form", formName],
    queryFn: () => formsApi.getFormByName(formName),
  });

  // TanStack Query v5 removed onSuccess — use useEffect instead
  useEffect(() => {
    if (!form) return;
    const flow = form.schema?.flow;
    if (flow?.startId && currentNodeId === null) {
      const startNode = flow.nodes.find((n: FlowNode) => n.id === flow.startId);
      const firstId = startNode?.defaultNextId ?? null;
      setCurrentNodeId(firstId ?? flow.startId);
      setHistory([]);
      setFormData({ work_date: format(new Date(), "yyyy-MM-dd") });
    }
  }, [form]);

  const { data: dicts } = useQuery({
    queryKey: ["dictionaries"],
    queryFn: reportsApi.getDictionaries,
  });

  const submitMutation = useMutation({
    mutationFn: () => {
      if (!form?.id) throw new Error("Форма не загружена");
      // JSON для API: только строковые поля
      const payload: Record<string, string> = {};
      Object.entries(formData).forEach(([k, v]) => {
        if (v !== undefined && v !== null) payload[k] = String(v);
      });
      return reportsApi.submitFormResponse(form.id, payload);
    },
    onSuccess: () => {
      setSubmitError("");
      void qc.invalidateQueries({ queryKey: ["form-responses"] });
      void qc.invalidateQueries({ queryKey: ["otd-feed"] });
      void qc.invalidateQueries({ queryKey: ["stats"] });
      if (Platform.OS === "web") {
        showAppAlert("Готово", "Форма успешно отправлена.");
        nav.goBack();
      } else {
        Alert.alert("Отправлено!", "Форма успешно заполнена.", [
          { text: "OK", onPress: () => nav.goBack() },
        ]);
      }
    },
    onError: (e: unknown) => {
      const msg = formatApiError(e);
      setSubmitError(msg);
      showAppAlert("Ошибка отправки", msg);
    },
  });

  const flow = form?.schema?.flow;
  const nodeMap = useMemo(() => {
    const m: Record<string, FlowNode> = {};
    flow?.nodes.forEach((n) => { m[n.id] = n; });
    return m;
  }, [flow]);

  const currentNode = currentNodeId ? nodeMap[currentNodeId] : null;

  // ── Navigation helpers ──
  const goNext = (nodeId: string | null) => {
    if (!nodeId) return;
    if (currentNodeId) setHistory((h) => [...h, currentNodeId]);
    setCurrentNodeId(nodeId);
  };

  const goBack = () => {
    const prev = history[history.length - 1];
    if (!prev) return;
    setHistory((h) => h.slice(0, -1));
    setCurrentNodeId(prev);
  };

  const setValue = (key: string, value: string) =>
    setFormData((d) => {
      const next: Record<string, string> = { ...d, [key]: value };
      // Keep work_date in sync with whichever date step the user selects
      const node = flow?.nodes?.find((n: FlowNode) => n.id === key);
      if (node?.type === "date") next.work_date = value;
      return next;
    });

  // Find a dict item by source key and selected value, return its mode info if any
  const findDictItemMode = (src: string, value: string): { mode: string; options?: string[] | null; message?: string | null } | null => {
    if (!dicts || !value) return null;
    switch (src) {
      case "machine_kinds": {
        const k = dicts.machine_kinds.find((k) => k.title === value);
        return k?.mode ? { mode: k.mode, options: k.options, message: k.message } : null;
      }
      case "activities_tech":
      case "activities_hand": {
        const a = dicts.activities.find((a) => a.name === value);
        return a?.mode ? { mode: a.mode, options: a.options, message: a.message } : null;
      }
      case "locations":
      case "locations_field":
      case "locations_store": {
        const l = dicts.locations.find((l) => l.name === value);
        return l?.mode ? { mode: l.mode, options: l.options, message: l.message } : null;
      }
      case "crops": {
        const c = dicts.crops.find((c) => c.name === value);
        return c?.mode ? { mode: c.mode, options: c.options, message: c.message } : null;
      }
      default: {
        if (src.startsWith("custom:")) {
          const dictId = parseInt(src.replace("custom:", ""), 10);
          const cd = (dicts.custom_dicts ?? []).find((d) => d.id === dictId);
          const item = cd?.items.find((i) => i.value === value);
          return item?.mode ? { mode: item.mode, options: item.options, message: item.message } : null;
        }
        return null;
      }
    }
  };

  // Navigate forward, injecting virtual sub-steps based on dict item modes
  const handleChoiceNext = (node: FlowNode, selected: string | undefined) => {
    const nextId = getNextNodeId(node, selected);
    const src = node.source;

    if (src && selected && dicts) {
      const itemMode = findDictItemMode(src, selected);

      if (itemMode) {
        if (itemMode.mode === "list" && src === "machine_kinds") {
          // machine_kinds list: show machine_items sub-list
          const kind = dicts.machine_kinds.find((k) => k.title === selected);
          if (kind) {
            const kindItems = dicts.machine_items.filter((i) => i.kind_id === kind.id).map((i) => i.name);
            if (kindItems.length > 0) {
              if (currentNodeId) setHistory((h) => [...h, currentNodeId]);
              setCurrentNodeId(null);
              setVirtualStep({ kindId: kind.id, kindTitle: kind.title, mode: "list", options: kindItems, parentNodeId: node.id, nextId });
              return;
            }
          }
        } else if (itemMode.mode === "choices" && itemMode.options?.length) {
          if (currentNodeId) setHistory((h) => [...h, currentNodeId]);
          setCurrentNodeId(null);
          setVirtualStep({ kindId: 0, kindTitle: selected, mode: "choices", options: itemMode.options, parentNodeId: node.id, nextId });
          return;
        } else if (itemMode.mode === "message" && itemMode.message) {
          if (currentNodeId) setHistory((h) => [...h, currentNodeId]);
          setCurrentNodeId(null);
          setVirtualStep({ kindId: 0, kindTitle: selected, mode: "message", message: itemMode.message, parentNodeId: node.id, nextId });
          return;
        }
      }
    }

    goNext(nextId);
  };

  const finishVirtual = (selectedSub?: string) => {
    if (!virtualStep) return;
    if (selectedSub) setValue(`__sub_${virtualStep.parentNodeId}`, selectedSub);
    setVirtualStep(null);
    goNext(virtualStep.nextId);
  };

  // ── Loading states ──
  if (formLoading || !form) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#1a5c2e" />
        <Text style={styles.loadingText}>Загрузка формы…</Text>
      </View>
    );
  }

  if (!flow) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle-outline" size={48} color="#e74c3c" />
        <Text style={styles.errorText}>Схема формы не настроена.</Text>
        <Text style={styles.errorSub}>Обратитесь к администратору.</Text>
      </View>
    );
  }

  // После выбора вида техники (например «Трактор») currentNodeId временно null — показываем подшаг списка техники
  // ── Virtual sub-step rendering (ДО проверки currentNode!) ──
  if (virtualStep) {
    const subKey = `__sub_${virtualStep.parentNodeId}`;
    const subSelected = formData[subKey];

    if (virtualStep.mode === "message") {
      return (
        <ScrollView style={styles.container} contentContainerStyle={styles.content}>
          <ProgressBar history={history} flow={flow} />
          <StepCard title={virtualStep.kindTitle}>
            <View style={styles.msgBox}>
              <Ionicons name="information-circle-outline" size={32} color="#1a5c2e" style={{ marginBottom: 10 }} />
              <Text style={styles.msgText}>{virtualStep.message}</Text>
            </View>
            <NavRow
              onBack={() => {
                setVirtualStep(null);
                const prev = history[history.length - 1];
                setHistory((h) => h.slice(0, -1));
                setCurrentNodeId(prev);
              }}
              onNext={() => finishVirtual()}
              nextLabel="Понятно"
            />
          </StepCard>
        </ScrollView>
      );
    }

    // mode === "list" | "choices"
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <ProgressBar history={history} flow={flow} />
        <StepCard title={`Выберите: ${virtualStep.kindTitle}`}>
          {(virtualStep.options ?? []).map((opt) => (
            <TouchableOpacity
              key={opt}
              style={[styles.optBtn, subSelected === opt && styles.optBtnActive]}
              onPress={() => setValue(subKey, opt)}
            >
              <Text style={[styles.optText, subSelected === opt && styles.optTextActive]}>{opt}</Text>
            </TouchableOpacity>
          ))}
          <NavRow
            onBack={() => {
              setVirtualStep(null);
              const prev = history[history.length - 1];
              setHistory((h) => h.slice(0, -1));
              setCurrentNodeId(prev);
            }}
            onNext={() => finishVirtual(subSelected)}
            nextDisabled={!subSelected}
          />
        </StepCard>
      </ScrollView>
    );
  }

  if (!currentNode) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle-outline" size={48} color="#e74c3c" />
        <Text style={styles.errorText}>Схема формы не настроена.</Text>
        <Text style={styles.errorSub}>Обратитесь к администратору.</Text>
      </View>
    );
  }

  const options = currentNode.type === "choice"
    ? getOptionsForNode(currentNode, dicts, formData)
    : [];
  const selectedValue = formData[currentNode.id];
  const canGoNext = currentNode.type !== "choice" || !!selectedValue;

  // ── Render current step ──
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <ProgressBar history={history} flow={flow} />

      {/* ── DATE ── */}
      {currentNode.type === "date" && (
        <StepCard title={currentNode.label}>
          <DatePicker
            value={formData[currentNode.id] || format(new Date(), "yyyy-MM-dd")}
            onChange={(v) => setValue(currentNode.id, v)}
          />
          <NavRow
            onBack={history.length > 0 ? goBack : undefined}
            onNext={() => goNext(getNextNodeId(currentNode, selectedValue))}
            nextDisabled={!formData[currentNode.id]}
          />
        </StepCard>
      )}

      {/* ── NUMBER ── */}
      {currentNode.type === "number" && (
        <StepCard title={currentNode.label}>
          {[2, 4, 6, 8, 10, 12].map((n) => (
            <TouchableOpacity
              key={n}
              style={[styles.optBtn, selectedValue === String(n) && styles.optBtnActive]}
              onPress={() => setValue(currentNode.id, String(n))}
            >
              <Text style={[styles.optText, selectedValue === String(n) && styles.optTextActive]}>
                {n}
              </Text>
            </TouchableOpacity>
          ))}
          <TextInput
            style={[styles.input, { marginTop: 8 }]}
            value={formData[currentNode.id] || ""}
            onChangeText={(v) => setValue(currentNode.id, v)}
            placeholder="Другое значение..."
            keyboardType="numeric"
            placeholderTextColor="#999"
          />
          <NavRow
            onBack={history.length > 0 ? goBack : undefined}
            onNext={() => goNext(getNextNodeId(currentNode, selectedValue))}
            nextDisabled={!formData[currentNode.id]}
          />
        </StepCard>
      )}

      {/* ── CHOICE ── */}
      {currentNode.type === "choice" && (
        <StepCard title={currentNode.label}>
          {options.length === 0 ? (
            <Text style={styles.emptyHint}>Варианты не настроены. Обратитесь к администратору.</Text>
          ) : (
            options.map((opt) => (
              <TouchableOpacity
                key={opt}
                style={[styles.optBtn, selectedValue === opt && styles.optBtnActive]}
                onPress={() => setValue(currentNode.id, opt)}
              >
                <Text style={[styles.optText, selectedValue === opt && styles.optTextActive]}>
                  {opt}
                </Text>
              </TouchableOpacity>
            ))
          )}
          <NavRow
            onBack={history.length > 0 ? goBack : undefined}
            onNext={() => handleChoiceNext(currentNode, selectedValue)}
            nextDisabled={!canGoNext || options.length === 0}
          />
        </StepCard>
      )}

      {/* ── TEXT ── */}
      {currentNode.type === "text" && (
        <StepCard title={currentNode.label}>
          <TextInput
            style={[styles.input, styles.textArea]}
            value={formData[currentNode.id] || ""}
            onChangeText={(v) => setValue(currentNode.id, v)}
            placeholder="Введите текст..."
            multiline
            numberOfLines={4}
            placeholderTextColor="#999"
          />
          <NavRow
            onBack={history.length > 0 ? goBack : undefined}
            onNext={() => goNext(getNextNodeId(currentNode, selectedValue))}
          />
        </StepCard>
      )}

      {/* ── CONFIRM ── */}
      {currentNode.type === "confirm" && (
        <View style={styles.card}>
          <Text style={styles.stepTitle}>Подтверждение</Text>
          <Text style={styles.confirmSub}>Проверьте данные перед отправкой</Text>

          <View style={styles.summaryList}>
            {flow.nodes
              .filter((n) => n.type !== "start" && n.type !== "confirm" && formData[n.id])
              .map((n) => (
                <View key={n.id} style={styles.summaryRow}>
                  <Text style={styles.summaryKey}>{n.label}</Text>
                  <Text style={styles.summaryVal}>{formData[n.id]}</Text>
                </View>
              ))}
            {/* Подшаг техники (после «Трактор» и т.п.) */}
            {Object.entries(formData)
              .filter(([k]) => k.startsWith("__sub_"))
              .map(([k, v]) => (
                <View key={k} style={styles.summaryRow}>
                  <Text style={styles.summaryKey}>Техника (уточнение)</Text>
                  <Text style={styles.summaryVal}>{v}</Text>
                </View>
              ))}
          </View>

          {!!submitError && (
            <Text style={styles.submitErrText} accessibilityLiveRegion="polite">
              {submitError}
            </Text>
          )}

          <View style={styles.navRow}>
            {history.length > 0 && (
              <TouchableOpacity style={styles.backBtn} onPress={goBack}>
                <Ionicons name="arrow-back" size={18} color="#1a5c2e" />
                <Text style={styles.backText}>Назад</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity
              style={[styles.submitBtn, submitMutation.isPending && styles.nextBtnDisabled]}
              onPress={() => {
                setSubmitError("");
                submitMutation.mutate();
              }}
              disabled={submitMutation.isPending}
              accessibilityRole="button"
            >
              {submitMutation.isPending ? (
                <ActivityIndicator color="#fff" size="small" />
              ) : (
                <>
                  <Ionicons name="checkmark-circle-outline" size={20} color="#fff" />
                  <Text style={styles.submitText}>Отправить</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* Skip start node that may appear on initial render */}
      {currentNode.type === "start" && (
        <View style={styles.center}>
          <ActivityIndicator color="#1a5c2e" />
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  content: { padding: 16 },
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 32 },
  loadingText: { marginTop: 12, color: "#888", fontSize: 14 },
  errorText: { fontSize: 16, fontWeight: "bold", color: "#e74c3c", marginTop: 12 },
  errorSub: { fontSize: 13, color: "#888", marginTop: 4, textAlign: "center" },

  progressWrap: {
    height: 4, backgroundColor: "#ddd", borderRadius: 2, marginBottom: 16, overflow: "hidden",
  },
  progressBar: { height: 4, backgroundColor: "#1a5c2e", borderRadius: 2 },

  card: {
    backgroundColor: "#fff", borderRadius: 16, padding: 20,
    shadowColor: "#000", shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08, elevation: 3,
  },
  stepTitle: { fontSize: 18, fontWeight: "bold", color: "#1a5c2e", marginBottom: 16 },
  confirmSub: { fontSize: 13, color: "#888", marginBottom: 16, marginTop: -12 },

  optBtn: {
    padding: 14, borderRadius: 10, borderWidth: 1.5,
    borderColor: "#ddd", marginBottom: 8, backgroundColor: "#fafafa",
  },
  optBtnActive: { borderColor: "#1a5c2e", backgroundColor: "#e8f5e9" },
  optText: { fontSize: 15, color: "#555", textAlign: "center" },
  optTextActive: { color: "#1a5c2e", fontWeight: "bold" },

  input: {
    borderWidth: 1, borderColor: "#ddd", borderRadius: 10,
    padding: 14, fontSize: 15, backgroundColor: "#fafafa", color: "#222",
  },
  textArea: { height: 100, textAlignVertical: "top" },
  emptyHint: { fontSize: 13, color: "#e74c3c", textAlign: "center", marginVertical: 16 },

  navRow: {
    flexDirection: "row", justifyContent: "space-between",
    alignItems: "center", marginTop: 20,
  },
  backBtn: {
    flexDirection: "row", alignItems: "center", gap: 6,
    paddingVertical: 10, paddingHorizontal: 14,
    borderRadius: 10, borderWidth: 1.5, borderColor: "#1a5c2e",
  },
  backText: { color: "#1a5c2e", fontWeight: "600", fontSize: 14 },
  nextBtn: {
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: "#1a5c2e", paddingVertical: 12, paddingHorizontal: 20,
    borderRadius: 10,
  },
  nextBtnDisabled: { opacity: 0.4 },
  nextText: { color: "#fff", fontWeight: "bold", fontSize: 15 },

  submitBtn: {
    flexDirection: "row", alignItems: "center", gap: 8,
    backgroundColor: "#1a5c2e", paddingVertical: 14, paddingHorizontal: 24,
    borderRadius: 12, flex: 1, justifyContent: "center",
  },
  submitText: { color: "#fff", fontWeight: "bold", fontSize: 16 },

  summaryList: {
    borderTopWidth: 1, borderTopColor: "#eee", paddingTop: 12, marginBottom: 8,
  },
  summaryRow: {
    flexDirection: "row", justifyContent: "space-between",
    paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: "#f0f0f0",
  },
  summaryKey: { fontSize: 13, color: "#888", flex: 1 },
  summaryVal: { fontSize: 13, fontWeight: "600", color: "#222", flex: 1, textAlign: "right" },

  msgBox: { alignItems: "center", paddingVertical: 16 },
  msgText: { fontSize: 15, color: "#333", textAlign: "center", lineHeight: 22 },

  submitErrText: {
    color: "#c0392b",
    fontSize: 14,
    marginTop: 12,
    marginBottom: 4,
    padding: 10,
    backgroundColor: "#fdecea",
    borderRadius: 8,
  },
});
