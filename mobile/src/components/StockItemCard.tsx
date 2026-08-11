import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { StockItem } from "../types";
import { colors, layout, radius, spacing, typography } from "../theme";
import Icon from "./Icon";

/** Rozet, tasarımda dolu zemin değil renkli metin + soluk zemin (tint) olarak
 *  duruyor; okunabilirliği koyu temada belirgin şekilde daha iyi. */
function expiryTone(days: number | null): { color: string; tint: string } {
  if (days === null) return { color: colors.textMuted, tint: colors.card };
  if (days <= 30) return { color: colors.danger, tint: colors.dangerTint };
  if (days <= 90) return { color: colors.warning, tint: colors.warningTint };
  return { color: colors.success, tint: colors.successTint };
}

function expiryLabel(days: number | null): string {
  if (days === null) return "SKT bilinmiyor";
  if (days < 0) return `SKT geçti (${Math.abs(days)} gün önce)`;
  if (days === 0) return "SKT bugün doluyor";
  return `SKT: ${days} gün kaldı`;
}

function locationLabel(item: StockItem): string {
  if (item.hospital) return item.hospital.name;
  if (item.carried_by) return `${item.carried_by.full_name} (araçta)`;
  return "Depo";
}

/** Tasarımdaki meta satırı: değerler arasında soluk bir nokta ayraç var. */
function MetaRow({ parts }: { parts: string[] }) {
  return (
    <View style={styles.metaRow}>
      {parts.map((part, index) => (
        <React.Fragment key={part + index}>
          {index > 0 && <Text style={styles.metaSeparator}>•</Text>}
          <Text style={styles.meta}>{part}</Text>
        </React.Fragment>
      ))}
    </View>
  );
}

export default function StockItemCard({ item, onPress }: { item: StockItem; onPress: () => void }) {
  const isUsed = item.status === "used";
  const tone = expiryTone(item.days_to_expiry);

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.8}>
      <View style={styles.headerRow}>
        <Text style={styles.name} numberOfLines={1}>
          {item.product.name}
        </Text>
        <View style={[styles.badge, { backgroundColor: isUsed ? colors.card : tone.tint }]}>
          <Text style={[styles.badgeText, { color: isUsed ? colors.textMuted : tone.color }]}>
            {isUsed ? "Kullanıldı" : expiryLabel(item.days_to_expiry)}
          </Text>
        </View>
      </View>

      <View style={styles.metaGrid}>
        <MetaRow
          parts={[
            `Ref: ${item.product.reference_no}`,
            `ÜBB: ${item.product.ubb_no || "(boş)"}`,
            ...(item.product.sut_kodu ? [`SUT: ${item.product.sut_kodu}`] : []),
          ]}
        />
        <MetaRow parts={[`Lot: ${item.lot_no || "(boş)"}`, `Seri: ${item.serial_no || "(boş)"}`]} />
        {isUsed && (
          <MetaRow
            parts={[`Kullanım: ${new Date(item.updated_at).toLocaleDateString("tr-TR")}`]}
          />
        )}
      </View>

      <View style={styles.locationRow}>
        <Icon name={isUsed ? "hospital" : "location"} size={14} color={colors.primary} />
        <Text style={styles.location} numberOfLines={1}>
          {locationLabel(item)}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    padding: layout.cardPadding,
    marginBottom: layout.cardGap,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    gap: layout.cardGap,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: spacing(1),
  },
  name: {
    ...typography.cardTitle,
    color: colors.text,
    flex: 1,
  },
  badge: {
    borderRadius: radius.sm,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  badgeText: typography.badge,
  metaGrid: { gap: 4 },
  metaRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing(1) },
  meta: { ...typography.meta, color: colors.textMuted },
  metaSeparator: { ...typography.meta, color: colors.textDim },
  locationRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  location: { ...typography.bodyStrong, color: colors.primary, flexShrink: 1 },
});
