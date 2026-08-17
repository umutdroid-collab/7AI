import React, { useEffect, useState } from "react";
import { Image, Linking, Platform, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { CheckIn } from "../types";
import { colors, layout, radius, spacing, typography } from "../theme";
import { api, API_BASE_URL, apiErrorMessage } from "../api/client";
import { checkinPhotoUrl, deleteCheckIn } from "../api/services";
import { useAuth } from "../context/AuthContext";
import Alert from "../utils/alert";
import PhotoViewerModal from "./PhotoViewerModal";
import Icon from "./Icon";

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
        <View style={styles.hospitalRow}>
          <Icon name="hospital" size={12} color={colors.primary} />
          <Text style={styles.hospital} numberOfLines={1}>{checkin.hospital.name}</Text>
        </View>
        <Text style={styles.time}>{new Date(checkin.checked_in_at).toLocaleString("tr-TR")}</Text>
        {checkin.comment && <Text style={styles.comment}>{checkin.comment}</Text>}
        {checkin.latitude != null && checkin.longitude != null && (
          <TouchableOpacity
            onPress={() =>
              Linking.openURL(`https://www.google.com/maps?q=${checkin.latitude},${checkin.longitude}`)
            }
          >
            <View style={styles.linkRow}>
              <Icon name="location" size={12} color={colors.primary} />
              <Text style={styles.mapLink}>Haritada Gör</Text>
            </View>
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
            <View style={styles.linkRow}>
              <Icon name="bell" size={12} color={colors.warning} />
              <Text style={styles.followUpLink}>Takibe Al</Text>
            </View>
          </TouchableOpacity>
        )}
      </View>
      {user?.role === "admin" && (
        <TouchableOpacity style={styles.deleteButton} onPress={handleDelete} disabled={isDeleting}>
          {isDeleting ? (
            <Text style={styles.deleteButtonText}>...</Text>
          ) : (
            <Icon name="trash" size={14} color={colors.textMuted} />
          )}
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    padding: layout.cardGap,
    marginBottom: layout.cardGap,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  photo: {
    width: 80,
    height: 80,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceAlt,
    marginRight: layout.cardGap,
  },
  info: { flex: 1, gap: 4 },
  employee: { ...typography.cardTitle, color: colors.text },
  hospitalRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  hospital: { ...typography.bodyStrong, color: colors.primary, flexShrink: 1 },
  time: { ...typography.meta, color: colors.textMuted },
  comment: { ...typography.body, color: colors.textMuted, fontStyle: "italic" },
  linkRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 2 },
  mapLink: { ...typography.meta, color: colors.primary, fontWeight: "700" },
  followUpLink: { ...typography.meta, color: colors.warning, fontWeight: "700" },
  deleteButton: {
    width: 28,
    height: 28,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: spacing(1),
  },
  deleteButtonText: { color: colors.textMuted, fontSize: 12 },
});
