import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";

/** Геозоны (полигоны) — редактор и списки групп */
export default function FleetGeofencesScreen() {
  return (
    <View style={styles.wrap}>
      <Ionicons name="globe-outline" size={48} color="#0f766e" />
      <Text style={styles.title}>Геозоны</Text>
      <Text style={styles.sub}>
        Полигоны полей и зон, группы. Позже: рисование на карте и сохранение через API.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: "#fffbeb",
    padding: 24,
    justifyContent: "center",
    alignItems: "center",
  },
  title: { fontSize: 20, fontWeight: "700", color: "#134e4a", marginTop: 12 },
  sub: { fontSize: 14, color: "#64748b", textAlign: "center", marginTop: 12, lineHeight: 20 },
});
