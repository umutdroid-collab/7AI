import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity } from "react-native";
import Alert from "../../utils/alert";
import { createHospital, updateHospital } from "../../api/services";
import { apiErrorMessage } from "../../api/client";
import { contentColumn } from "../../components/ui";
import { colors, spacing } from "../../theme";
import { Hospital } from "../../types";

export default function AddHospitalScreen({ navigation, route }: any) {
  const editingHospital: Hospital | undefined = route.params?.hospital;

  const [name, setName] = useState(editingHospital?.name ?? "");
  const [city, setCity] = useState(editingHospital?.city ?? "");
  const [address, setAddress] = useState(editingHospital?.address ?? "");
  const [contactPerson, setContactPerson] = useState(editingHospital?.contact_person ?? "");
  const [contactPhone, setContactPhone] = useState(editingHospital?.contact_phone ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    navigation.setOptions({ title: editingHospital ? "Hastaneyi Düzenle" : "Yeni Hastane" });
  }, [navigation, editingHospital]);

  async function handleSubmit() {
    if (!name.trim()) {
      Alert.alert("Eksik bilgi", "Hastane adı zorunludur");
      return;
    }
    setIsSubmitting(true);
    try {
      const payload = {
        name: name.trim(),
        city: city || undefined,
        address: address || undefined,
        contact_person: contactPerson || undefined,
        contact_phone: contactPhone || undefined,
      };
      if (editingHospital) {
        await updateHospital(editingHospital.id, payload);
        Alert.alert("Başarılı", "Hastane güncellendi", [{ text: "Tamam", onPress: () => navigation.goBack() }]);
      } else {
        await createHospital(payload);
        Alert.alert("Başarılı", "Hastane eklendi", [{ text: "Tamam", onPress: () => navigation.goBack() }]);
      }
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
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
        {isSubmitting ? (
          <ActivityIndicator color="#0f172a" />
        ) : (
          <Text style={styles.submitText}>{editingHospital ? "Güncelle" : "Kaydet"}</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { ...contentColumn, padding: spacing(2) },
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
