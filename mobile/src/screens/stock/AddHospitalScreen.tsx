import React, { useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity } from "react-native";
import Alert from "../../utils/alert";
import { createHospital } from "../../api/services";
import { apiErrorMessage } from "../../api/client";
import { colors, spacing } from "../../theme";

export default function AddHospitalScreen({ navigation }: any) {
  const [name, setName] = useState("");
  const [city, setCity] = useState("");
  const [address, setAddress] = useState("");
  const [contactPerson, setContactPerson] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    if (!name.trim()) {
      Alert.alert("Eksik bilgi", "Hastane adı zorunludur");
      return;
    }
    setIsSubmitting(true);
    try {
      await createHospital({
        name: name.trim(),
        city: city || undefined,
        address: address || undefined,
        contact_person: contactPerson || undefined,
        contact_phone: contactPhone || undefined,
      });
      Alert.alert("Başarılı", "Hastane eklendi", [{ text: "Tamam", onPress: () => navigation.goBack() }]);
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing(2) }}>
      <Text style={styles.label}>Hastane adı</Text>
      <TextInput style={styles.input} value={name} onChangeText={setName} placeholderTextColor={colors.textMuted} />

      <Text style={styles.label}>Şehir</Text>
      <TextInput style={styles.input} value={city} onChangeText={setCity} placeholderTextColor={colors.textMuted} />

      <Text style={styles.label}>Adres</Text>
      <TextInput style={styles.input} value={address} onChangeText={setAddress} placeholderTextColor={colors.textMuted} />

      <Text style={styles.label}>Yetkili kişi</Text>
      <TextInput
        style={styles.input}
        value={contactPerson}
        onChangeText={setContactPerson}
        placeholderTextColor={colors.textMuted}
      />

      <Text style={styles.label}>Yetkili telefon</Text>
      <TextInput
        style={styles.input}
        value={contactPhone}
        onChangeText={setContactPhone}
        keyboardType="phone-pad"
        placeholderTextColor={colors.textMuted}
      />

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
