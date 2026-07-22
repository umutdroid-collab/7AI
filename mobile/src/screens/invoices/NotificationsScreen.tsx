import React, { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from "../../api/services";
import { Notification } from "../../types";
import { colors, spacing } from "../../theme";

export default function NotificationsScreen({ navigation }: any) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await fetchNotifications();
      setNotifications(data);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handlePress(n: Notification) {
    if (!n.is_read) {
      await markNotificationRead(n.id);
    }
    if (n.invoice_id) {
      navigation.navigate("InvoiceDetail", { invoiceId: n.invoice_id });
    } else {
      load();
    }
  }

  async function handleMarkAll() {
    await markAllNotificationsRead();
    load();
  }

  if (isLoading) {
    return <ActivityIndicator style={{ marginTop: spacing(4) }} color={colors.primary} />;
  }

  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.markAllButton} onPress={handleMarkAll}>
        <Text style={styles.markAllText}>Tümünü okundu işaretle</Text>
      </TouchableOpacity>
      <FlatList
        data={notifications}
        keyExtractor={(n) => String(n.id)}
        contentContainerStyle={{ padding: spacing(2) }}
        ListEmptyComponent={<Text style={styles.empty}>Bildirim yok</Text>}
        renderItem={({ item }) => (
          <TouchableOpacity style={[styles.card, !item.is_read && styles.cardUnread]} onPress={() => handlePress(item)}>
            <Text style={styles.title}>{item.title}</Text>
            <Text style={styles.message}>{item.message}</Text>
            <Text style={styles.date}>{new Date(item.created_at).toLocaleString("tr-TR")}</Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  markAllButton: { alignSelf: "flex-end", marginRight: spacing(2), marginTop: spacing(1) },
  markAllText: { color: colors.primary, fontSize: 13, fontWeight: "600" },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: spacing(2),
    marginBottom: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardUnread: { borderColor: colors.primary },
  title: { color: colors.text, fontWeight: "700", fontSize: 14 },
  message: { color: colors.textMuted, fontSize: 13, marginTop: 4 },
  date: { color: colors.textMuted, fontSize: 11, marginTop: spacing(1) },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(4) },
});
