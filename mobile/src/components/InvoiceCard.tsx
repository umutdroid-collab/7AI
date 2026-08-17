import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Invoice } from "../types";
import { colors, layout, radius, spacing, typography } from "../theme";

/** Rozet, tasarımda dolu zemin değil renkli metin + soluk zemin. */
function dueTone(days: number | null): { color: string; tint: string } {
  if (days === null) return { color: colors.textMuted, tint: colors.card };
  if (days < 0) return { color: colors.danger, tint: colors.dangerTint };
  if (days <= 7) return { color: colors.warning, tint: colors.warningTint };
  return { color: colors.success, tint: colors.successTint };
}

function dueLabel(days: number | null): string {
  if (days === null) return "Vade tarihi belirlenemedi";
  if (days < 0) return `Vadesi geçti (${Math.abs(days)} gün)`;
  if (days === 0) return "Vade bugün";
  return `${days} gün kaldı`;
}

export default function InvoiceCard({ invoice, onPress }: { invoice: Invoice; onPress: () => void }) {
  const isPaid = invoice.status === "paid";
  const tone = isPaid ? { color: colors.success, tint: colors.successTint } : dueTone(invoice.days_to_due);

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.8}>
      <View style={styles.headerRow}>
        <Text style={styles.number} numberOfLines={1}>
          {invoice.invoice_number || invoice.source_filename}
        </Text>
        <View style={[styles.badge, { backgroundColor: tone.tint }]}>
          <Text style={[styles.badgeText, { color: tone.color }]}>
            {isPaid ? "Ödendi" : dueLabel(invoice.days_to_due)}
          </Text>
        </View>
      </View>

      <Text style={styles.counterparty} numberOfLines={1}>
        {invoice.counterparty || "Tedarikçi bilgisi yok"}
      </Text>

      <View style={styles.footerRow}>
        <Text style={styles.amount}>
          {invoice.amount ? `${invoice.amount.toLocaleString("tr-TR")} ${invoice.currency}` : "Tutar bilinmiyor"}
        </Text>
        <Text style={styles.dueDate}>{invoice.due_date || "-"}</Text>
      </View>

      {invoice.status === "needs_review" && (
        <Text style={styles.reviewTag}>Otomatik okuma eksik, kontrol edin</Text>
      )}
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
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: spacing(1),
  },
  number: { ...typography.cardTitle, color: colors.text, flex: 1 },
  badge: { borderRadius: radius.sm, paddingHorizontal: 10, paddingVertical: 4 },
  badgeText: typography.badge,
  counterparty: { ...typography.body, color: colors.textMuted, marginTop: layout.cardGap },
  footerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: layout.cardGap,
  },
  amount: { color: colors.primary, fontSize: 16, fontWeight: "700" },
  dueDate: { ...typography.meta, color: colors.textMuted },
  reviewTag: { ...typography.meta, color: colors.warning, marginTop: spacing(1) },
});
