import React, { useCallback, useState } from "react";
import { ActivityIndicator, Platform, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import Alert from "../../utils/alert";
import { useFocusEffect } from "@react-navigation/native";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import secureStorage from "../../utils/secureStorage";
import { api, apiErrorMessage, API_BASE_URL, TOKEN_KEY } from "../../api/client";
import { fetchInvoice, invoicePdfUrl, updateInvoiceStatus } from "../../api/services";
import { Invoice } from "../../types";
import { colors, spacing } from "../../theme";
import { useAuth } from "../../context/AuthContext";

const STATUS_LABELS: Record<string, string> = {
  parsed: "Okundu",
  needs_review: "Kontrol Gerekli",
  paid: "Ödendi",
  overdue: "Vadesi Geçti",
  upcoming: "Yaklaşıyor",
  open: "Açık",
};

export default function InvoiceDetailScreen({ route }: any) {
  const { user } = useAuth();
  const { invoiceId } = route.params;
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await fetchInvoice(invoiceId);
      setInvoice(data);
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, [invoiceId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handleDownload() {
    if (!invoice) return;
    setIsDownloading(true);
    try {
      if (Platform.OS === "web") {
        const response = await api.get(invoicePdfUrl(invoice.id), { responseType: "blob" });
        const blobUrl = URL.createObjectURL(response.data as Blob);
        const link = document.createElement("a");
        link.href = blobUrl;
        link.download = invoice.source_filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(blobUrl);
      } else {
        const token = await secureStorage.getItemAsync(TOKEN_KEY);
        const localUri = `${FileSystem.cacheDirectory}${invoice.source_filename}`;
        const result = await FileSystem.downloadAsync(`${API_BASE_URL}${invoicePdfUrl(invoice.id)}`, localUri, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(result.uri, { mimeType: "application/pdf" });
        } else {
          Alert.alert("İndirildi", `PDF kaydedildi: ${result.uri}`);
        }
      }
    } catch (e) {
      Alert.alert("Hata", "PDF indirilemedi");
    } finally {
      setIsDownloading(false);
    }
  }

  async function handleToggleStatus() {
    if (!invoice) return;
    const nextStatus = invoice.status === "paid" ? "parsed" : "paid";
    setIsUpdatingStatus(true);
    try {
      const updated = await updateInvoiceStatus(invoice.id, nextStatus);
      setInvoice(updated);
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsUpdatingStatus(false);
    }
  }

  if (isLoading || !invoice) {
    return <ActivityIndicator style={{ marginTop: spacing(4) }} color={colors.primary} />;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing(2) }}>
      <Text style={styles.title}>{invoice.invoice_number || invoice.source_filename}</Text>

      <View style={styles.infoBox}>
        <InfoRow label="Fatura tarihi" value={invoice.invoice_date || "-"} />
        <InfoRow label="Vade tarihi" value={invoice.due_date || "-"} />
        <InfoRow
          label="Tutar"
          value={invoice.amount ? `${invoice.amount.toLocaleString("tr-TR")} ${invoice.currency}` : "-"}
        />
        <InfoRow label="Tedarikçi / Firma" value={invoice.counterparty || "-"} />
        <InfoRow label="Kaynak dosya" value={invoice.source_filename} truncate />
        <InfoRow label="Durum" value={STATUS_LABELS[invoice.status] ?? invoice.status} />
        <InfoRow label="Otomatik okuma güveni" value={`%${Math.round(invoice.parse_confidence * 100)}`} />
      </View>

      {invoice.status === "needs_review" && (
        <Text style={styles.warning}>
          ⚠ Bu faturanın bazı alanları otomatik olarak okunamadı. Lütfen PDF'i kontrol edin.
        </Text>
      )}

      <TouchableOpacity style={styles.downloadButton} onPress={handleDownload} disabled={isDownloading}>
        {isDownloading ? (
          <ActivityIndicator color="#0f172a" />
        ) : (
          <Text style={styles.downloadButtonText}>PDF İndir / Paylaş</Text>
        )}
      </TouchableOpacity>

      {user?.role === "admin" && (
        <TouchableOpacity
          style={[styles.statusButton, invoice.status === "paid" && styles.statusButtonUndo]}
          onPress={handleToggleStatus}
          disabled={isUpdatingStatus}
        >
          {isUpdatingStatus ? (
            <ActivityIndicator color={invoice.status === "paid" ? colors.text : "#0f172a"} />
          ) : (
            <Text style={[styles.statusButtonText, invoice.status === "paid" && styles.statusButtonUndoText]}>
              {invoice.status === "paid" ? "Ödendi İşaretini Kaldır" : "Ödendi Olarak İşaretle"}
            </Text>
          )}
        </TouchableOpacity>
      )}
    </ScrollView>
  );
}

function InfoRow({ label, value, truncate }: { label: string; value: string; truncate?: boolean }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text
        style={styles.infoValue}
        numberOfLines={truncate ? 1 : undefined}
        ellipsizeMode={truncate ? "middle" : undefined}
      >
        {value}
      </Text>
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
  infoValue: { color: colors.text, fontSize: 13, fontWeight: "600", flexShrink: 1, textAlign: "right" },
  warning: { color: colors.warning, marginTop: spacing(2) },
  downloadButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
    marginTop: spacing(3),
  },
  downloadButtonText: { color: "#0f172a", fontWeight: "700" },
  statusButton: {
    backgroundColor: colors.success,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
    marginTop: spacing(1.5),
  },
  statusButtonText: { color: "#0f172a", fontWeight: "700" },
  statusButtonUndo: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  statusButtonUndoText: { color: colors.text },
});
