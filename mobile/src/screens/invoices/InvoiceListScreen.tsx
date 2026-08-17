import React, { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import Alert from "../../utils/alert";
import { useFocusEffect } from "@react-navigation/native";
import * as DocumentPicker from "expo-document-picker";
import { fetchInvoices, fetchNotifications, invoiceExportUrl, uploadInvoicePdf } from "../../api/services";
import { Invoice } from "../../types";
import { colors, layout, radius, spacing, typography } from "../../theme";
import InvoiceCard from "../../components/InvoiceCard";
import ErrorRetry from "../../components/ErrorRetry";
import Icon from "../../components/Icon";
import { ActionPill, FilterChip, SearchField, WrapRow } from "../../components/ui";
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
      <View style={styles.controls}>
        <View style={styles.topRow}>
          <View style={styles.searchWrapper}>
            <SearchField
              value={query}
              onChangeText={setQuery}
              onSubmit={load}
              placeholder="Fatura no veya firma ara"
            />
          </View>

          {user?.role === "admin" && (
            <>
              <IconButton icon="upload" onPress={handleUpload} loading={isUploading} />
              <IconButton icon="folder" onPress={() => navigation.navigate("BulkUpload")} />
            </>
          )}
          <IconButton
            icon="bell"
            onPress={() => navigation.navigate("Notifications")}
            badge={unreadCount}
          />
        </View>

        <WrapRow>
          <FilterChip label="Tümü" active={filter === "all"} onPress={() => setFilter("all")} />
          <FilterChip
            label="Vadesi Yaklaşan"
            active={filter === "upcoming"}
            onPress={() => setFilter("upcoming")}
          />
          <FilterChip
            label="Vadesi Geçmiş"
            active={filter === "overdue"}
            onPress={() => setFilter("overdue")}
          />
          <FilterChip label="Ödendi" active={filter === "paid"} onPress={() => setFilter("paid")} />
        </WrapRow>

        <WrapRow>
          <ActionPill
            label="Excel'e Aktar"
            icon="file"
            tone="success"
            loading={isExporting}
            onPress={handleExportExcel}
          />
        </WrapRow>
      </View>

      {isLoading ? (
        <ActivityIndicator style={{ marginTop: spacing(4) }} color={colors.primary} />
      ) : error ? (
        <ErrorRetry message={error} onRetry={load} />
      ) : (
        <FlatList
          data={invoices}
          keyExtractor={(i) => String(i.id)}
          contentContainerStyle={styles.list}
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

/** Arama kutusunun yanındaki 36x36 kare eylem düğmeleri; zil olanı okunmamış
 *  bildirim sayısını rozet olarak taşıyor. */
function IconButton({
  icon,
  onPress,
  loading,
  badge,
}: {
  icon: React.ComponentProps<typeof Icon>["name"];
  onPress: () => void;
  loading?: boolean;
  badge?: number;
}) {
  return (
    <TouchableOpacity style={styles.iconButton} onPress={onPress} disabled={loading}>
      {loading ? (
        <ActivityIndicator size="small" color={colors.primary} />
      ) : (
        <Icon name={icon} size={18} color={colors.textMuted} />
      )}
      {!!badge && badge > 0 && (
        <View style={styles.iconBadge}>
          <Text style={styles.iconBadgeText}>{badge > 99 ? "99+" : badge}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  controls: { padding: layout.screenPadding, gap: layout.cardGap },
  topRow: { flexDirection: "row", alignItems: "center", gap: spacing(1) },
  searchWrapper: { flex: 1 },
  iconButton: {
    width: 36,
    height: 36,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  iconBadge: {
    position: "absolute",
    top: -4,
    right: -6,
    minWidth: 18,
    paddingHorizontal: 4,
    height: 16,
    borderRadius: radius.full,
    backgroundColor: colors.danger,
    alignItems: "center",
    justifyContent: "center",
  },
  iconBadgeText: { color: "#fff", fontSize: 10, fontWeight: "700" },
  list: { paddingHorizontal: layout.screenPadding, paddingBottom: spacing(6) },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(4) },
});
