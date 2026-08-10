import React, { useEffect, useState } from "react";
import { Image, Linking, Platform, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { CheckIn } from "../types";
import { colors, spacing } from "../theme";
import { api, API_BASE_URL, apiErrorMessage } from "../api/client";
import { checkinPhotoUrl, deleteCheckIn } from "../api/services";
import { useAuth } from "../context/AuthContext";
import Alert from "../utils/alert";
import PhotoViewerModal from "./PhotoViewerModal";

export default function CheckInCard({
  checkin,
  token,
  showEmployee,
  onDeleted,
  navigation,
}: {
  checkin: CheckIn;
  token: string | null;
  showEmployee: boolean;
  onDeleted?: () => void;
  navigation?: any;
}) {
  const { user } = useAuth();
  const [webPhotoUri, setWebPhotoUri] = useState<string | null>(null);
  const [webFullPhotoUri, setWebFullPhotoUri] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isViewerOpen, setIsViewerOpen] = useState(false);

  useEffect(() => {
    if (Platform.OS !== "web") return;
    let objectUrl: string | null = null;
    api
      .get(checkinPhotoUrl(checkin.id), { responseType: "blob" })
      .then((response) => {
        objectUrl = URL.createObjectURL(response.data as Blob);
        setWebPhotoUri(objectUrl);
      })
      .catch(() => {});
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [checkin.id]);

  // Tam boy dosya yalnızca büyütüldüğünde indirilir; listedeki her kart için
  // baştan indirmek mobil veride gereksiz yük olurdu.
  useEffect(() => {
    if (Platform.OS !== "web" || !isViewerOpen || webFullPhotoUri) return;
    let objectUrl: string | null = null;
    api
      .get(checkinPhotoUrl(checkin.id, "tam"), { responseType: "blob" })
      .then((response) => {
        objectUrl = URL.createObjectURL(response.data as Blob);
        setWebFullPhotoUri(objectUrl);
      })
      .catch(() => {});
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [checkin.id, isViewerOpen]);

  const nativeHeaders = token ? { Authorization: `Bearer ${token}` } : undefined;
  const photoUri =
    Platform.OS === "web" ? webPhotoUri : `${API_BASE_URL}${checkinPhotoUrl(checkin.id)}`;
  const fullPhotoUri =
    Platform.OS === "web" ? webFullPhotoUri : `${API_BASE_URL}${checkinPhotoUrl(checkin.id, "tam")}`;

  function handleDelete() {
    Alert.alert("Girişi sil", "Bu giriş kaydı ve fotoğrafı kalıcı olarak silinecek. Emin misiniz?", [
      { text: "Vazgeç", style: "cancel" },
      {
        text: "Sil",
        style: "destructive",
        onPress: async () => {
          setIsDeleting(true);
          try {
            await deleteCheckIn(checkin.id);
            onDeleted?.();
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
      <PhotoViewerModal
        visible={isViewerOpen}
        uri={
          // Native'de yetkilendirme başlığı gerektiği için Image kaynağı
          // doğrudan kullanılamaz; aşağıdaki nativeSource ile veriliyor.
          Platform.OS === "web" ? webFullPhotoUri : fullPhotoUri
        }
        nativeHeaders={Platform.OS === "web" ? undefined : nativeHeaders}
        title={checkin.hospital.name}
        subtitle={`${showEmployee ? checkin.user.full_name + " - " : ""}${new Date(
          checkin.checked_in_at
        ).toLocaleString("tr-TR")}`}
        onClose={() => setIsViewerOpen(false)}
      />
      {photoUri && (
        <TouchableOpacity onPress={() => setIsViewerOpen(true)} accessibilityLabel="Fotoğrafı büyüt">
          <Image
            source={
              Platform.OS === "web"
                ? { uri: photoUri }
                : { uri: photoUri, headers: nativeHeaders }
            }
            style={styles.photo}
          />
        </TouchableOpacity>
      )}
      <View style={styles.info}>
        {showEmployee && <Text style={styles.employee}>{checkin.user.full_name}</Text>}
        <Text style={styles.hospital}>🏥 {checkin.hospital.name}</Text>
        <Text style={styles.time}>{new Date(checkin.checked_in_at).toLocaleString("tr-TR")}</Text>
        {checkin.comment && <Text style={styles.comment}>{checkin.comment}</Text>}
        {checkin.latitude != null && checkin.longitude != null && (
          <TouchableOpacity
            onPress={() =>
              Linking.openURL(`https://www.google.com/maps?q=${checkin.latitude},${checkin.longitude}`)
            }
          >
            <Text style={styles.mapLink}>📍 Haritada Gör</Text>
          </TouchableOpacity>
        )}
        {/* Dikkat çeken bir yorum listede aşağı kayıp kayboluyordu; buradan
            hatırlatıcıya dönüştürülüp tarihi geldiğinde özet e-postasında
            karşımıza çıkıyor. */}
        {user?.role === "admin" && navigation && (
          <TouchableOpacity
            onPress={() =>
              navigation.navigate("FollowUps", {
                checkinId: checkin.id,
                aboutUserId: checkin.user.id,
                initialNote: checkin.comment ?? "",
              })
            }
          >
            <Text style={styles.followUpLink}>🔔 Takibe Al</Text>
          </TouchableOpacity>
        )}
      </View>
      {user?.role === "admin" && (
        <TouchableOpacity style={styles.deleteButton} onPress={handleDelete} disabled={isDeleting}>
          <Text style={styles.deleteButtonText}>{isDeleting ? "..." : "🗑"}</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing(1.5),
    marginBottom: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.border,
  },
  photo: {
    width: 64,
    height: 64,
    borderRadius: 10,
    backgroundColor: colors.surfaceAlt,
    marginRight: spacing(1.5),
  },
  info: { flex: 1 },
  employee: { color: colors.text, fontWeight: "700", fontSize: 14 },
  hospital: { color: colors.primary, fontSize: 13, fontWeight: "600", marginTop: 2 },
  time: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  comment: { color: colors.textMuted, fontSize: 12, marginTop: spacing(0.5), fontStyle: "italic" },
  mapLink: { color: colors.primary, fontSize: 12, marginTop: spacing(0.5), fontWeight: "600" },
  followUpLink: { color: colors.warning, fontSize: 12, marginTop: spacing(0.5), fontWeight: "600" },
  deleteButton: {
    paddingHorizontal: spacing(1.5),
    paddingVertical: spacing(1),
    marginLeft: spacing(1),
  },
  deleteButtonText: { fontSize: 18 },
});
