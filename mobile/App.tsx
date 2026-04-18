import React, { useEffect, Component, ErrorInfo, ReactNode } from "react";
import { Platform, View, Text, ScrollView, StyleSheet } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Navigation from "./src/navigation";
import { api } from "./src/api/client";
import { useSyncFormsAndDictionaries } from "./src/hooks/useSyncFormsAndDictionaries";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      // Формы и словари часто инвалидируются явно; короткий staleTime — чаще свежие данные
      staleTime: 15_000,
      refetchOnReconnect: true,
    },
  },
});

function SyncFormsOnForeground() {
  useSyncFormsAndDictionaries();
  return null;
}

// Shows the error on screen instead of blank white
class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("App crashed:", error, info);
  }
  render() {
    if (this.state.error) {
      const err = this.state.error as Error;
      return (
        <View style={s.err}>
          <Text style={s.errTitle}>Crash: {err.message}</Text>
          <ScrollView><Text style={s.errStack}>{err.stack}</Text></ScrollView>
        </View>
      );
    }
    return this.props.children;
  }
}

const s = StyleSheet.create({
  err: { flex: 1, padding: 20, backgroundColor: "#fff2f2" },
  errTitle: { fontSize: 16, fontWeight: "bold", color: "#c00", marginBottom: 10, marginTop: 40 },
  errStack: { fontSize: 11, color: "#555" },
});

async function setupNotifications() {
  if (Platform.OS === "web") return;
  try {
    const Notifications = await import("expo-notifications");
    const Device = await import("expo-device");
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: true,
      }),
    });
    if (!Device.isDevice) return;
    const { status } = await Notifications.requestPermissionsAsync();
    if (status !== "granted") return;
    const token = (await Notifications.getExpoPushTokenAsync()).data;
    await api
      .post(`/users/me/push-token?token=${encodeURIComponent(token)}&platform=${Device.osName?.toLowerCase() || "unknown"}`)
      .catch(() => {});
  } catch {}
}

export default function App() {
  useEffect(() => { setupNotifications(); }, []);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <SyncFormsOnForeground />
          <Navigation />
        </QueryClientProvider>
      </ErrorBoundary>
    </GestureHandlerRootView>
  );
}
