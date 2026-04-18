import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";

interface EmptyStateProps {
  icon?: keyof typeof Ionicons.glyphMap;
  message: string;
  subtitle?: string;
}

export default function EmptyState({
  icon = "document-outline",
  message,
  subtitle,
}: EmptyStateProps) {
  return (
    <View style={styles.container}>
      <Ionicons name={icon} size={52} color="#ccc" />
      <Text style={styles.message}>{message}</Text>
      {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    paddingTop: 64,
    paddingHorizontal: 32,
  },
  message: {
    color: "#aaa",
    fontSize: 16,
    marginTop: 12,
    textAlign: "center",
  },
  subtitle: {
    color: "#bbb",
    fontSize: 13,
    marginTop: 6,
    textAlign: "center",
  },
});
