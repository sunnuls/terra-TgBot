import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { Ionicons } from "@expo/vector-icons";
import FleetMapScreen from "../screens/fleet/FleetMapScreen";
import FleetObjectsScreen from "../screens/fleet/FleetObjectsScreen";
import FleetGeofencesScreen from "../screens/fleet/FleetGeofencesScreen";

const Tab = createBottomTabNavigator();

/** Отдельный «мини-приложение» мониторинга: свои вкладки, не смешиваем с отчётами/чатами */
export default function FleetNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          const icons: Record<string, keyof typeof Ionicons.glyphMap> = {
            FleetMap: "map-outline",
            FleetObjects: "car-outline",
            FleetGeofences: "globe-outline",
          };
          return <Ionicons name={icons[route.name] || "ellipse-outline"} size={size} color={color} />;
        },
        tabBarActiveTintColor: "#0f766e",
        tabBarInactiveTintColor: "#94a3b8",
        headerShown: false,
        tabBarStyle: { borderTopWidth: 0, elevation: 8 },
      })}
    >
      <Tab.Screen name="FleetMap" component={FleetMapScreen} options={{ title: "Карта" }} />
      <Tab.Screen name="FleetObjects" component={FleetObjectsScreen} options={{ title: "Объекты" }} />
      <Tab.Screen name="FleetGeofences" component={FleetGeofencesScreen} options={{ title: "Геозоны" }} />
    </Tab.Navigator>
  );
}
