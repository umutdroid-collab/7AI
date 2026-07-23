import React, { useCallback, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import Alert from "../../utils/alert";
import { deleteSalesTarget, fetchSalesTargets } from "../../api/services";
import { SalesTarget } from "../../types";
import { colors, spacing } from "../../theme";
import { apiErrorMessage } from "../../api/client";
import { useAuth } from "../../context/AuthContext";

function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

function TargetCard({ target, onDeleted }: { target: SalesTarget; onDeleted: () => void }) {
  const { user } = useAuth();
  const [isDeleting, setIsDeleting] = useState(false);
  const ratio = target.target_quantity > 0 ? Math.min(target.progress / target.target_quantity, 1) : 0;
  const isComplete = target.progress >= target.target_quantity;

  function handleDelete() {
    Alert.alert("Hedefi sil", "Bu hedef kalıcı olarak silinecek. Emin misiniz?", [
      { text: "Vazgeç", style: "cancel" },
      {
        text: "Sil",
        style: "destructive",
        onPress: async () => {
          setIsDeleting(true);
          try {
            await deleteSalesTarget(target.id);
            onDeleted();
          } catch (e) {
            Alert.alert("Hata", apiErrorMessage(e));
          } finally {
            setIsDeleting(false);
          }
        },
      },
    ]);
  }

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.productName} numberOfLines={2}>
          {target.product.name}
        </Text>
        <View style={[styles.scopeBadge, target.assigned_user ? styles.scopeBadgePerson : styles.scopeBadgeTeam]}>
          <Text style={styles.scopeBadgeText}>{target.assigned_user ? target.assigned_user.full_name : "Tüm Ekip"}</Text>
        </View>
      </View>

      <View style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: `${ratio * 100}%` }, isComplete && styles.progressFillComplete]} />
      </View>
      <Text style={styles.progressText}>
        {target.progress} / {target.target_quantity} adet {isComplete ? "🎉 Hedef tamamlandı!" : ""}
      </Text>

      <Text style={styles.period}>
        {formatDate(target.period_start)} – {formatDate(target.period_end)}
      </Text>

      {target.note && <Text style={styles.note}>{target.note}</Text>}

      {!target.assigned_user && target.contributors.length > 0 && (
        <View style={styles.contributors}>
          {target.contributors.map((c) => (
            <Text key={c.user_id} style={styles.contributorRow}>
              {c.full_name}: {c.quantity} adet
            </Text>
          ))}
        </View>
      )}

      {user?.role === "admin" && (
        <TouchableOpacity style={styles.deleteButton} onPress={handleDelete} disabled={isDeleting}>
          <Text style={styles.deleteButtonText}>{isDeleting ? "Siliniyor..." : "Hedefi Sil"}</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

export default function PersonelTakipScreen({ navigation }: any) {
  const { user } = useAuth();
  const [targets, setTargets] = useState<SalesTarget[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchSalesTargets();
      setTargets(data);
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

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={{ padding: spacing(2) }}>
        {user?.role === "admin" && (
          <TouchableOpacity style={styles.addButton} onPress={() => navigation.navigate("AddSalesTarget")}>
            <Text style={styles.addButtonText}>+ Yeni Hedef</Text>
          </TouchableOpacity>
        )}

        {isLoading ? (
          <ActivityIndicator color={colors.primary} style={{ marginTop: spacing(4) }} />
        ) : error ? (
          <Text style={styles.error}>{error}</Text>
        ) : targets.length === 0 ? (
          <Text style={styles.empty}>Henüz hedef tanımlanmadı</Text>
        ) : (
          targets.map((t) => <TargetCard key={t.id} target={t} onDeleted={load} />)
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  addButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.5),
    alignItems: "center",
    marginBottom: spacing(2),
  },
  addButtonText: { color: "#0f172a", fontWeight: "700" },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing(2),
    marginBottom: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.border,
  },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  productName: { color: colors.text, fontSize: 15, fontWeight: "700", flex: 1, marginRight: spacing(1) },
  scopeBadge: { borderRadius: 8, paddingHorizontal: spacing(1), paddingVertical: spacing(0.5) },
  scopeBadgePerson: { backgroundColor: "rgba(96, 165, 250, 0.18)" },
  scopeBadgeTeam: { backgroundColor: "rgba(74, 222, 128, 0.18)" },
  scopeBadgeText: { color: colors.text, fontSize: 11, fontWeight: "700" },
  progressTrack: {
    height: 10,
    borderRadius: 6,
    backgroundColor: colors.surfaceAlt,
    marginTop: spacing(1.5),
    overflow: "hidden",
  },
  progressFill: { height: "100%", backgroundColor: colors.primary, borderRadius: 6 },
  progressFillComplete: { backgroundColor: colors.success },
  progressText: { color: colors.text, fontSize: 13, fontWeight: "600", marginTop: spacing(0.75) },
  period: { color: colors.textMuted, fontSize: 12, marginTop: spacing(0.5) },
  note: { color: colors.textMuted, fontSize: 12, marginTop: spacing(0.5), fontStyle: "italic" },
  contributors: {
    marginTop: spacing(1),
    paddingTop: spacing(1),
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  contributorRow: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  deleteButton: { alignSelf: "flex-end", marginTop: spacing(1.5) },
  deleteButtonText: { color: colors.danger, fontSize: 12, fontWeight: "700" },
  error: { color: colors.danger, textAlign: "center", marginTop: spacing(4) },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(4) },
});
