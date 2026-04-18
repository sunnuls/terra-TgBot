import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";

/** Список техники / трекеров по IMEI и статусам */
export default function FleetObjectsScreen() {
  return (
    <View style={styles.wrap}>
      <Ionicons name="car-outline" size={48} color="#0f766e" />
      <Text style={styles.title}>Объекты</Text>
      <Text style={styles.sub}>
        Список машин и трекеров, фильтры, поиск. Привязка к IMEI из вашей базы.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: "#f8fafc",
    padding: 24,
    justifyContent: "center",
    alignItems: "center",
  },
  title: { fontSize: 20, fontWeight: "700", color: "#134e4a", marginTop: 12 },
  sub: { fontSize: 14, color: "#64748b", textAlign: "center", marginTop: 12, lineHeight: 20 },
});
