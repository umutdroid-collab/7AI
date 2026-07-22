import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { fetchHospitals, fetchStock } from "../../api/services";
import { Hospital, StockItem } from "../../types";
import { colors, spacing } from "../../theme";
import StockItemCard from "../../components/StockItemCard";
import { apiErrorMessage } from "../../api/client";

export default function StockListScreen({ navigation }: any) {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [selectedHospitalId, setSelectedHospitalId] = useState<number | "all" | "warehouse">("all");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<StockItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHospitals().then(setHospitals).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      const params: any = { q: query || undefined };
      if (selectedHospitalId === "warehouse") {
        // Depodaki ürünler: hospital_id backend'de sorgulanamıyor (null filtre), istemci tarafında filtrele
      } else if (selectedHospitalId !== "all") {
        params.hospital_id = selectedHospitalId;
      }
      const data = await fetchStock(params);
      const filtered = selectedHospitalId === "warehouse" ? data.filter((i) => !i.hospital) : data;
      setItems(filtered);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, [query, selectedHospitalId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.search}
        placeholder="Ref no, ÜBB no, lot no veya seri no ile ara"
        placeholderTextColor={colors.textMuted}
        value={query}
        onChangeText={setQuery}
        onSubmitEditing={load}
        returnKeyType="search"
      />

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipsRow}>
        <FilterChip
          label="Tümü"
          active={selectedHospitalId === "all"}
          onPress={() => setSelectedHospitalId("all")}
        />
        <FilterChip
          label="Depo"
          active={selectedHospitalId === "warehouse"}
          onPress={() => setSelectedHospitalId("warehouse")}
        />
        {hospitals.map((h) => (
          <FilterChip
            key={h.id}
            label={h.name}
            active={selectedHospitalId === h.id}
            onPress={() => setSelectedHospitalId(h.id)}
          />
        ))}
      </ScrollView>

      {isLoading ? (
        <ActivityIndicator style={{ marginTop: spacing(4) }} color={colors.primary} />
      ) : error ? (
        <Text style={styles.error}>{error}</Text>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={{ padding: spacing(2) }}
          refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={colors.primary} />}
          ListEmptyComponent={<Text style={styles.empty}>Kayıt bulunamadı</Text>}
          renderItem={({ item }) => (
            <StockItemCard item={item} onPress={() => navigation.navigate("StockDetail", { stockItemId: item.id })} />
          )}
        />
      )}

      <TouchableOpacity style={styles.fab} onPress={() => navigation.navigate("AddStock")}>
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>
    </View>
  );
}

function FilterChip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity style={[styles.chip, active && styles.chipActive]} onPress={onPress}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  search: {
    margin: spacing(2),
    marginBottom: spacing(1),
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipsRow: { paddingHorizontal: spacing(2), marginBottom: spacing(1), flexGrow: 0 },
  chip: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1),
    marginRight: spacing(1),
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textMuted, fontSize: 13, fontWeight: "600" },
  chipTextActive: { color: "#0f172a" },
  error: { color: colors.danger, textAlign: "center", marginTop: spacing(4) },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(4) },
  fab: {
    position: "absolute",
    right: spacing(3),
    bottom: spacing(3),
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
    elevation: 4,
  },
  fabText: { fontSize: 28, color: "#0f172a", fontWeight: "700", marginTop: -2 },
});
