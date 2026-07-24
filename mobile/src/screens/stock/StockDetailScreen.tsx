import React, { useCallback, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import Alert from "../../utils/alert";
import { useFocusEffect } from "@react-navigation/native";
import { fetchStock, fetchStockHistory, markStockItemUsed } from "../../api/services";
import { StockItem, StockMovement } from "../../types";
import { colors, spacing } from "../../theme";
import { apiErrorMessage } from "../../api/client";

const MOVEMENT_LABELS: Record<string, string> = {
  dispatch: "Depodan çıkış",
  transfer: "Hastaneler arası taşıma",
  return: "Depoya iade",
  use: "Hastada kullanıldı",
  adjustment: "Manuel düzeltme",
  vehicle_pickup: "Araca alındı",
};

function locationLabel(item: StockItem): string {
  if (item.hospital) return item.hospital.name;
  if (item.carried_by) return `🚗 ${item.carried_by.full_name} (araçta)`;
  return "Depo";
}

export default function StockDetailScreen({ route, navigation }: any) {
  const { stockItemId } = route.params;
  const [item, setItem] = useState<StockItem | null>(null);
  const [history, setHistory] = useState<StockMovement[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [items, movements] = await Promise.all([
        fetchStock({ include_used: true }),
        fetchStockHistory(stockItemId),
      ]);
      const found = items.find((i) => i.id === stockItemId) ?? null;
      setItem(found);
      setHistory(movements);
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, [stockItemId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handleMarkUsed() {
    Alert.alert("Kullanıldı olarak işaretle", "Bu ürün hastada kullanıldı mı?", [
      { text: "Vazgeç", style: "cancel" },
      {
        text: "Evet, kullanıldı",
        onPress: async () => {
          try {
            await markStockItemUsed(stockItemId);
            load();
          } catch (e) {
            Alert.alert("Hata", apiErrorMessage(e));
          }
        },
      },
    ]);
  }

  if (isLoading || !item) {
    return <ActivityIndicator style={{ marginTop: spacing(4) }} color={colors.primary} />;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing(2) }}>
      <Text style={styles.title}>{item.product.name}</Text>
      <View style={styles.infoBox}>
        <InfoRow label="Ref numarası" value={item.product.reference_no} />
        <InfoRow label="ÜBB numarası" value={item.product.ubb_no || "-"} />
        <InfoRow label="SUT kodu" value={item.product.sut_kodu || "-"} />
        <InfoRow label="Lot numarası" value={item.lot_no} />
        <InfoRow label="Seri numarası" value={item.serial_no || "-"} />
        <InfoRow label="SKT" value={item.skt} />
        <InfoRow label="Miktar" value={String(item.quantity)} />
        <InfoRow label="Mevcut konum" value={locationLabel(item)} />
        <InfoRow label="Durum" value={item.status} />
      </View>

      <View style={styles.actionsRow}>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => navigation.navigate("TransferStock", { item })}
        >
          <Text style={styles.primaryButtonText}>
            {item.status === "used" ? "Kullanımı Geri Al (Hastaneye/Depoya Taşı)" : "Taşı / Hastane Değiştir"}
          </Text>
        </TouchableOpacity>
        {item.status !== "used" && (
          <TouchableOpacity style={styles.secondaryButton} onPress={handleMarkUsed}>
            <Text style={styles.secondaryButtonText}>Kullanıldı Olarak İşaretle</Text>
          </TouchableOpacity>
        )}
      </View>

      <Text style={styles.sectionTitle}>Hareket Geçmişi</Text>
      {history.length === 0 ? (
        <Text style={styles.empty}>Hareket kaydı yok</Text>
      ) : (
        history
          .slice()
          .reverse()
          .map((m) => (
            <View key={m.id} style={styles.historyRow}>
              <Text style={styles.historyType}>{MOVEMENT_LABELS[m.movement_type] || m.movement_type}</Text>
              <Text style={styles.historyDate}>{new Date(m.moved_at).toLocaleString("tr-TR")}</Text>
              {m.note ? <Text style={styles.historyNote}>{m.note}</Text> : null}
            </View>
          ))
      )}
    </ScrollView>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  title: { color: colors.text, fontSize: 20, fontWeight: "700", marginBottom: spacing(2) },
  infoBox: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing(2),
    borderWidth: 1,
    borderColor: colors.border,
  },
  infoRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing(0.75),
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  infoLabel: { color: colors.textMuted, fontSize: 13 },
  infoValue: { color: colors.text, fontSize: 13, fontWeight: "600" },
  actionsRow: { marginTop: spacing(2), gap: spacing(1.5) },
  primaryButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
  },
  primaryButtonText: { color: "#0f172a", fontWeight: "700" },
  secondaryButton: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  secondaryButtonText: { color: colors.text, fontWeight: "600" },
  sectionTitle: { color: colors.text, fontSize: 16, fontWeight: "700", marginTop: spacing(3), marginBottom: spacing(1) },
  historyRow: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: spacing(1.5),
    marginBottom: spacing(1),
    borderWidth: 1,
    borderColor: colors.border,
  },
  historyType: { color: colors.text, fontWeight: "700", fontSize: 13 },
  historyDate: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  historyNote: { color: colors.textMuted, fontSize: 12, marginTop: 4, fontStyle: "italic" },
  empty: { color: colors.textMuted },
});
