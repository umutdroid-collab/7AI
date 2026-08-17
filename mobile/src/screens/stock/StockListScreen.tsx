import React, { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import Alert from "../../utils/alert";
import { fetchHospitals, fetchStock, stockExportUrl } from "../../api/services";
import { Hospital, StockItem } from "../../types";
import { colors, layout, spacing } from "../../theme";
import StockItemCard from "../../components/StockItemCard";
import { apiErrorMessage } from "../../api/client";
import { dateStampedFilename, downloadFile } from "../../utils/download";
import { useAuth } from "../../context/AuthContext";
import HospitalPickerModal from "../../components/HospitalPickerModal";
import ErrorRetry from "../../components/ErrorRetry";
import { ActionPill, Fab, FilterChip, SearchField, SegmentedToggle, WrapRow } from "../../components/ui";

type ViewMode = "active" | "used";

export default function StockListScreen({ navigation }: any) {
  const { user } = useAuth();
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [selectedHospitalId, setSelectedHospitalId] = useState<number | "all" | "warehouse">("all");
  const [isPickerVisible, setIsPickerVisible] = useState(false);
  const [query, setQuery] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("active");
  const [items, setItems] = useState<StockItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  useFocusEffect(
    useCallback(() => {
      fetchHospitals().then(setHospitals).catch(() => {});
    }, [])
  );

  const buildParams = useCallback(() => {
    const params: any = { q: query || undefined };
    if (viewMode === "used") {
      params.status = "used";
    }
    if (selectedHospitalId === "warehouse") {
      // Depodaki ürünler: hospital_id backend'de sorgulanamıyor (null filtre), istemci tarafında filtrele
    } else if (selectedHospitalId !== "all") {
      params.hospital_id = selectedHospitalId;
    }
    return params;
  }, [query, selectedHospitalId, viewMode]);

  const load = useCallback(async () => {
    setError(null);
    try {
      const params = buildParams();
      const data = await fetchStock(params);
      const filtered = selectedHospitalId === "warehouse" ? data.filter((i) => !i.hospital) : data;
      setItems(filtered);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, [buildParams, selectedHospitalId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handleExportExcel() {
    setIsExporting(true);
    try {
      await downloadFile(stockExportUrl(buildParams()), dateStampedFilename("stok-raporu", "xlsx"));
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.controls}>
        <SegmentedToggle
          value={viewMode}
          onChange={setViewMode}
          options={[
            { value: "active", label: "Aktif Stok" },
            { value: "used", label: "Kullanım" },
          ]}
        />

        <SearchField
          value={query}
          onChangeText={setQuery}
          onSubmit={load}
          placeholder="Ref no, ÜBB no, lot no veya seri no ile ara"
        />

        <WrapRow>
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
          <FilterChip
            label={
              typeof selectedHospitalId === "number"
                ? hospitals.find((h) => h.id === selectedHospitalId)?.name ?? "Hastane"
                : "Hastane Seç"
            }
            active={typeof selectedHospitalId === "number"}
            icon="chevronDown"
            onPress={() => setIsPickerVisible(true)}
          />
        </WrapRow>

        <WrapRow>
          {user?.role === "admin" && (
            <>
              <ActionPill
                label="Hastaneler"
                icon="settings"
                onPress={() => navigation.navigate("HospitalList")}
              />
              <ActionPill
                label="Ürünler"
                icon="settings"
                onPress={() => navigation.navigate("ProductList")}
              />
            </>
          )}
          <ActionPill
            label="Excel'e Aktar"
            icon="file"
            tone="success"
            loading={isExporting}
            onPress={handleExportExcel}
          />
        </WrapRow>
      </View>

      <HospitalPickerModal
        visible={isPickerVisible}
        hospitals={hospitals}
        onSelect={(id) => setSelectedHospitalId(id ?? "all")}
        onClose={() => setIsPickerVisible(false)}
        title="Hastaneye Göre Filtrele"
      />

      {isLoading ? (
        <ActivityIndicator style={{ marginTop: spacing(4) }} color={colors.primary} />
      ) : error ? (
        <ErrorRetry message={error} onRetry={load} />
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={colors.primary} />}
          ListEmptyComponent={
            <Text style={styles.empty}>
              {viewMode === "used" ? "Henüz kullanılan ürün yok" : "Kayıt bulunamadı"}
            </Text>
          }
          renderItem={({ item }) => (
            <StockItemCard item={item} onPress={() => navigation.navigate("StockDetail", { stockItemId: item.id })} />
          )}
        />
      )}

      {viewMode === "active" && user?.role === "admin" && (
        <Fab onPress={() => navigation.navigate("AddStock")} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  controls: {
    padding: layout.screenPadding,
    gap: layout.cardGap,
  },
  list: { paddingHorizontal: layout.screenPadding, paddingBottom: spacing(10) },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(4) },
});
