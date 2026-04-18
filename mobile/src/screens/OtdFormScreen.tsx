import React, { useState } from "react";
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  Alert, ActivityIndicator, TextInput,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { reportsApi } from "../api/reports";
import { format } from "date-fns";
import DatePicker from "../components/DatePicker";

type Step = "date" | "hours" | "work_type" | "machine_type" | "machine" | "activity" | "location" | "trips" | "crop" | "confirm";

interface FormState {
  work_date: string;
  hours: number;
  activity_grp: string;
  activity: string;
  machine_type: string;
  machine_name: string;
  location: string;
  location_grp: string;
  trips: number;
  crop: string;
}

export default function OtdFormScreen() {
  const nav = useNavigation();
  const qc = useQueryClient();
  const [step, setStep] = useState<Step>("date");
  const [form, setForm] = useState<Partial<FormState>>({
    work_date: format(new Date(), "yyyy-MM-dd"),
  });

  const { data: dicts, isLoading: dictsLoading } = useQuery({
    queryKey: ["dictionaries"],
    queryFn: reportsApi.getDictionaries,
  });

  const mutation = useMutation({
    mutationFn: reportsApi.createReport,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reports"] });
      qc.invalidateQueries({ queryKey: ["otd-feed"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      Alert.alert("Отчёт отправлен!", "Отчёт ОТД успешно сохранён.", [
        { text: "OK", onPress: () => nav.goBack() },
      ]);
    },
    onError: (e: any) => {
      Alert.alert("Ошибка", e?.response?.data?.detail || "Не удалось сохранить отчёт");
    },
  });

  if (dictsLoading || !dicts) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#1a5c2e" />
      </View>
    );
  }

  const techActivities = dicts.activities.filter((a) => a.grp === "техника");
  const handActivities = dicts.activities.filter((a) => a.grp === "ручная");
  const polya = dicts.locations.filter((l) => l.grp === "поля");
  const sklad = dicts.locations.filter((l) => l.grp === "склад");
  const isTech = form.activity_grp === "техника";

  const handleSubmit = () => {
    mutation.mutate({
      work_date: form.work_date!,
      hours: form.hours!,
      location: form.location!,
      location_grp: form.location_grp!,
      activity: form.activity!,
      activity_grp: form.activity_grp!,
      machine_type: form.machine_type || undefined,
      machine_name: form.machine_name || undefined,
      trips: form.trips || undefined,
      crop: form.crop || undefined,
    });
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <StepIndicator steps={STEPS} current={STEPS.indexOf(step)} />

      {step === "date" && (
        <StepCard title="Дата работы">
          <DatePicker
            value={form.work_date || format(new Date(), "yyyy-MM-dd")}
            onChange={(v) => setForm({ ...form, work_date: v })}
          />
          <NavButton label="Далее →" onPress={() => setStep("hours")} disabled={!form.work_date} />
        </StepCard>
      )}

      {step === "hours" && (
        <StepCard title="Количество часов">
          {[2, 4, 6, 8, 10, 12].map((h) => (
            <SelectButton
              key={h}
              label={`${h} ч`}
              selected={form.hours === h}
              onPress={() => setForm({ ...form, hours: h })}
            />
          ))}
          <TextInput
            style={[styles.input, { marginTop: 8 }]}
            value={form.hours?.toString() || ""}
            onChangeText={(v) => setForm({ ...form, hours: parseFloat(v) || 0 })}
            placeholder="Другое..."
            keyboardType="numeric"
          />
          <NavRow
            onBack={() => setStep("date")}
            onNext={() => setStep("work_type")}
            nextDisabled={!form.hours || form.hours <= 0}
          />
        </StepCard>
      )}

      {step === "work_type" && (
        <StepCard title="Тип работ">
          <SelectButton
            label="Техника"
            selected={form.activity_grp === "техника"}
            onPress={() => setForm({ ...form, activity_grp: "техника", machine_type: "", machine_name: "", activity: "" })}
          />
          <SelectButton
            label="Ручная"
            selected={form.activity_grp === "ручная"}
            onPress={() => setForm({ ...form, activity_grp: "ручная", machine_type: "Ручная", machine_name: "", trips: 0 })}
          />
          <NavRow
            onBack={() => setStep("hours")}
            onNext={() => setStep(form.activity_grp === "техника" ? "machine_type" : "activity")}
            nextDisabled={!form.activity_grp}
          />
        </StepCard>
      )}

      {step === "machine_type" && (
        <StepCard title="Тип техники">
          {dicts.machine_kinds.map((k) => (
            <SelectButton
              key={k.id}
              label={k.title}
              selected={form.machine_type === k.title}
              onPress={() => setForm({ ...form, machine_type: k.title })}
            />
          ))}
          <NavRow
            onBack={() => setStep("work_type")}
            onNext={() =>
              setStep(
                dicts.machine_kinds.find((k) => k.title === form.machine_type)?.mode === "list"
                  ? "machine"
                  : "activity"
              )
            }
            nextDisabled={!form.machine_type}
          />
        </StepCard>
      )}

      {step === "machine" && (
        <StepCard title="Выберите технику">
          {dicts.machine_items
            .filter((i) => dicts.machine_kinds.find((k) => k.title === form.machine_type)?.id === i.kind_id)
            .map((item) => (
              <SelectButton
                key={item.id}
                label={item.name}
                selected={form.machine_name === item.name}
                onPress={() => setForm({ ...form, machine_name: item.name })}
              />
            ))}
          <NavRow
            onBack={() => setStep("machine_type")}
            onNext={() => setStep("activity")}
            nextDisabled={!form.machine_name}
          />
        </StepCard>
      )}

      {step === "activity" && (
        <StepCard title={isTech ? "Вид деятельности" : "Вид ручной работы"}>
          {(isTech ? techActivities : handActivities).map((a) => (
            <SelectButton
              key={a.id}
              label={a.name}
              selected={form.activity === a.name}
              onPress={() => setForm({ ...form, activity: a.name })}
            />
          ))}
          <NavRow
            onBack={() => setStep(isTech ? "machine_type" : "work_type")}
            onNext={() => setStep("location")}
            nextDisabled={!form.activity}
          />
        </StepCard>
      )}

      {step === "location" && (
        <StepCard title="Поле / Склад">
          <Text style={styles.groupLabel}>Поля</Text>
          {polya.map((l) => (
            <SelectButton
              key={l.id}
              label={l.name}
              selected={form.location === l.name}
              onPress={() => setForm({ ...form, location: l.name, location_grp: "поля" })}
            />
          ))}
          <Text style={styles.groupLabel}>Склад</Text>
          {sklad.map((l) => (
            <SelectButton
              key={l.id}
              label={l.name}
              selected={form.location === l.name}
              onPress={() => setForm({ ...form, location: l.name, location_grp: "склад" })}
            />
          ))}
          <NavRow
            onBack={() => setStep("activity")}
            onNext={() => setStep(isTech ? "trips" : "crop")}
            nextDisabled={!form.location}
          />
        </StepCard>
      )}

      {step === "trips" && (
        <StepCard title="Количество рейсов">
          {[1, 2, 3, 4, 5, 6, 8, 10].map((t) => (
            <SelectButton
              key={t}
              label={`${t} рейс${t === 1 ? "" : t < 5 ? "а" : "ов"}`}
              selected={form.trips === t}
              onPress={() => setForm({ ...form, trips: t })}
            />
          ))}
          <TextInput
            style={[styles.input, { marginTop: 8 }]}
            value={form.trips?.toString() || ""}
            onChangeText={(v) => setForm({ ...form, trips: parseInt(v) || 0 })}
            placeholder="Другое..."
            keyboardType="numeric"
          />
          <SelectButton
            label="Не применимо"
            selected={form.trips === 0}
            onPress={() => setForm({ ...form, trips: 0 })}
          />
          <NavRow
            onBack={() => setStep("location")}
            onNext={() => setStep("crop")}
          />
        </StepCard>
      )}

      {step === "crop" && (
        <StepCard title="Культура (необязательно)">
          {dicts.crops.map((c) => (
            <SelectButton
              key={c.name}
              label={c.name}
              selected={form.crop === c.name}
              onPress={() => setForm({ ...form, crop: c.name })}
            />
          ))}
          <SelectButton
            label="Не указывать"
            selected={!form.crop}
            onPress={() => setForm({ ...form, crop: "" })}
          />
          <NavRow
            onBack={() => setStep(isTech ? "trips" : "location")}
            onNext={() => setStep("confirm")}
          />
        </StepCard>
      )}

      {step === "confirm" && (
        <StepCard title="Подтверждение">
          <ConfirmRow label="Дата" value={form.work_date || "—"} />
          <ConfirmRow label="Часы" value={`${form.hours} ч`} />
          <ConfirmRow label="Тип работ" value={isTech ? "Техника" : "Ручная"} />
          {form.machine_type && (
            <ConfirmRow
              label="Техника"
              value={`${form.machine_type}${form.machine_name ? ` — ${form.machine_name}` : ""}`}
            />
          )}
          <ConfirmRow label="Деятельность" value={form.activity || "—"} />
          <ConfirmRow label="Место" value={form.location || "—"} />
          {isTech && form.trips != null && form.trips > 0 && (
            <ConfirmRow label="Рейсов" value={String(form.trips)} />
          )}
          {form.crop && <ConfirmRow label="Культура" value={form.crop} />}
          <NavRow
            onBack={() => setStep("crop")}
            onNext={handleSubmit}
            nextLabel="Отправить"
            nextDisabled={mutation.isPending}
          />
          {mutation.isPending && <ActivityIndicator style={{ marginTop: 8 }} color="#1a5c2e" />}
        </StepCard>
      )}
    </ScrollView>
  );
}

