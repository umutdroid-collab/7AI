import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { StockItem } from "../types";
import { colors, spacing } from "../theme";

function expiryColor(days: number | null): string {
  if (days === null) return colors.textMuted;
  if (days < 0) return colors.danger;
  if (days <= 30) return colors.danger;
  if (days <= 90) return colors.warning;
  return colors.success;
}

function expiryLabel(days: number | null): string {
  if (days === null) return "SKT bilinmiyor";
  if (days < 0) return `SKT geçti (${Math.abs(days)} gün önce)`;
  if (days === 0) return "SKT bugün doluyor";
  return `SKT: ${days} gün kaldı`;
}

function locationLabel(item: StockItem): string {
  if (item.hospital) return item.hospital.name;
  if (item.carried_by) return `🚗 ${item.carried_by.full_name} (araçta)`;
  return "Depo";
}

export default function StockItemCard({ item, onPress }: { item: StockItem; onPress: () => void }) {
  const isUsed = item.status === "used";

  return (
    <TouchableOpacity style={styles.card} onPress={onPress}>
      <View style={styles.headerRow}>
        <Text style={styles.name} numberOfLines={1}>
          {item.product.name}
        </Text>
        {isUsed ? (
          <View style={[styles.badge, { backgroundColor: colors.textMuted }]}>
            <Text style={styles.badgeText}>Kullanıldı</Text>
          </View>
        ) : (
          <View style={[styles.badge, { backgroundColor: expiryColor(item.days_to_expiry) }]}>
            <Text style={styles.badgeText}>{expiryLabel(item.days_to_expiry)}</Text>
          </View>
        )}
      </View>

      <Text style={styles.meta}>
        Ref: {item.product.reference_no}
        {item.product.ubb_no ? `  •  ÜBB: ${item.product.ubb_no}` : ""}
      </Text>
      <Text style={styles.meta}>
        Lot: {item.lot_no}
        {item.serial_no ? `  •  Seri: ${item.serial_no}` : ""}
      </Text>

      {isUsed ? (
        <>
          <Text style={styles.location}>🏥 Kullanıldığı yer: {locationLabel(item)}</Text>
          <Text style={styles.meta}>
            Kullanım tarihi: {new Date(item.updated_at).toLocaleDateString("tr-TR")}
          </Text>
        </>
      ) : (
        <Text style={styles.location}>📍 {locationLabel(item)}</Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing(2),
    marginBottom: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.border,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: spacing(1),
  },
  name: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "700",
    flex: 1,
    marginRight: spacing(1),
  },
  badge: {
    borderRadius: 8,
    paddingHorizontal: spacing(1),
    paddingVertical: spacing(0.5),
  },
  badgeText: {
    color: "#0f172a",
    fontSize: 11,
    fontWeight: "700",
  },
  meta: {
    color: colors.textMuted,
    fontSize: 13,
    marginTop: 2,
  },
  location: {
    color: colors.primary,
    fontSize: 13,
    marginTop: spacing(1),
    fontWeight: "600",
  },
});
