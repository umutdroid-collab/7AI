import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { Invoice } from "../types";
import { colors, spacing } from "../theme";

function dueColor(days: number | null): string {
  if (days === null) return colors.textMuted;
  if (days < 0) return colors.danger;
  if (days <= 7) return colors.warning;
  return colors.success;
}

function dueLabel(days: number | null): string {
  if (days === null) return "Vade tarihi belirlenemedi";
  if (days < 0) return `Vadesi geçti (${Math.abs(days)} gün)`;
  if (days === 0) return "Vade bugün";
  return `${days} gün kaldı`;
}

export default function InvoiceCard({ invoice, onPress }: { invoice: Invoice; onPress: () => void }) {
  const isPaid = invoice.status === "paid";
  return (
    <TouchableOpacity style={styles.card} onPress={onPress}>
      <View style={styles.headerRow}>
        <Text style={styles.number} numberOfLines={1}>
          {invoice.invoice_number || invoice.source_filename}
        </Text>
        <View style={[styles.badge, { backgroundColor: isPaid ? colors.success : dueColor(invoice.days_to_due) }]}>
          <Text style={styles.badgeText}>{isPaid ? "Ödendi" : dueLabel(invoice.days_to_due)}</Text>
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
        <Text style={styles.reviewTag}>⚠ Otomatik okuma eksik, kontrol edin</Text>
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
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  number: { color: colors.text, fontSize: 15, fontWeight: "700", flex: 1, marginRight: spacing(1) },
  badge: { borderRadius: 8, paddingHorizontal: spacing(1), paddingVertical: spacing(0.5) },
  badgeText: { color: "#0f172a", fontSize: 11, fontWeight: "700" },
  counterparty: { color: colors.textMuted, fontSize: 13, marginTop: spacing(0.5) },
  footerRow: { flexDirection: "row", justifyContent: "space-between", marginTop: spacing(1.5) },
  amount: { color: colors.primary, fontWeight: "700", fontSize: 14 },
  dueDate: { color: colors.textMuted, fontSize: 13 },
  reviewTag: { color: colors.warning, fontSize: 12, marginTop: spacing(1) },
});
