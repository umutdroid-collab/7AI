import React, { useEffect, useState } from "react";
import { Alert, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { fetchHospitals, transferStockItem } from "../../api/services";
import { Hospital } from "../../types";
import { colors, spacing } from "../../theme";
import { apiErrorMessage } from "../../api/client";
import HospitalPickerModal from "../../components/HospitalPickerModal";

export default function TransferStockScreen({ route, navigation }: any) {
  const { item } = route.params;
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [selectedId, setSelectedId] = useState<number | null | undefined>(undefined);
  const [isPickerVisible, setIsPickerVisible] = useState(false);
  const [note, setNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchHospitals().then(setHospitals).catch(() => {});
  }, []);

  const selectableHospitals = hospitals.filter((h) => h.id !== item.hospital?.id);

  async function handleConfirm() {
    if (selectedId === undefined) {
      Alert.alert("Hedef seçin", "Ürünü nereye taşıyacağınızı seçin");
      return;
    }
    setIsSubmitting(true);
    try {
      await transferStockItem(item.id, selectedId, note || undefined);
      Alert.alert("Başarılı", "Ürün taşındı", [{ text: "Tamam", onPress: () => navigation.goBack() }]);
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{item.product.name}</Text>
      <Text style={styles.subtitle}>
        Şu an: {item.hospital ? item.hospital.name : "Depo"} — Lot {item.lot_no}
      </Text>

      <Text style={styles.label}>Hedef konum</Text>
      <TouchableOpacity style={styles.hospitalSelect} onPress={() => setIsPickerVisible(true)}>
        <Text style={selectedId === undefined ? styles.hospitalSelectPlaceholder : styles.hospitalSelectText}>
          {selectedId === undefined
            ? "Hedef seçin..."
            : selectedId === null
            ? "Depo (iade)"
            : hospitals.find((h) => h.id === selectedId)?.name}
        </Text>
        <Text style={styles.hospitalSelectChevron}>▾</Text>
      </TouchableOpacity>

      <HospitalPickerModal
        visible={isPickerVisible}
        hospitals={selectableHospitals}
        onSelect={setSelectedId}
        onClose={() => setIsPickerVisible(false)}
        extraOptions={[{ id: null, name: "Depo (iade)" }]}
        title="Hedef Konum Seç"
      />

      <Text style={styles.label}>Not (opsiyonel)</Text>
      <TextInput
        style={styles.input}
        value={note}
        onChangeText={setNote}
        placeholder="Örn. Dr. Ahmet'e teslim edildi"
        placeholderTextColor={colors.textMuted}
      />

      <TouchableOpacity
        style={[styles.confirmButton, isSubmitting && { opacity: 0.6 }]}
        onPress={handleConfirm}
        disabled={isSubmitting}
      >
        <Text style={styles.confirmButtonText}>Taşımayı Onayla</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing(2) },
  title: { color: colors.text, fontSize: 18, fontWeight: "700" },
  subtitle: { color: colors.textMuted, marginTop: 4, marginBottom: spacing(2) },
  label: { color: colors.textMuted, fontSize: 13, marginBottom: spacing(1), marginTop: spacing(1) },
  hospitalSelect: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.border,
  },
  hospitalSelectText: { color: colors.text, fontSize: 14, fontWeight: "600" },
  hospitalSelectPlaceholder: { color: colors.textMuted, fontSize: 14 },
  hospitalSelectChevron: { color: colors.textMuted },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  confirmButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
    marginTop: spacing(3),
  },
  confirmButtonText: { color: "#0f172a", fontWeight: "700" },
});
