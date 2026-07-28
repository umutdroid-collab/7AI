import React, { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { AuditLogEntry, fetchAuditLogs } from "../../api/services";
import { apiErrorMessage } from "../../api/client";
import { colors, spacing } from "../../theme";
import ErrorRetry from "../../components/ErrorRetry";

const ACTION_LABELS: Record<string, string> = {
  create: "Oluşturma",
  delete: "Silme",
  bulk_delete: "Toplu Silme",
  restore: "Geri Yükleme",
  activate: "Aktifleştirme",
  deactivate: "Pasifleştirme",
};

const ACTION_COLORS: Record<string, string> = {
  create: colors.success,
  delete: colors.danger,
  bulk_delete: colors.danger,
  restore: colors.warning,
  activate: colors.success,
  deactivate: colors.warning,
};

export default function AuditLogScreen() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setEntries(await fetchAuditLogs());
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  if (isLoading) {
    return <ActivityIndicator color={colors.primary} style={{ marginTop: spacing(4) }} />;
  }
  if (error) {
    return <ErrorRetry message={error} onRetry={load} />;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.intro}>
        Silme, geri yükleme ve kullanıcı işlemlerinin kaydı. Bir kaydın neden kaybolduğunu ya da kimin
        değiştirdiğini buradan görebilirsiniz.
      </Text>
      <FlatList
        data={entries}
        keyExtractor={(e) => String(e.id)}
        contentContainerStyle={{ paddingBottom: spacing(3) }}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={colors.primary} />}
        ListEmptyComponent={<Text style={styles.empty}>Henüz kayıt yok</Text>}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.headerRow}>
              <View style={[styles.badge, { backgroundColor: ACTION_COLORS[item.action] ?? colors.textMuted }]}>
                <Text style={styles.badgeText}>{ACTION_LABELS[item.action] ?? item.action}</Text>
              </View>
              <Text style={styles.date}>{new Date(item.created_at).toLocaleString("tr-TR")}</Text>
            </View>
            <Text style={styles.summary}>{item.summary}</Text>
            <Text style={styles.user}>👤 {item.user_name}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing(2) },
  intro: { color: colors.textMuted, fontSize: 13, marginBottom: spacing(2), lineHeight: 18 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: spacing(1.75),
    marginBottom: spacing(1.25),
    borderWidth: 1,
    borderColor: colors.border,
  },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  badge: { borderRadius: 8, paddingHorizontal: spacing(1), paddingVertical: 3 },
  badgeText: { color: "#0f172a", fontSize: 11, fontWeight: "700" },
  date: { color: colors.textMuted, fontSize: 11 },
  summary: { color: colors.text, fontSize: 13, marginTop: spacing(1), lineHeight: 18 },
  user: { color: colors.textMuted, fontSize: 12, marginTop: spacing(0.75) },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(4) },
});
