import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { colors, spacing } from "../theme";

export default function ErrorRetry({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View style={styles.container}>
      <Text style={styles.message}>{message}</Text>
      <TouchableOpacity style={styles.button} onPress={onRetry}>
        <Text style={styles.buttonText}>Tekrar Dene</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: "center", marginTop: spacing(4) },
  message: { color: colors.danger, textAlign: "center", marginBottom: spacing(1.5) },
  button: {
    borderRadius: 10,
    paddingHorizontal: spacing(2.5),
    paddingVertical: spacing(1.25),
    borderWidth: 1,
    borderColor: colors.primary,
  },
  buttonText: { color: colors.primary, fontWeight: "700", fontSize: 13 },
});
