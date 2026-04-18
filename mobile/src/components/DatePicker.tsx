import React, { useState } from "react";
import { View, Text, TouchableOpacity, Platform, StyleSheet } from "react-native";
import { format, parseISO } from "date-fns";
import { Ionicons } from "@expo/vector-icons";

interface DatePickerProps {
  value: string; // yyyy-MM-dd
  onChange: (value: string) => void;
  label?: string;
}

export default function DatePicker({ value, onChange, label }: DatePickerProps) {
  const [show, setShow] = useState(false);

  if (Platform.OS === "web") {
    const today = new Date().toISOString().split("T")[0];
    return (
      <View>
        {label && <Text style={styles.label}>{label}</Text>}
        <View style={styles.button}>
          <Ionicons name="calendar-outline" size={18} color="#1a5c2e" />
          {React.createElement("input", {
            type: "date",
            value: value || today,
            max: today,
            onChange: (e: any) => onChange(e.target.value),
            style: {
              flex: 1,
              border: "none",
              outline: "none",
              fontSize: 16,
              color: "#222",
              backgroundColor: "transparent",
              cursor: "pointer",
              fontFamily: "inherit",
              minWidth: 0,
            },
          })}
        </View>
      </View>
    );
  }

  // Native only
  const RNDateTimePicker = require("@react-native-community/datetimepicker").default;
  const date = value ? parseISO(value) : new Date();

  const handleChange = (_event: any, selected?: Date) => {
    setShow(Platform.OS === "ios");
    if (selected) onChange(format(selected, "yyyy-MM-dd"));
  };

  return (
    <View>
      {label && <Text style={styles.label}>{label}</Text>}
      <TouchableOpacity style={styles.button} onPress={() => setShow(true)}>
        <Ionicons name="calendar-outline" size={18} color="#1a5c2e" />
        <Text style={styles.dateText}>{format(date, "dd.MM.yyyy")}</Text>
        <Ionicons name="chevron-down" size={16} color="#aaa" />
      </TouchableOpacity>
      {show && (
        <RNDateTimePicker
          value={date}
          mode="date"
          display={Platform.OS === "ios" ? "inline" : "default"}
          onChange={handleChange}
          maximumDate={new Date()}
          style={{ backgroundColor: "#fff" }}
          accentColor="#1a5c2e"
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  label: {
    fontSize: 13,
    color: "#888",
    fontWeight: "600",
    textTransform: "uppercase",
    marginBottom: 6,
  },
  button: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 10,
    padding: 14,
    backgroundColor: "#fafafa",
  },
  dateText: {
    flex: 1,
    fontSize: 16,
    color: "#222",
  },
});
