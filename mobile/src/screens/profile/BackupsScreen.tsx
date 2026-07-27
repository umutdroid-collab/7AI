import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Platform,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import Alert from "../../utils/alert";
import secureStorage from "../../utils/secureStorage";
import {
  BackupInfo,
  backupDownloadUrl,
  deleteBackup,
  fetchBackups,
  restoreBackup,
  runBackupNow,
} from "../../api/services";
import { api, apiErrorMessage, API_BASE_URL, TOKEN_KEY } from "../../api/client";
import { colors, spacing } from "../../theme";
import ErrorRetry from "../../components/ErrorRetry";

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function BackupsScreen() {
  const [backups, setBackups] = useState<BackupInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [busyFilename, setBusyFilename] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchBackups();
      setBackups(data);
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

  async function handleRunNow() {
    setIsRunning(true);
    try {
      await runBackupNow();
      await load();
      Alert.alert("Tamamlandı", "Yedek alındı");
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsRunning(false);
    }
  }

  async function handleDownload(backup: BackupInfo) {
    setBusyFilename(backup.filename);
    try {
      const url = backupDownloadUrl(backup.filename);
      if (Platform.OS === "web") {
        const response = await api.get(url, { responseType: "blob" });
        const blobUrl = URL.createObjectURL(response.data as Blob);
        const link = document.createElement("a");
        link.href = blobUrl;
        link.download = backup.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(blobUrl);
      } else {
        const token = await secureStorage.getItemAsync(TOKEN_KEY);
        const localUri = `${FileSystem.cacheDirectory}${backup.filename}`;
        const result = await FileSystem.downloadAsync(`${API_BASE_URL}${url}`, localUri, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(result.uri);
        } else {
          Alert.alert("İndirildi", `Yedek kaydedildi: ${result.uri}`);
        }
      }
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setBusyFilename(null);
    }
  }

  function handleRestore(backup: BackupInfo) {
    Alert.alert(
      "Dikkat: Yedekten geri yükle",
      `${new Date(backup.created_at).toLocaleString("tr-TR")} tarihli yedek geri yüklenecek. Bu işlem şu ANDAKİ tüm verilerin (stok, fatura, kullanıcı vb.) üzerine yazar ve geri alınamaz.\n\nDevam etmeden önce mevcut durumun bir güvenlik yedeği otomatik alınacak.`,
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: "Devam et",
          style: "destructive",
          onPress: () => {
            Alert.alert(
              "Son onay",
              "Emin misiniz? Bu geri alınamaz bir işlemdir ve uygulama bu sırada kısa süreliğine kullanılamayabilir.",
              [
                { text: "Vazgeç", style: "cancel" },
                {
                  text: "Evet, geri yükle",
                  style: "destructive",
                  onPress: async () => {
                    setBusyFilename(backup.filename);
                    try {
                      await restoreBackup(backup.filename);
                      await load();
                      Alert.alert("Tamamlandı", "Sistem seçilen yedekten geri yüklendi");
                    } catch (e) {
                      Alert.alert("Hata", apiErrorMessage(e));
                    } finally {
                      setBusyFilename(null);
                    }
                  },
                },
              ]
            );
          },
        },
      ]
    );
  }

  function handleDelete(backup: BackupInfo) {
    Alert.alert("Yedeği sil", `${new Date(backup.created_at).toLocaleString("tr-TR")} tarihli yedek silinecek.`, [
      { text: "Vazgeç", style: "cancel" },
      {
        text: "Sil",
        style: "destructive",
        onPress: async () => {
          setBusyFilename(backup.filename);
          try {
            await deleteBackup(backup.filename);
            await load();
          } catch (e) {
            Alert.alert("Hata", apiErrorMessage(e));
          } finally {
            setBusyFilename(null);
          }
        },
      },
    ]);
  }

  return (
    <View style={styles.container}>
      <Text style={styles.intro}>
        Sistem her hafta otomatik olarak yedeklenir (son {8} yedek saklanır). İsterseniz şimdi manuel bir yedek de
        alabilir, ya da bir yedeği indirip kendi bilgisayarınızda/Google Drive'da saklayabilirsiniz.
      </Text>

      <TouchableOpacity style={styles.primaryButton} onPress={handleRunNow} disabled={isRunning}>
        {isRunning ? <ActivityIndicator color="#0f172a" /> : <Text style={styles.primaryButtonText}>Şimdi Yedek Al</Text>}
      </TouchableOpacity>

      {isLoading ? (
        <ActivityIndicator color={colors.primary} style={{ marginTop: spacing(4) }} />
      ) : error ? (
        <ErrorRetry message={error} onRetry={load} />
      ) : (
        <FlatList
          data={backups}
          keyExtractor={(b) => b.filename}
          contentContainerStyle={{ paddingVertical: spacing(2) }}
          refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={colors.primary} />}
          ListEmptyComponent={<Text style={styles.empty}>Henüz yedek yok</Text>}
          renderItem={({ item }) => {
            const busy = busyFilename === item.filename;
            return (
              <View style={styles.card}>
                <Text style={styles.date}>{new Date(item.created_at).toLocaleString("tr-TR")}</Text>
                <Text style={styles.size}>{formatSize(item.size_bytes)}</Text>
                <View style={styles.actionsRow}>
                  <TouchableOpacity style={styles.actionButton} onPress={() => handleDownload(item)} disabled={busy}>
                    <Text style={styles.actionButtonText}>{busy ? "..." : "İndir"}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.actionButton, styles.restoreButton]}
                    onPress={() => handleRestore(item)}
                    disabled={busy}
                  >
                    <Text style={[styles.actionButtonText, styles.restoreButtonText]}>Geri Yükle</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.actionButton, styles.deleteButton]}
                    onPress={() => handleDelete(item)}
                    disabled={busy}
                  >
                    <Text style={[styles.actionButtonText, styles.deleteButtonText]}>Sil</Text>
                  </TouchableOpacity>
                </View>
              </View>
            );
          }}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing(2) },
  intro: { color: colors.textMuted, fontSize: 13, marginBottom: spacing(2), lineHeight: 18 },
  primaryButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
  },
  primaryButtonText: { color: "#0f172a", fontWeight: "700" },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(4) },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing(2),
    marginBottom: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.border,
  },
  date: { color: colors.text, fontSize: 14, fontWeight: "700" },
  size: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  actionsRow: { flexDirection: "row", gap: spacing(1), marginTop: spacing(1.5) },
  actionButton: {
    flex: 1,
    borderRadius: 8,
    paddingVertical: spacing(1),
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceAlt,
  },
  actionButtonText: { color: colors.text, fontSize: 12, fontWeight: "700" },
  restoreButton: { borderColor: colors.warning },
  restoreButtonText: { color: colors.warning },
  deleteButton: { borderColor: colors.danger },
  deleteButtonText: { color: colors.danger },
});
