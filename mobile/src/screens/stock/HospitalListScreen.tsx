import React, { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import Alert from "../../utils/alert";
import { deleteHospital, fetchHospitals } from "../../api/services";
import { Hospital } from "../../types";
import { contentColumn } from "../../components/ui";
import { colors, spacing } from "../../theme";
import Icon from "../../components/Icon";
import { apiErrorMessage } from "../../api/client";
import ErrorRetry from "../../components/ErrorRetry";

export default function HospitalListScreen({ navigation }: any) {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchHospitals();
      setHospitals(data);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const filtered = useMemo(() => {
    if (!query.trim()) return hospitals;
    const lower = query.trim().toLowerCase();
    return hospitals.filter((h) => h.name.toLowerCase().includes(lower) || (h.city ?? "").toLowerCase().includes(lower));
  }, [hospitals, query]);

  function handleDelete(hospital: Hospital) {
    Alert.alert("Hastaneyi sil", `"${hospital.name}" kalıcı olarak silinecek. Emin misiniz?`, [
      { text: "Vazgeç", style: "cancel" },
      {
        text: "Sil",
        style: "destructive",
        onPress: async () => {
          setDeletingId(hospital.id);
          try {
            await deleteHospital(hospital.id);
            load();
          } catch (e) {
            Alert.alert("Silinemedi", apiErrorMessage(e));
          } finally {
            setDeletingId(null);
          }
        },
      },
    ]);
  }

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <TouchableOpacity style={styles.addButton} onPress={() => navigation.navigate("AddHospital")}>
          <Text style={styles.addButtonText}>+ Yeni Hastane</Text>
        </TouchableOpacity>

        <TextInput
          style={styles.search}
          placeholder="Hastane adı veya şehir ara"
          placeholderTextColor={colors.textMuted}
          value={query}
          onChangeText={setQuery}
        />

        {isLoading ? (
          <ActivityIndicator color={colors.primary} style={{ marginTop: spacing(4) }} />
        ) : error ? (
          <ErrorRetry message={error} onRetry={load} />
        ) : filtered.length === 0 ? (
          <Text style={styles.empty}>Hastane bulunamadı</Text>
        ) : (
          filtered.map((h) => (
            <View key={h.id} style={styles.row}>
              <TouchableOpacity style={{ flex: 1 }} onPress={() => navigation.navigate("AddHospital", { hospital: h })}>
                <Text style={styles.name}>{h.name}</Text>
                {!!h.city && <Text style={styles.city}>{h.city}</Text>}
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.deleteButton}
                onPress={() => handleDelete(h)}
                disabled={deletingId === h.id}
              >
                {deletingId === h.id ? (
                  <Text style={styles.deleteButtonText}>...</Text>
                ) : (
                  <Icon name="trash" size={16} color={colors.textMuted} />
                )}
              </TouchableOpacity>
            </View>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { ...contentColumn, padding: spacing(2) },
  addButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.5),
    alignItems: "center",
    marginBottom: spacing(2),
  },
  addButtonText: { color: "#0f172a", fontWeight: "700" },
  search: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing(2),
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: spacing(1.5),
    marginBottom: spacing(1),
    borderWidth: 1,
    borderColor: colors.border,
  },
  name: { color: colors.text, fontWeight: "700", fontSize: 14 },
  city: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  deleteButton: { paddingHorizontal: spacing(1.5), paddingVertical: spacing(1), marginLeft: spacing(1) },
  deleteButtonText: { fontSize: 18 },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(4) },
});
