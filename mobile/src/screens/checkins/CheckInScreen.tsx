import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import * as ImagePicker from "expo-image-picker";
import * as SecureStore from "expo-secure-store";
import { createCheckIn, fetchCheckIns, fetchHospitals } from "../../api/services";
import { CheckIn, Hospital } from "../../types";
import { colors, spacing } from "../../theme";
import { apiErrorMessage, TOKEN_KEY } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import CheckInCard from "../../components/CheckInCard";

type ViewMode = "mine" | "team";

export default function CheckInScreen() {
  const { user } = useAuth();
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [selectedHospitalId, setSelectedHospitalId] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [viewMode, setViewMode] = useState<ViewMode>("mine");
  const [checkins, setCheckins] = useState<CheckIn[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    fetchHospitals().then(setHospitals).catch(() => {});
    SecureStore.getItemAsync(TOKEN_KEY).then(setToken);
  }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      const params = viewMode === "mine" && user ? { user_id: user.id } : undefined;
      const data = await fetchCheckIns(params);
      setCheckins(data);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, [viewMode, user]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handleCheckIn() {
    if (!selectedHospitalId) {
      Alert.alert("Hastane seçin", "Giriş yapmadan önce hangi hastanede olduğunuzu seçin");
      return;
    }

    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("İzin gerekli", "Fotoğraf çekmek için kamera izni vermeniz gerekiyor");
      return;
    }

    const result = await ImagePicker.launchCameraAsync({ quality: 0.5 });
    if (result.canceled || !result.assets?.length) return;

    setIsSubmitting(true);
    try {
      await createCheckIn(selectedHospitalId, result.assets[0].uri, comment || undefined);
      setComment("");
      Alert.alert("Giriş kaydedildi", "İyi çalışmalar!", [{ text: "Tamam", onPress: load }]);
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={{ padding: spacing(2) }} keyboardShouldPersistTaps="handled">
        <View style={styles.formCard}>
          <Text style={styles.formTitle}>Bugün nerede olduğunuzu bildirin</Text>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.hospitalRow}>
            {hospitals.map((h) => (
              <TouchableOpacity
                key={h.id}
                style={[styles.chip, selectedHospitalId === h.id && styles.chipActive]}
                onPress={() => setSelectedHospitalId(h.id)}
              >
                <Text style={[styles.chipText, selectedHospitalId === h.id && styles.chipTextActive]}>{h.name}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          <TextInput
            style={styles.commentInput}
            placeholder="İsterseniz hastaneyle ilgili bir not bırakın (opsiyonel)"
            placeholderTextColor={colors.textMuted}
            value={comment}
            onChangeText={setComment}
            multiline
          />

          <TouchableOpacity style={styles.checkInButton} onPress={handleCheckIn} disabled={isSubmitting}>
            {isSubmitting ? (
              <ActivityIndicator color="#0f172a" />
            ) : (
              <Text style={styles.checkInButtonText}>📷 Fotoğraf Çek ve Giriş Yap</Text>
            )}
          </TouchableOpacity>
        </View>

        {user?.role === "admin" && (
          <View style={styles.segmentRow}>
            <TouchableOpacity
              style={[styles.segment, viewMode === "mine" && styles.segmentActive]}
              onPress={() => setViewMode("mine")}
            >
              <Text style={[styles.segmentText, viewMode === "mine" && styles.segmentTextActive]}>Girişlerim</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.segment, viewMode === "team" && styles.segmentActive]}
              onPress={() => setViewMode("team")}
            >
              <Text style={[styles.segmentText, viewMode === "team" && styles.segmentTextActive]}>Tüm Ekip</Text>
            </TouchableOpacity>
          </View>
        )}

        <Text style={styles.sectionTitle}>{viewMode === "team" ? "Ekip Girişleri" : "Geçmişim"}</Text>

        {isLoading ? (
          <ActivityIndicator color={colors.primary} style={{ marginTop: spacing(2) }} />
        ) : error ? (
          <Text style={styles.error}>{error}</Text>
        ) : checkins.length === 0 ? (
          <Text style={styles.empty}>Henüz giriş kaydı yok</Text>
        ) : (
          checkins.map((c) => (
            <CheckInCard key={c.id} checkin={c} token={token} showEmployee={viewMode === "team"} />
          ))
        )}
      </ScrollView>
    </View>
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
  hospitalRow: { flexGrow: 0, marginBottom: spacing(1.5) },
  chip: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: 20,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1),
    marginRight: spacing(1),
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipText: { color: colors.textMuted, fontSize: 13, fontWeight: "600" },
  chipTextActive: { color: "#0f172a" },
  commentInput: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 60,
    textAlignVertical: "top",
    marginBottom: spacing(1.5),
  },
  checkInButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
  },
  checkInButtonText: { color: "#0f172a", fontWeight: "700" },
  segmentRow: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 4,
    marginBottom: spacing(2),
  },
  segment: { flex: 1, paddingVertical: spacing(1.25), borderRadius: 8, alignItems: "center" },
  segmentActive: { backgroundColor: colors.primary },
  segmentText: { color: colors.textMuted, fontSize: 13, fontWeight: "700" },
  segmentTextActive: { color: "#0f172a" },
  sectionTitle: { color: colors.text, fontSize: 15, fontWeight: "700", marginBottom: spacing(1) },
  error: { color: colors.danger, textAlign: "center", marginTop: spacing(2) },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(2) },
});
