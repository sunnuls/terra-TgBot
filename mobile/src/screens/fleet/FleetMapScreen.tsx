import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";

/** Карта техники — сюда позже: react-native-maps / Yandex MapKit, слой маркеров с API */
export default function FleetMapScreen() {
  return (
    <View style={styles.wrap}>
      <Ionicons name="map-outline" size={48} color="#0f766e" />
      <Text style={styles.title}>Карта</Text>
      <Text style={styles.sub}>
        Здесь будет карта с объектами (трекеры). Данные — с вашего бэкенда после настройки приёма
        телеметрии.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: "#f0fdfa",
    padding: 24,
    justifyContent: "center",
    alignItems: "center",
  },
  title: { fontSize: 20, fontWeight: "700", color: "#134e4a", marginTop: 12 },
  sub: { fontSize: 14, color: "#64748b", textAlign: "center", marginTop: 12, lineHeight: 20 },
});
