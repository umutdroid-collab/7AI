import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import Alert from "../../utils/alert";
import { apiErrorMessage } from "../../api/client";
import {
  createFollowUp,
  deleteFollowUp,
  fetchFollowUps,
  updateFollowUp,
} from "../../api/services";
import { FollowUp } from "../../types";
import { colors, spacing } from "../../theme";
import ErrorRetry from "../../components/ErrorRetry";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Yöneticinin takip notları. Çıkış noktası: bir çalışanın check-in yorumunda
 * dikkat çeken bir şey, listede aşağı kaydıkça kayboluyordu. Buradaki notlar
 * tarihi geldiğinde günlük özet e-postasında hatırlatılır.
 */
export default function FollowUpsScreen({ route }: any) {
  const [items, setItems] = useState<FollowUp[]>([]);
  const [includeDone, setIncludeDone] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Check-in kartından gelindiyse not ve bağlantı hazır gelir.
  const [note, setNote] = useState<string>(route.params?.initialNote ?? "");
  const [remindOn, setRemindOn] = useState(todayIso());
  const [isSaving, setIsSaving] = useState(false);
  const checkinId: number | undefined = route.params?.checkinId;
  const aboutUserId: number | undefined = route.params?.aboutUserId;

  const load = useCallback(async () => {
    setError(null);
    try {
      setItems(await fetchFollowUps(includeDone));
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, [includeDone]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handleAdd() {
    if (!note.trim()) {
      Alert.alert("Eksik bilgi", "Hatırlatılacak notu yazın");
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(remindOn)) {
      Alert.alert("Geçersiz tarih", "Tarihi YYYY-AA-GG biçiminde girin (örn. 2026-09-01)");
      return;
    }
    setIsSaving(true);
    try {
      await createFollowUp({
        note: note.trim(),
        remind_on: remindOn,
        checkin_id: checkinId,
        about_user_id: aboutUserId,
      });
      setNote("");
      setRemindOn(todayIso());
      await load();
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleToggleDone(item: FollowUp) {
    try {
      await updateFollowUp(item.id, { is_done: !item.is_done });
      await load();
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    }
  }

  function handleDelete(item: FollowUp) {
    Alert.alert("Hatırlatıcıyı sil", "Bu not kalıcı olarak silinecek. Emin misiniz?", [
      { text: "Vazgeç", style: "cancel" },
      {
        text: "Sil",
        style: "destructive",
        onPress: async () => {
          try {
            await deleteFollowUp(item.id);
            await load();
          } catch (e) {
            Alert.alert("Hata", apiErrorMessage(e));
          }
        },
      },
    ]);
  }

  function dueLabel(item: FollowUp) {
    const days = item.days_until_due;
    if (days === null) return "";
    if (days < 0) return `${Math.abs(days)} gün gecikti`;
    if (days === 0) return "Bugün";
    return `${days} gün kaldı`;
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing(2) }}>
      <View style={styles.formCard}>
        <Text style={styles.formTitle}>Yeni hatırlatıcı</Text>
        <TextInput
          style={styles.noteInput}
          placeholder="Toplantıda konuşulacak not"
          placeholderTextColor={colors.textMuted}
          value={note}
          onChangeText={setNote}
          multiline
        />
        {checkinId && (
          <Text style={styles.linkedHint}>
            Bu not, seçtiğiniz ziyaret kaydına bağlanacak.
          </Text>
        )}
        <Text style={styles.label}>Hatırlatma tarihi (YYYY-AA-GG)</Text>
        <TextInput
          style={styles.input}
          value={remindOn}
          onChangeText={setRemindOn}
          placeholderTextColor={colors.textMuted}
        />
        <TouchableOpacity style={styles.addButton} onPress={handleAdd} disabled={isSaving}>
          {isSaving ? (
            <ActivityIndicator color="#0f172a" />
          ) : (
            <Text style={styles.addButtonText}>Ekle</Text>
          )}
        </TouchableOpacity>
      </View>

      <View style={styles.toggleRow}>
        <Text style={styles.toggleLabel}>Tamamlananları da göster</Text>
        <Switch value={includeDone} onValueChange={setIncludeDone} />
      </View>

      {isLoading ? (
        <ActivityIndicator color={colors.primary} style={{ marginTop: spacing(2) }} />
      ) : error ? (
        <ErrorRetry message={error} onRetry={load} />
      ) : items.length === 0 ? (
        <Text style={styles.empty}>
          {includeDone ? "Hiç hatırlatıcı yok" : "Açık hatırlatıcı yok"}
        </Text>
      ) : (
        items.map((item) => (
          <View key={item.id} style={[styles.card, item.is_done && styles.cardDone]}>
            <TouchableOpacity style={styles.checkArea} onPress={() => handleToggleDone(item)}>
              <View style={[styles.checkbox, item.is_done && styles.checkboxChecked]}>
                {item.is_done && <Text style={styles.checkTick}>✓</Text>}
              </View>
            </TouchableOpacity>

            <View style={styles.cardBody}>
              <Text style={[styles.note, item.is_done && styles.noteDone]}>{item.note}</Text>
              <Text
                style={[
                  styles.due,
                  !item.is_done && (item.days_until_due ?? 0) < 0 && styles.dueOverdue,
                ]}
              >
                📅 {new Date(item.remind_on).toLocaleDateString("tr-TR")} · {dueLabel(item)}
              </Text>
              {item.checkin && (
                <Text style={styles.context}>
                  {item.checkin.hospital_name} · {item.checkin.user_name}
                  {item.checkin.comment ? `\n"${item.checkin.comment}"` : ""}
                </Text>
              )}
            </View>

            <TouchableOpacity style={styles.deleteButton} onPress={() => handleDelete(item)}>
              <Text style={styles.deleteButtonText}>🗑</Text>
            </TouchableOpacity>
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  formCard: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing(2),
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing(2),
  },
  formTitle: { color: colors.text, fontSize: 15, fontWeight: "700", marginBottom: spacing(1.5) },
  label: { color: colors.textMuted, fontSize: 12, marginBottom: spacing(0.5) },
  noteInput: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 70,
    textAlignVertical: "top",
    marginBottom: spacing(1.5),
  },
  linkedHint: { color: colors.textMuted, fontSize: 12, marginBottom: spacing(1.5) },
  input: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.25),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing(1.5),
  },
  addButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.5),
    alignItems: "center",
  },
  addButtonText: { color: "#0f172a", fontWeight: "700" },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing(1.5),
  },
  toggleLabel: { color: colors.textMuted, fontSize: 13 },
  card: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing(1.5),
    marginBottom: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardDone: { opacity: 0.55 },
  checkArea: { paddingRight: spacing(1.5), paddingTop: 2 },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  checkboxChecked: { backgroundColor: colors.primary, borderColor: colors.primary },
  checkTick: { color: "#0f172a", fontSize: 14, fontWeight: "700", lineHeight: 18 },
  cardBody: { flex: 1 },
  note: { color: colors.text, fontSize: 14, fontWeight: "600" },
  noteDone: { textDecorationLine: "line-through" },
  due: { color: colors.textMuted, fontSize: 12, marginTop: spacing(0.5) },
  dueOverdue: { color: colors.danger, fontWeight: "700" },
  context: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: spacing(0.5),
    fontStyle: "italic",
  },
  deleteButton: { paddingHorizontal: spacing(1), paddingVertical: spacing(0.5) },
  deleteButtonText: { fontSize: 16 },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(2) },
});
