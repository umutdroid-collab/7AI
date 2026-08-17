import React from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  ViewStyle,
} from "react-native";
import { colors, layout, radius, shadow, spacing, typography } from "../theme";
import Icon, { IconName } from "./Icon";

/**
 * Tasarımda tekrar eden kontroller. Beş ekranın da aynı segment çubuğunu,
 * arama kutusunu, çipini ve hap butonunu kullanması için tek yerde duruyorlar;
 * ekranlar kendi kopyalarını tutarsa tasarım güncellemesi yine 20 dosya
 * dolaşmak demek olurdu.
 */

/** İki seçenekli segment çubuğu (Aktif Stok / Kullanım, Girişlerim / Tüm Ekip). */
export function SegmentedToggle<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <View style={styles.segmentBar}>
      {options.map((option) => {
        const active = option.value === value;
        return (
          <TouchableOpacity
            key={option.value}
            style={[styles.segment, active && styles.segmentActive]}
            onPress={() => onChange(option.value)}
            activeOpacity={0.8}
          >
            <Text style={[styles.segmentText, active && styles.segmentTextActive]}>
              {option.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

export function SearchField({
  value,
  onChangeText,
  placeholder,
  onSubmit,
}: {
  value: string;
  onChangeText: (text: string) => void;
  placeholder: string;
  onSubmit?: () => void;
}) {
  return (
    <View style={styles.searchBar}>
      <Icon name="search" size={16} color={colors.textMuted} />
      <TextInput
        style={styles.searchInput}
        placeholder={placeholder}
        placeholderTextColor={colors.textMuted}
        value={value}
        onChangeText={onChangeText}
        onSubmitEditing={onSubmit}
        returnKeyType="search"
      />
    </View>
  );
}

/** Yuvarlak filtre çipi. Aktifken camgöbeği zemin + siyah yazı. */
export function FilterChip({
  label,
  active,
  onPress,
  icon,
}: {
  label: string;
  active?: boolean;
  onPress: () => void;
  icon?: IconName;
}) {
  return (
    <TouchableOpacity
      style={[styles.chip, active && styles.chipActive]}
      onPress={onPress}
      activeOpacity={0.8}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
      {icon && <Icon name={icon} size={10} color={active ? colors.onPrimary : colors.textMuted} />}
    </TouchableOpacity>
  );
}

/** Kesikli kenarlıklı aksiyon hapı (Hastaneler ⚙, Excel'e Aktar 📄).
 *  Tasarımda ikincil eylemler filtrelerden bu şekilde ayrılıyor. */
export function ActionPill({
  label,
  icon,
  onPress,
  tone = "primary",
  loading,
}: {
  label: string;
  icon: IconName;
  onPress: () => void;
  tone?: "primary" | "success";
  loading?: boolean;
}) {
  const color = tone === "success" ? colors.success : colors.primary;
  const tint = tone === "success" ? colors.successTint : colors.primaryTint;
  return (
    <TouchableOpacity
      style={[styles.pill, { backgroundColor: tint, borderColor: color }]}
      onPress={onPress}
      disabled={loading}
      activeOpacity={0.8}
    >
      {loading ? (
        <ActivityIndicator size="small" color={color} />
      ) : (
        <>
          <Text style={[styles.pillText, { color }]}>{label}</Text>
          <Icon name={icon} size={14} color={color} />
        </>
      )}
    </TouchableOpacity>
  );
}

/** Sağ altta duran yuvarlak ekle butonu. */
export function Fab({ onPress, icon = "plus" }: { onPress: () => void; icon?: IconName }) {
  return (
    <TouchableOpacity style={styles.fab} onPress={onPress} activeOpacity={0.85}>
      <Icon name={icon} size={24} color={colors.onPrimary} />
    </TouchableOpacity>
  );
}

/**
 * Geniş ekranda içeriği ortalanmış bir sütunda tutar.
 *
 * Tasarım 402 px telefon için çizildi; masaüstü tarayıcıda (saha.7medikal.com
 * bilgisayardan da açılıyor) kartlar 2000 px'e yayılınca satırlar okunamayacak
 * kadar uzuyor ve kart içindeki hizalamalar dağılıyor. Liste ve kontrol
 * kapsayıcılarına uygulanır; alt gezinme çubuğu tam genişlikte kalmalı.
 */
export const contentColumn = {
  width: "100%",
  maxWidth: layout.maxContentWidth,
  alignSelf: "center",
} as const;

/** Yatay kaydırılabilir yerine saran satır: React Native Web'de yatay
 *  ScrollView yükseklik alamayıp görünmez olabiliyor (fatura filtre
 *  çiplerinde bizzat yaşandı). */
export function WrapRow({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[styles.wrapRow, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  segmentBar: {
    flexDirection: "row",
    height: 44,
    padding: 4,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
  },
  segment: { flex: 1, alignItems: "center", justifyContent: "center", borderRadius: radius.sm },
  segmentActive: { backgroundColor: colors.primary },
  segmentText: { ...typography.bodyStrong, color: colors.textMuted },
  segmentTextActive: { color: colors.onPrimary },

  searchBar: {
    flexDirection: "row",
    alignItems: "center",
    gap: layout.cardGap,
    height: 44,
    paddingHorizontal: layout.cardPadding,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    borderRadius: radius.md,
  },
  searchInput: { flex: 1, ...typography.body, color: colors.text },

  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: layout.cardPadding,
    paddingVertical: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { ...typography.bodyStrong, color: colors.textMuted },
  chipTextActive: { color: colors.onPrimary },

  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: layout.cardGap,
    paddingVertical: 6,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderStyle: "dashed",
  },
  pillText: typography.bodyStrong,

  fab: {
    position: "absolute",
    right: 20,
    bottom: 20,
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
    ...shadow.floating,
  },

  wrapRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing(1) },
});
