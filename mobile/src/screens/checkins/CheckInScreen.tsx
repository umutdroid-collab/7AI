import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import * as ImagePicker from "expo-image-picker";
import * as Location from "expo-location";
import Alert from "../../utils/alert";
import secureStorage from "../../utils/secureStorage";
import { createCheckIn, fetchCheckIns, fetchHospitals } from "../../api/services";
import { CheckIn, Hospital } from "../../types";
import { colors, spacing } from "../../theme";
import { apiErrorMessage, TOKEN_KEY } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import CheckInCard from "../../components/CheckInCard";
import HospitalPickerModal from "../../components/HospitalPickerModal";
import ErrorRetry from "../../components/ErrorRetry";
import WebCameraModal from "../../components/WebCameraModal";

type ViewMode = "mine" | "team";

export default function CheckInScreen() {
  const { user } = useAuth();
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [selectedHospitalId, setSelectedHospitalId] = useState<number | null>(null);
  const [isPickerVisible, setIsPickerVisible] = useState(false);
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [viewMode, setViewMode] = useState<ViewMode>("mine");
  const [checkins, setCheckins] = useState<CheckIn[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isCameraVisible, setIsCameraVisible] = useState(false);
  const hasSetDefaultViewMode = useRef(false);

  useEffect(() => {
    secureStorage.getItemAsync(TOKEN_KEY).then(setToken);
  }, []);

  useEffect(() => {
    if (!hasSetDefaultViewMode.current && user) {
      hasSetDefaultViewMode.current = true;
      // Adminler için varsayılan görünüm "Tüm Ekip" olsun - asıl kullanım amacı
      // çalışanların o gün nerede check-in yaptığını görmek, kendi girişleri değil.
      if (user.role === "admin") setViewMode("team");
    }
  }, [user]);

  useFocusEffect(
    useCallback(() => {
      fetchHospitals().then(setHospitals).catch(() => {});
    }, [])
  );

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

    if (Platform.OS === "web") {
      // Web'de expo-image-picker'ın kamera seçeneği aslında bir dosya seçici
      // (<input type=file capture>) - tarayıcıya göre kullanıcı yine de
      // galeriden eski bir fotoğraf seçebiliyor. O anda çekildiğini garanti
      // etmek için gerçek kamera akışından kare yakalayan bir bileşen kullanıyoruz.
      setIsCameraVisible(true);
      return;
    }

    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("İzin gerekli", "Fotoğraf çekmek için kamera izni vermeniz gerekiyor");
      return;
    }

    const result = await ImagePicker.launchCameraAsync({ quality: 0.5 });
    if (result.canceled || !result.assets?.length) return;

    await submitCheckIn(result.assets[0].uri, result.assets[0].file);
  }

  async function handleWebCapture(photo: { uri: string; blob: Blob }) {
    setIsCameraVisible(false);
    await submitCheckIn(photo.uri, photo.blob);
  }

  async function submitCheckIn(photoUri: string, webFile?: Blob | File | null) {
    if (!selectedHospitalId) return;

    let location: { latitude: number; longitude: number } | null = null;
    try {
      const locationPermission = await Location.requestForegroundPermissionsAsync();
      if (locationPermission.granted) {
        const position = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
        location = { latitude: position.coords.latitude, longitude: position.coords.longitude };
      }
    } catch {
      // Konum alınamadı (izin reddedildi, GPS kapalı vb.) - check-in'i konumsuz devam ettir.
    }

    setIsSubmitting(true);
    try {
      await createCheckIn(selectedHospitalId, photoUri, comment || undefined, webFile, location);
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
      <WebCameraModal
        visible={isCameraVisible}
        onClose={() => setIsCameraVisible(false)}
        onCapture={handleWebCapture}
      />
      <ScrollView contentContainerStyle={{ padding: spacing(2) }} keyboardShouldPersistTaps="handled">
        <View style={styles.formCard}>
          <Text style={styles.formTitle}>Bugün nerede olduğunuzu bildirin</Text>

          <TouchableOpacity style={styles.hospitalSelect} onPress={() => setIsPickerVisible(true)}>
            <Text style={selectedHospitalId ? styles.hospitalSelectText : styles.hospitalSelectPlaceholder}>
              {selectedHospitalId ? hospitals.find((h) => h.id === selectedHospitalId)?.name : "Hastane seçin..."}
            </Text>
            <Text style={styles.hospitalSelectChevron}>▾</Text>
          </TouchableOpacity>

          <HospitalPickerModal
            visible={isPickerVisible}
            hospitals={hospitals}
            onSelect={setSelectedHospitalId}
            onClose={() => setIsPickerVisible(false)}
          />

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
          <ErrorRetry message={error} onRetry={load} />
        ) : checkins.length === 0 ? (
          <Text style={styles.empty}>Henüz giriş kaydı yok</Text>
        ) : (
          checkins.map((c) => (
            <CheckInCard key={c.id} checkin={c} token={token} showEmployee={viewMode === "team"} onDeleted={load} />
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
  hospitalSelect: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: colors.surfaceAlt,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing(1.5),
  },
  hospitalSelectText: { color: colors.text, fontSize: 14, fontWeight: "600" },
  hospitalSelectPlaceholder: { color: colors.textMuted, fontSize: 14 },
  hospitalSelectChevron: { color: colors.textMuted },
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
