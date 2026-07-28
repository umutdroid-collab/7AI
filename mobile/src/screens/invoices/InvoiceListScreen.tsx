import React, { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, RefreshControl, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import Alert from "../../utils/alert";
import { useFocusEffect } from "@react-navigation/native";
import * as DocumentPicker from "expo-document-picker";
import { fetchInvoices, fetchNotifications, invoiceExportUrl, uploadInvoicePdf } from "../../api/services";
import { Invoice } from "../../types";
import { colors, spacing } from "../../theme";
import InvoiceCard from "../../components/InvoiceCard";
import ErrorRetry from "../../components/ErrorRetry";
import { apiErrorMessage } from "../../api/client";
import { dateStampedFilename, downloadFile } from "../../utils/download";
import { useAuth } from "../../context/AuthContext";

type Filter = "all" | "upcoming" | "overdue" | "paid";

export default function InvoiceListScreen({ navigation }: any) {
  const { user } = useAuth();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const params: any = { q: query || undefined };
      if (filter === "upcoming") params.upcoming_only = true;
      if (filter === "overdue") params.overdue_only = true;
      const [data, unread] = await Promise.all([fetchInvoices(params), fetchNotifications(true)]);
      setInvoices(filter === "paid" ? data.filter((i) => i.status === "paid") : data);
      setUnreadCount(unread.length);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, [filter, query]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handleUpload() {
    const result = await DocumentPicker.getDocumentAsync({ type: "application/pdf", copyToCacheDirectory: true });
    if (result.canceled || !result.assets?.length) return;

    const file = result.assets[0];
    setIsUploading(true);
    try {
      const invoice = await uploadInvoicePdf(file.uri, file.name || "fatura.pdf", file.file);
      Alert.alert(
        "Fatura yüklendi",
        invoice.parse_confidence >= 0.75
          ? "Fatura bilgileri otomatik olarak okundu."
          : "Fatura yüklendi ancak bazı alanlar otomatik okunamadı, kontrol edip düzeltmeniz gerekebilir.",
        [{ text: "Tamam", onPress: load }]
      );
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsUploading(false);
    }
  }

  async function handleExportExcel() {
    setIsExporting(true);
    try {
      const url = invoiceExportUrl({
        q: query || undefined,
        upcoming_only: filter === "upcoming" || undefined,
        overdue_only: filter === "overdue" || undefined,
        paid_only: filter === "paid" || undefined,
      });
      await downloadFile(url, dateStampedFilename("fatura-raporu", "xlsx"));
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.topRow}>
        <TextInput
          style={styles.search}
          placeholder="Fatura no veya firma ara"
          placeholderTextColor={colors.textMuted}
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={load}
        />
        {user?.role === "admin" && (
          <TouchableOpacity style={styles.uploadButton} onPress={handleUpload} disabled={isUploading}>
            {isUploading ? (
              <ActivityIndicator size="small" color={colors.primary} />
            ) : (
              <Text style={styles.uploadText}>📤</Text>
            )}
          </TouchableOpacity>
        )}
        {user?.role === "admin" && (
          <TouchableOpacity style={styles.uploadButton} onPress={() => navigation.navigate("BulkUpload")}>
            <Text style={styles.uploadText}>📚</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity style={styles.bellButton} onPress={() => navigation.navigate("Notifications")}>
          <Text style={styles.bellText}>🔔</Text>
          {unreadCount > 0 && (
            <View style={styles.bellBadge}>
              <Text style={styles.bellBadgeText}>{unreadCount}</Text>
            </View>
          )}
        </TouchableOpacity>
      </View>

      <View style={styles.chipsRow}>
        <Chip label="Tümü" active={filter === "all"} onPress={() => setFilter("all")} />
        <Chip label="Vadesi Yaklaşan" active={filter === "upcoming"} onPress={() => setFilter("upcoming")} />
        <Chip label="Vadesi Geçmiş" active={filter === "overdue"} onPress={() => setFilter("overdue")} />
        <Chip label="Ödendi" active={filter === "paid"} onPress={() => setFilter("paid")} />
        <TouchableOpacity style={styles.exportChip} onPress={handleExportExcel} disabled={isExporting}>
          {isExporting ? (
            <ActivityIndicator size="small" color={colors.primary} />
          ) : (
            <Text style={styles.exportChipText}>📊 Excel'e Aktar</Text>
          )}
        </TouchableOpacity>
      </View>

      {isLoading ? (
        <ActivityIndicator style={{ marginTop: spacing(4) }} color={colors.primary} />
      ) : error ? (
        <ErrorRetry message={error} onRetry={load} />
      ) : (
        <FlatList
          data={invoices}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={{ padding: spacing(2) }}
          refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={colors.primary} />}
          ListEmptyComponent={<Text style={styles.empty}>Fatura bulunamadı</Text>}
          renderItem={({ item }) => (
            <InvoiceCard invoice={item} onPress={() => navigation.navigate("InvoiceDetail", { invoiceId: item.id })} />
          )}
        />
      )}
    </View>
  );
}

function Chip({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity style={[styles.chip, active && styles.chipActive]} onPress={onPress}>
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  topRow: { flexDirection: "row", alignItems: "center", paddingHorizontal: spacing(2), marginTop: spacing(2) },
  search: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  uploadButton: { marginLeft: spacing(1.5), padding: spacing(1) },
  uploadText: { fontSize: 20 },
  bellButton: { marginLeft: spacing(1.5), padding: spacing(1) },
  bellText: { fontSize: 22 },
  bellBadge: {
    position: "absolute",
    top: 0,
    right: 0,
    backgroundColor: colors.danger,
    borderRadius: 9,
    minWidth: 18,
    height: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  bellBadgeText: { color: "#fff", fontSize: 10, fontWeight: "700" },
  chipsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: spacing(2),
    marginVertical: spacing(1),
    gap: spacing(1),
  },
  chip: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1),
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textMuted, fontSize: 13, fontWeight: "600" },
  chipTextActive: { color: "#0f172a" },
  exportChip: {
    borderRadius: 20,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1),
    borderWidth: 1,
    borderColor: colors.primary,
    borderStyle: "dashed",
  },
  exportChipText: { color: colors.primary, fontSize: 13, fontWeight: "700" },
  error: { color: colors.danger, textAlign: "center", marginTop: spacing(4) },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(4) },
});
