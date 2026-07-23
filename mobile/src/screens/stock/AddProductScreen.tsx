import React, { useState } from "react";
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity } from "react-native";
import { createProduct } from "../../api/services";
import { apiErrorMessage } from "../../api/client";
import { colors, spacing } from "../../theme";

export default function AddProductScreen({ navigation }: any) {
  const [name, setName] = useState("");
  const [referenceNo, setReferenceNo] = useState("");
  const [ubbNo, setUbbNo] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [unit, setUnit] = useState("");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    if (!name.trim() || !referenceNo.trim()) {
      Alert.alert("Eksik bilgi", "Ürün adı ve ref numarası zorunludur");
      return;
    }
    setIsSubmitting(true);
    try {
      const product = await createProduct({
        name: name.trim(),
        reference_no: referenceNo.trim(),
        ubb_no: ubbNo || undefined,
        manufacturer: manufacturer || undefined,
        unit: unit || undefined,
        notes: notes || undefined,
      });
      navigation.navigate("AddStock", { newProduct: product });
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing(2) }}>
      <Text style={styles.label}>Ürün adı</Text>
      <TextInput style={styles.input} value={name} onChangeText={setName} placeholderTextColor={colors.textMuted} />

      <Text style={styles.label}>Ref numarası</Text>
      <TextInput
        style={styles.input}
        value={referenceNo}
        onChangeText={setReferenceNo}
        placeholderTextColor={colors.textMuted}
      />

      <Text style={styles.label}>ÜBB numarası</Text>
      <TextInput style={styles.input} value={ubbNo} onChangeText={setUbbNo} placeholderTextColor={colors.textMuted} />

      <Text style={styles.label}>Üretici</Text>
      <TextInput
        style={styles.input}
        value={manufacturer}
        onChangeText={setManufacturer}
        placeholderTextColor={colors.textMuted}
      />

      <Text style={styles.label}>Birim</Text>
      <TextInput style={styles.input} value={unit} onChangeText={setUnit} placeholderTextColor={colors.textMuted} />

      <Text style={styles.label}>Notlar</Text>
      <TextInput style={styles.input} value={notes} onChangeText={setNotes} placeholderTextColor={colors.textMuted} />

      <TouchableOpacity style={styles.submit} onPress={handleSubmit} disabled={isSubmitting}>
        {isSubmitting ? <ActivityIndicator color="#0f172a" /> : <Text style={styles.submitText}>Kaydet</Text>}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  label: { color: colors.textMuted, fontSize: 13, marginBottom: spacing(1), marginTop: spacing(1.5) },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  submit: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
    marginTop: spacing(3),
    marginBottom: spacing(4),
  },
  submitText: { color: "#0f172a", fontWeight: "700" },
});
