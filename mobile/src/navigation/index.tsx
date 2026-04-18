import React, { useEffect } from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createStackNavigator } from "@react-navigation/stack";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { ActivityIndicator, Platform, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useAuthStore } from "../store/authStore";

import LoginScreen from "../screens/LoginScreen";
import HomeScreen from "../screens/HomeScreen";
import OtdFormScreen from "../screens/OtdFormScreen";
import BrigFormScreen from "../screens/BrigFormScreen";
import ReportsScreen from "../screens/ReportsScreen";
import ReportDetailScreen from "../screens/ReportDetailScreen";
import StatsScreen from "../screens/StatsScreen";
import ChatListScreen from "../screens/ChatListScreen";
import ChatRoomScreen from "../screens/ChatRoomScreen";
import ProfileScreen from "../screens/ProfileScreen";
import DynamicFormScreen from "../screens/DynamicFormScreen";
import FlowFormScreen from "../screens/FlowFormScreen";
import AdminScreen from "../screens/AdminScreen";
import EditReportScreen from "../screens/EditReportScreen";
import EditFormResponseScreen from "../screens/EditFormResponseScreen";
import FleetNavigator from "./FleetNavigator";
import { Report, FormResponse } from "../api/reports";

export type RootStackParamList = {
  Auth: undefined;
  Main: undefined;
  OtdForm: undefined;
  BrigForm: undefined;
  FlowForm: { formName: string; title: string };
  ReportDetail: { id: number; source?: "otd" | "form" };
  EditReport: { id: number; report: Report };
  EditFormResponse: { id: number; formResponse: FormResponse };
  ChatRoom: { id: number; name: string };
  DynamicForm: { formId: number; title: string };
  Admin: undefined;
  /** Мониторинг транспорта (отдельный блок вкладок) */
  Fleet: undefined;
};

const Stack = createStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator();

const linking = Platform.OS === "web" ? {
  prefixes: [],
  config: {
    screens: {
      Auth: "login",
      Main: "",
      OtdForm: "otd-form",
      BrigForm: "brig-form",
      Admin: "admin",
    },
  },
} : undefined;

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          const icons: Record<string, keyof typeof Ionicons.glyphMap> = {
            Home: "home-outline",
            Reports: "document-text-outline",
            Stats: "bar-chart-outline",
            Chat: "chatbubbles-outline",
            Profile: "person-outline",
          };
          return <Ionicons name={icons[route.name] || "ellipse-outline"} size={size} color={color} />;
        },
        tabBarActiveTintColor: "#1a5c2e",
        tabBarStyle: { borderTopWidth: 0, elevation: 10, shadowOpacity: 0.08 },
        headerStyle: { backgroundColor: "#1a5c2e" },
        headerTintColor: "#fff",
        headerTitleStyle: { fontWeight: "bold" },
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} options={{ title: "Главная" }} />
      <Tab.Screen name="Reports" component={ReportsScreen} options={{ title: "Отчёты" }} />
      <Tab.Screen name="Stats" component={StatsScreen} options={{ title: "Статистика" }} />
      <Tab.Screen name="Chat" component={ChatListScreen} options={{ title: "Чаты" }} />
      <Tab.Screen name="Profile" component={ProfileScreen} options={{ title: "Профиль" }} />
    </Tab.Navigator>
  );
}

export default function Navigation() {
  const isLoading = useAuthStore((s) => s.isLoading);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const loadUser = useAuthStore((s) => s.loadUser);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  if (isLoading) {
    return (
      <SafeAreaProvider>
        <View style={{ flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#f5f7f5" }}>
          <ActivityIndicator size="large" color="#1a5c2e" />
        </View>
      </SafeAreaProvider>
    );
  }

  return (
    <SafeAreaProvider>
      <NavigationContainer linking={linking}>
        <Stack.Navigator
          key={isAuthenticated ? "authed" : "guest"}
          screenOptions={{
            headerStyle: { backgroundColor: "#1a5c2e" },
            headerTintColor: "#fff",
            headerTitleStyle: { fontWeight: "bold" },
            cardStyle: { flex: 1 },
          }}
        >
          {!isAuthenticated ? (
            <Stack.Screen name="Auth" component={LoginScreen} options={{ headerShown: false }} />
          ) : (
            <>
              <Stack.Screen name="Main" component={MainTabs} options={{ headerShown: false }} />
              <Stack.Screen name="OtdForm" component={OtdFormScreen} options={{ title: "Новый ОТД отчёт" }} />
              <Stack.Screen name="BrigForm" component={BrigFormScreen} options={{ title: "Отчёт бригадира" }} />
              <Stack.Screen
                name="FlowForm"
                component={FlowFormScreen}
                options={({ route }) => ({ title: route.params.title })}
              />
              <Stack.Screen name="ReportDetail" component={ReportDetailScreen} options={{ title: "Отчёт" }} />
              <Stack.Screen name="EditReport" component={EditReportScreen} options={{ title: "Редактировать отчёт" }} />
              <Stack.Screen name="EditFormResponse" component={EditFormResponseScreen} options={{ title: "Редактировать ответ формы" }} />
              <Stack.Screen
                name="ChatRoom"
                component={ChatRoomScreen}
                options={({ route }) => ({ title: route.params.name })}
              />
              <Stack.Screen
                name="DynamicForm"
                component={DynamicFormScreen}
                options={({ route }) => ({ title: route.params.title })}
              />
              <Stack.Screen
                name="Admin"
                component={AdminScreen}
                options={{ title: "Управление пользователями" }}
              />
              <Stack.Screen
                name="Fleet"
                component={FleetNavigator}
                options={{ title: "Мониторинг транспорта", headerShown: true }}
              />
            </>
          )}
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
