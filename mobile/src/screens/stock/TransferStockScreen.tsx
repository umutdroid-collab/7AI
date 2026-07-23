import React, { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import Alert from "../../utils/alert";
import { fetchHospitals, transferStockItem } from "../../api/services";
import { Hospital } from "../../types";
import { colors, spacing } from "../../theme";
import { apiErrorMessage } from "../../api/client";
import HospitalPickerModal from "../../components/HospitalPickerModal";

type Destination = number | "depot" | "vehicle" | undefined;

export default function TransferStockScreen({ route, navigation }: any) {
  const { item } = route.params;
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [destination, setDestination] = useState<Destination>(undefined);
  const [isPickerVisible, setIsPickerVisible] = useState(false);
  const [note, setNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchHospitals().then(setHospitals).catch(() => {});
  }, []);

  const selectableHospitals = hospitals.filter((h) => h.id !== item.hospital?.id);

  async function handleConfirm() {
    if (destination === undefined) {
      Alert.alert("Hedef seçin", "Ürünü nereye taşıyacağınızı seçin");
      return;
    }
    setIsSubmitting(true);
    try {
      if (destination === "vehicle") {
        await transferStockItem(item.id, null, note || undefined, true);
      } else if (destination === "depot") {
        await transferStockItem(item.id, null, note || undefined, false);
      } else {
        await transferStockItem(item.id, destination, note || undefined, false);
      }
      Alert.alert("Başarılı", "Ürün taşındı", [{ text: "Tamam", onPress: () => navigation.goBack() }]);
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsSubmitting(false);
    }
  }

  const destinationLabel =
    destination === undefined
      ? "Hedef seçin..."
      : destination === "depot"
      ? "Depo (iade)"
      : destination === "vehicle"
      ? "🚗 Arabama Al"
      : hospitals.find((h) => h.id === destination)?.name;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{item.product.name}</Text>
      <Text style={styles.subtitle}>
        Şu an: {item.hospital ? item.hospital.name : item.carried_by ? `${item.carried_by.full_name} (araçta)` : "Depo"} — Lot{" "}
        {item.lot_no}
      </Text>

      <Text style={styles.label}>Hızlı seçim</Text>
      <View style={styles.quickRow}>
        <TouchableOpacity
          style={[styles.quickChip, destination === "vehicle" && styles.quickChipActive]}
          onPress={() => setDestination("vehicle")}
        >
          <Text style={[styles.quickChipText, destination === "vehicle" && styles.quickChipTextActive]}>
            🚗 Arabama Al
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.quickChip, destination === "depot" && styles.quickChipActive]}
          onPress={() => setDestination("depot")}
        >
          <Text style={[styles.quickChipText, destination === "depot" && styles.quickChipTextActive]}>
            Depoya İade
          </Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.label}>veya bir hastane seçin</Text>
      <TouchableOpacity style={styles.hospitalSelect} onPress={() => setIsPickerVisible(true)}>
        <Text style={typeof destination === "number" ? styles.hospitalSelectText : styles.hospitalSelectPlaceholder}>
          {typeof destination === "number" ? destinationLabel : "Hastane Seç..."}
        </Text>
        <Text style={styles.hospitalSelectChevron}>▾</Text>
      </TouchableOpacity>

      <HospitalPickerModal
        visible={isPickerVisible}
        hospitals={selectableHospitals}
        onSelect={(id) => setDestination(id === null ? "depot" : id)}
        onClose={() => setIsPickerVisible(false)}
        title="Hedef Hastane Seç"
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
        {isSubmitting ? (
          <ActivityIndicator color="#0f172a" />
        ) : (
          <Text style={styles.confirmButtonText}>
            {destination === undefined ? "Taşımayı Onayla" : `Onayla: ${destinationLabel}`}
          </Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing(2) },
  title: { color: colors.text, fontSize: 18, fontWeight: "700" },
  subtitle: { color: colors.textMuted, marginTop: 4, marginBottom: spacing(2) },
  label: { color: colors.textMuted, fontSize: 13, marginBottom: spacing(1), marginTop: spacing(1) },
  quickRow: { flexDirection: "row", gap: spacing(1) },
  quickChip: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingVertical: spacing(1.5),
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  quickChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  quickChipText: { color: colors.text, fontWeight: "600", fontSize: 13 },
  quickChipTextActive: { color: "#0f172a" },
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
