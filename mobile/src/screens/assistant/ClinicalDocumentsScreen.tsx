import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import * as DocumentPicker from "expo-document-picker";
import Alert from "../../utils/alert";
import {
  bulkUploadClinicalDocuments,
  deleteClinicalDocument,
  fetchClinicalDocuments,
} from "../../api/services";
import { ClinicalDocument } from "../../types";
import { apiErrorMessage } from "../../api/client";
import { colors, spacing } from "../../theme";
import Icon from "../../components/Icon";
import ErrorRetry from "../../components/ErrorRetry";

function formatSize(bytes: number): string {
  if (!bytes) return "-";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ClinicalDocumentsScreen() {
  const [documents, setDocuments] = useState<ClinicalDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setDocuments(await fetchClinicalDocuments());
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

  async function handleUpload() {
    const result = await DocumentPicker.getDocumentAsync({
      type: "application/pdf",
      copyToCacheDirectory: true,
      multiple: true,
    });
    if (result.canceled || !result.assets?.length) return;

    setIsUploading(true);
    try {
      const files = result.assets.map((a) => ({
        uri: a.uri,
        name: a.name || "calisma.pdf",
        webFile: a.file,
      }));
      const uploadResult = await bulkUploadClinicalDocuments(files);
      await load();
      const parts = [`${uploadResult.created} klinik çalışma eklendi ve indekslendi`];
      if (uploadResult.errors?.length) {
        parts.push(`${uploadResult.errors.length} dosyada sorun var:`);
        uploadResult.errors.slice(0, 3).forEach((e: any) => parts.push(`• ${e.message}`));
      }
      Alert.alert("Yükleme tamamlandı", parts.join("\n"));
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsUploading(false);
    }
  }

  function handleDelete(doc: ClinicalDocument) {
    Alert.alert(
      "Klinik çalışmayı sil",
      `"${doc.title || doc.filename}" silinecek. Asistan bundan sonra bu çalışmadan alıntı yapmayacak.`,
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: "Sil",
          style: "destructive",
          onPress: async () => {
            setBusyId(doc.id);
            try {
              await deleteClinicalDocument(doc.id);
              await load();
            } catch (e) {
              Alert.alert("Hata", apiErrorMessage(e));
            } finally {
              setBusyId(null);
            }
          },
        },
      ]
    );
  }

  const totalSize = documents.reduce((sum, d) => sum + (d.file_size || 0), 0);

  return (
    <View style={styles.container}>
      <Text style={styles.intro}>
        Klinik Asistan yalnızca buradaki çalışmalara ve PubMed'e dayanarak cevap verir. Birden fazla PDF'i aynı
        anda seçebilirsiniz.
      </Text>

      <TouchableOpacity style={styles.primaryButton} onPress={handleUpload} disabled={isUploading}>
        {isUploading ? (
          <ActivityIndicator color="#0f172a" />
        ) : (
          <View style={styles.primaryButtonRow}>
            <Icon name="upload" size={16} color={colors.onPrimary} />
            <Text style={styles.primaryButtonText}>Klinik Çalışma Ekle (PDF)</Text>
          </View>
        )}
      </TouchableOpacity>

      {documents.length > 0 && (
        <Text style={styles.summary}>
          {documents.length} çalışma · toplam {formatSize(totalSize)}
        </Text>
      )}

      {isLoading ? (
        <ActivityIndicator color={colors.primary} style={{ marginTop: spacing(4) }} />
      ) : error ? (
        <ErrorRetry message={error} onRetry={load} />
      ) : (
        <FlatList
          data={documents}
          keyExtractor={(d) => String(d.id)}
          contentContainerStyle={{ paddingVertical: spacing(1), paddingBottom: spacing(3) }}
          refreshControl={<RefreshControl refreshing={false} onRefresh={load} tintColor={colors.primary} />}
          ListEmptyComponent={<Text style={styles.empty}>Henüz klinik çalışma eklenmemiş</Text>}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={{ flex: 1 }}>
                <Text style={styles.title} numberOfLines={2}>
                  {item.title || item.filename}
                </Text>
                <Text style={styles.filename} numberOfLines={1} ellipsizeMode="middle">
                  {item.filename}
                </Text>
                <Text style={styles.meta}>
                  {formatSize(item.file_size)} · {item.num_chunks} bölüm ·{" "}
                  {new Date(item.indexed_at).toLocaleDateString("tr-TR")}
                </Text>
              </View>
              <TouchableOpacity
                style={styles.deleteButton}
                onPress={() => handleDelete(item)}
                disabled={busyId === item.id}
              >
                {busyId === item.id ? (
                  <Text style={styles.deleteButtonText}>...</Text>
                ) : (
                  <Icon name="trash" size={16} color={colors.textMuted} />
                )}
              </TouchableOpacity>
            </View>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  primaryButtonRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  container: { flex: 1, backgroundColor: colors.background, padding: spacing(2) },
  intro: { color: colors.textMuted, fontSize: 13, marginBottom: spacing(2), lineHeight: 18 },
  primaryButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
  },
  primaryButtonText: { color: "#0f172a", fontWeight: "700" },
  summary: { color: colors.textMuted, fontSize: 12, marginTop: spacing(1.5) },
  card: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: spacing(1.75),
    marginTop: spacing(1.25),
    borderWidth: 1,
    borderColor: colors.border,
  },
  title: { color: colors.text, fontSize: 14, fontWeight: "700" },
  filename: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  meta: { color: colors.textMuted, fontSize: 12, marginTop: 4 },
  deleteButton: { paddingHorizontal: spacing(1.5), paddingVertical: spacing(1) },
  deleteButtonText: { fontSize: 18 },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(4) },
});
