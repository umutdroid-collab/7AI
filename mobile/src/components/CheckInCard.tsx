import React from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { CheckIn } from "../types";
import { colors, spacing } from "../theme";
import { API_BASE_URL } from "../api/client";
import { checkinPhotoUrl } from "../api/services";

export default function CheckInCard({
  checkin,
  token,
  showEmployee,
}: {
  checkin: CheckIn;
  token: string | null;
  showEmployee: boolean;
}) {
  return (
    <View style={styles.card}>
      {token && (
        <Image
          source={{ uri: `${API_BASE_URL}${checkinPhotoUrl(checkin.id)}`, headers: { Authorization: `Bearer ${token}` } }}
          style={styles.photo}
        />
      )}
      <View style={styles.info}>
        {showEmployee && <Text style={styles.employee}>{checkin.user.full_name}</Text>}
        <Text style={styles.hospital}>🏥 {checkin.hospital.name}</Text>
        <Text style={styles.time}>{new Date(checkin.checked_in_at).toLocaleString("tr-TR")}</Text>
        {checkin.comment && <Text style={styles.comment}>{checkin.comment}</Text>}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
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
});
