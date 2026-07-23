import React, { useMemo, useState } from "react";
import { FlatList, Modal, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { Hospital } from "../types";
import { colors, spacing } from "../theme";

interface PickerOption {
  id: number | null;
  name: string;
}

export default function HospitalPickerModal({
  visible,
  hospitals,
  onSelect,
  onClose,
  extraOptions,
  title = "Hastane Seç",
}: {
  visible: boolean;
  hospitals: Hospital[];
  onSelect: (id: number | null) => void;
  onClose: () => void;
  extraOptions?: PickerOption[];
  title?: string;
}) {
  const [query, setQuery] = useState("");

  const options: PickerOption[] = useMemo(() => {
    const base = [...(extraOptions ?? []), ...hospitals.map((h) => ({ id: h.id, name: h.name }))];
    if (!query.trim()) return base;
    const lower = query.trim().toLowerCase();
    return base.filter((o) => o.name.toLowerCase().includes(lower));
  }, [hospitals, extraOptions, query]);

  function handleSelect(id: number | null) {
    setQuery("");
    onSelect(id);
    onClose();
  }

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <View style={styles.headerRow}>
            <Text style={styles.title}>{title}</Text>
            <TouchableOpacity onPress={onClose}>
              <Text style={styles.closeText}>Kapat</Text>
            </TouchableOpacity>
          </View>

          <TextInput
            style={styles.search}
            placeholder="Hastane ara..."
            placeholderTextColor={colors.textMuted}
            value={query}
            onChangeText={setQuery}
            autoFocus
          />

          <FlatList
            data={options}
            keyExtractor={(o) => String(o.id)}
            keyboardShouldPersistTaps="handled"
            ListEmptyComponent={<Text style={styles.empty}>Sonuç bulunamadı</Text>}
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.option} onPress={() => handleSelect(item.id)}>
                <Text style={styles.optionText}>{item.name}</Text>
              </TouchableOpacity>
            )}
          />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", justifyContent: "flex-end" },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: spacing(2),
    maxHeight: "80%",
    minHeight: "50%",
  },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing(1.5) },
  title: { color: colors.text, fontSize: 16, fontWeight: "700" },
  closeText: { color: colors.primary, fontWeight: "600" },
  search: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing(1.5),
  },
  option: {
    paddingVertical: spacing(1.5),
    paddingHorizontal: spacing(1),
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  optionText: { color: colors.text, fontSize: 15 },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(3) },
});