const STEPS: Step[] = [
  "date", "hours", "work_type", "machine_type", "machine",
  "activity", "location", "trips", "crop", "confirm",
];

function StepIndicator({ steps, current }: { steps: string[]; current: number }) {
  return (
    <View style={{ flexDirection: "row", justifyContent: "center", marginBottom: 16, gap: 4 }}>
      {steps.map((_, i) => (
        <View
          key={i}
          style={{
            width: i === current ? 20 : 8,
            height: 8,
            borderRadius: 4,
            backgroundColor: i === current ? "#1a5c2e" : i < current ? "#a8d5b5" : "#ddd",
          }}
        />
      ))}
    </View>
  );
}

function StepCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.stepCard}>
      <Text style={styles.stepTitle}>{title}</Text>
      {children}
    </View>
  );
}

function SelectButton({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity
      style={[styles.selectBtn, selected && styles.selectBtnActive]}
      onPress={onPress}
    >
      <Text style={[styles.selectBtnText, selected && styles.selectBtnTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

function NavButton({ label, onPress, disabled }: { label: string; onPress: () => void; disabled?: boolean }) {
  return (
    <TouchableOpacity
      style={[styles.navBtn, disabled && styles.navBtnDisabled]}
      onPress={onPress}
      disabled={disabled}
    >
      <Text style={styles.navBtnText}>{label}</Text>
    </TouchableOpacity>
  );
}

function NavRow({
  onBack,
  onNext,
  nextLabel = "Далее →",
  nextDisabled,
}: {
  onBack: () => void;
  onNext: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
}) {
  return (
    <View style={{ flexDirection: "row", gap: 10, marginTop: 16 }}>
      <TouchableOpacity
        style={[styles.navBtn, { flex: 1, backgroundColor: "#eee" }]}
        onPress={onBack}
      >
        <Text style={[styles.navBtnText, { color: "#333" }]}>← Назад</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.navBtn, { flex: 2 }, nextDisabled && styles.navBtnDisabled]}
        onPress={onNext}
        disabled={nextDisabled}
      >
        <Text style={styles.navBtnText}>{nextLabel}</Text>
      </TouchableOpacity>
    </View>
  );
}

function ConfirmRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.confirmRow}>
      <Text style={styles.confirmLabel}>{label}:</Text>
      <Text style={styles.confirmValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f7f5" },
  content: { padding: 16 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  stepCard: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 20,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    elevation: 3,
  },
  stepTitle: { fontSize: 18, fontWeight: "bold", color: "#1a5c2e", marginBottom: 16 },
  selectBtn: {
    padding: 14,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: "#ddd",
    marginBottom: 8,
    backgroundColor: "#fafafa",
  },
  selectBtnActive: { borderColor: "#1a5c2e", backgroundColor: "#e8f5e9" },
  selectBtnText: { fontSize: 15, color: "#444", textAlign: "center" },
  selectBtnTextActive: { color: "#1a5c2e", fontWeight: "bold" },
  navBtn: {
    backgroundColor: "#1a5c2e",
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 4,
  },
  navBtnDisabled: { backgroundColor: "#b0bdb1" },
  navBtnText: { color: "#fff", fontSize: 15, fontWeight: "bold" },
  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    backgroundColor: "#fafafa",
  },
  groupLabel: {
    fontSize: 13,
    fontWeight: "bold",
    color: "#888",
    marginTop: 10,
    marginBottom: 4,
    textTransform: "uppercase",
  },
  confirmRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#f0f0f0",
  },
  confirmLabel: { fontSize: 14, color: "#888" },
  confirmValue: { fontSize: 14, fontWeight: "600", color: "#222" },
});
