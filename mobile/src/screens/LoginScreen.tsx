import React, { useState } from "react";
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, Alert, ActivityIndicator, ScrollView,
} from "react-native";
import { useAuthStore } from "../store/authStore";
import { SafeAreaView } from "react-native-safe-area-context";

export default function LoginScreen() {
  const { login, register } = useAuthStore();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loginVal, setLoginVal] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  const handleSubmit = async () => {
    setErrorText("");
    if (!loginVal.trim() || !password.trim()) {
      const m = "Заполните все поля";
      setErrorText(m);
      if (Platform.OS !== "web") Alert.alert("Ошибка", m);
      return;
    }
    if (mode === "register" && !fullName.trim()) {
      const m = "Укажите имя";
      setErrorText(m);
      if (Platform.OS !== "web") Alert.alert("Ошибка", m);
      return;
    }
    if (loginVal.trim().length < 3) {
      const m = "Логин не короче 3 символов";
      setErrorText(m);
      if (Platform.OS !== "web") Alert.alert("Ошибка", m);
      return;
    }
    if (password.length < 6) {
      const m = "Пароль не короче 6 символов";
      setErrorText(m);
      if (Platform.OS !== "web") Alert.alert("Ошибка", m);
      return;
    }
    setLoading(true);
    try {
      if (mode === "login") {
        await login(loginVal.trim(), password);
      } else {
        await register(loginVal.trim(), password, fullName.trim());
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((x: { msg?: string }) => x.msg || "").filter(Boolean).join(", ")
            : e?.message === "Network Error"
              ? "Нет связи с сервером. Запустите backend (порт 8000) и проверьте адрес API."
              : e?.code === "ECONNABORTED" || String(e?.message || "").toLowerCase().includes("timeout")
                ? "Таймаут: сервер не ответил. Убедитесь, что API запущен на http://localhost:8000"
                : "Ошибка входа";
      setErrorText(msg);
      if (Platform.OS !== "web") Alert.alert("Ошибка", msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
    <KeyboardAvoidingView style={styles.flex1} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Text style={styles.logo}>🌾 TerraApp</Text>
          <Text style={styles.subtitle}>Корпоративная система</Text>
        </View>

        <View style={styles.card}>
          <View style={styles.tabs}>
            <TouchableOpacity
              style={[styles.tab, mode === "login" && styles.tabActive]}
              onPress={() => setMode("login")}
            >
              <Text style={[styles.tabText, mode === "login" && styles.tabTextActive]}>Вход</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.tab, mode === "register" && styles.tabActive]}
              onPress={() => setMode("register")}
            >
              <Text style={[styles.tabText, mode === "register" && styles.tabTextActive]}>Регистрация</Text>
            </TouchableOpacity>
          </View>

          {mode === "register" && (
            <TextInput
              style={styles.input}
              placeholder="Имя и фамилия"
              placeholderTextColor="#999"
              value={fullName}
              onChangeText={setFullName}
              autoCapitalize="words"
            />
          )}

          <TextInput
            style={styles.input}
            placeholder="Логин"
            placeholderTextColor="#999"
            value={loginVal}
            onChangeText={setLoginVal}
            autoCapitalize="none"
            autoCorrect={false}
          />

          <TextInput
            style={styles.input}
            placeholder="Пароль"
            placeholderTextColor="#999"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />

          {!!errorText && (
            <Text style={styles.errorText} accessibilityLiveRegion="polite">
              {errorText}
            </Text>
          )}

          <TouchableOpacity style={styles.button} onPress={handleSubmit} disabled={loading}>
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>{mode === "login" ? "Войти" : "Зарегистрироваться"}</Text>
            )}
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f0f4f0", minHeight: "100%" as any },
  flex1: { flex: 1 },
  scroll: { flexGrow: 1, justifyContent: "center", padding: 24 },
  header: { alignItems: "center", marginBottom: 32 },
  logo: { fontSize: 36, fontWeight: "bold", color: "#1a5c2e" },
  subtitle: { fontSize: 16, color: "#555", marginTop: 4 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 24,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
  },
  tabs: { flexDirection: "row", marginBottom: 20, borderRadius: 8, overflow: "hidden", backgroundColor: "#f0f4f0" },
  tab: { flex: 1, paddingVertical: 10, alignItems: "center" },
  tabActive: { backgroundColor: "#1a5c2e" },
  tabText: { fontSize: 15, color: "#555", fontWeight: "600" },
  tabTextActive: { color: "#fff" },
  input: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 10,
    padding: 14,
    marginBottom: 14,
    fontSize: 16,
    backgroundColor: "#fafafa",
  },
  button: {
    backgroundColor: "#1a5c2e",
    borderRadius: 10,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 4,
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "bold" },
  errorText: {
    color: "#c0392b",
    fontSize: 14,
    marginBottom: 10,
    textAlign: "center",
    padding: 10,
    backgroundColor: "#fdecea",
    borderRadius: 8,
  },
});
