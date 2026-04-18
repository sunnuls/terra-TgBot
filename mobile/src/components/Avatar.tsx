import React from "react";
import { View, Text, StyleSheet } from "react-native";

const COLORS = [
  "#1a5c2e", "#2d6a4f", "#40916c", "#52b788",
  "#1b6ca8", "#5c4033", "#6a3d9a", "#c0392b",
];

function colorFromName(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return COLORS[Math.abs(hash) % COLORS.length];
}

interface AvatarProps {
  name: string;
  size?: number;
}

export default function Avatar({ name, size = 40 }: AvatarProps) {
  const initial = (name || "?")[0].toUpperCase();
  const bg = colorFromName(name);
  const fontSize = size * 0.4;

  return (
    <View
      style={[
        styles.avatar,
        { width: size, height: size, borderRadius: size / 2, backgroundColor: bg },
      ]}
    >
      <Text style={[styles.initial, { fontSize }]}>{initial}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  avatar: {
    justifyContent: "center",
    alignItems: "center",
  },
  initial: {
    color: "#fff",
    fontWeight: "bold",
  },
});
