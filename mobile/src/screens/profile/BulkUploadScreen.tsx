import React, { useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import * as DocumentPicker from "expo-document-picker";
import Alert from "../../utils/alert";
import {
  BulkUploadResult,
  bulkUploadHospitals,
  bulkUploadInvoices,
  bulkUploadProducts,
  bulkUploadStock,
} from "../../api/services";
import { apiErrorMessage } from "../../api/client";
import { colors, spacing } from "../../theme";

/**
 * Yüzlerce satırlık bir dosyada hataların neredeyse tamamı aynı birkaç
 * sebepten kaynaklanır (örn. "ürün bulunamadı"). Hepsini tek tek listelemek
 * yerine sebebe göre gruplayıp kaç satırı etkilediğini ve birkaç örnek satır
 * numarasını gösteriyoruz - yalnızca "144 satırda hata var" demek kullanıcıya
 * neyi düzelteceğini söylemiyordu.
 */
export function summarizeErrors(errors: { row?: number; file?: string; message: string }[]): string[] {
  const groups = new Map<string, { count: number; samples: string[] }>();
  for (const error of errors) {
    // Mesajlardaki tırnak içindeki değerler satırdan satıra değişir
    // ("Ref no 'A-1' bulunamadı"), gruplamak için sabitlenir.
    const key = (error.message || "Bilinmeyen hata").replace(/'[^']*'/g, "'…'");
    const group = groups.get(key) ?? { count: 0, samples: [] };
    group.count += 1;
    const label = error.row !== undefined ? `satır ${error.row}` : error.file;
    if (label && group.samples.length < 3) group.samples.push(label);
    groups.set(key, group);
  }

  return [...groups.entries()]
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 4)
    .map(([message, group]) => {
      const where = group.samples.length ? ` (örn. ${group.samples.join(", ")})` : "";
      return `• ${message} — ${group.count} satır${where}`;
    });
}

function resultMessage(result: BulkUploadResult): string {
  const parts = [`${result.created} kayıt eklendi`];
  if (result.skipped) parts.push(`${result.skipped} kayıt zaten vardı, atlandı`);
  if (result.errors?.length) {
    parts.push(`\n${result.errors.length} satır eklenemedi:`);
    parts.push(...summarizeErrors(result.errors));
  }
  return parts.join("\n");
}

function CsvUploadSection({
  title,
  description,
  columns,
  onUpload,
}: {
  title: string;
  description: string;
  columns: string;
  onUpload: (fileUri: string, fileName: string, webFile?: File | Blob | null) => Promise<BulkUploadResult>;
}) {
  const [isUploading, setIsUploading] = useState(false);

  async function handlePick() {
    const result = await DocumentPicker.getDocumentAsync({ type: "*/*", copyToCacheDirectory: true });
    if (result.canceled || !result.assets?.length) return;
    const file = result.assets[0];
    if (!(file.name || "").toLowerCase().endsWith(".csv")) {
      Alert.alert("CSV dosyası seçin", "Lütfen .csv uzantılı bir dosya seçin (Excel'den 'CSV olarak kaydet' ile alabilirsiniz)");
      return;
    }
    setIsUploading(true);
    try {
      const uploadResult = await onUpload(file.uri, file.name || "veri.csv", file.file);
      Alert.alert("Yükleme tamamlandı", resultMessage(uploadResult));
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text style={styles.cardDescription}>{description}</Text>
      <Text style={styles.columns}>Sütunlar: {columns}</Text>
      <TouchableOpacity style={styles.primaryButton} onPress={handlePick} disabled={isUploading}>
        {isUploading ? (
          <ActivityIndicator color="#0f172a" />
        ) : (
          <Text style={styles.primaryButtonText}>CSV Dosyası Seç ve Yükle</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

function InvoiceUploadSection() {
  const [isUploading, setIsUploading] = useState(false);

  async function handlePick() {
    const result = await DocumentPicker.getDocumentAsync({
      type: "application/pdf",
      copyToCacheDirectory: true,
      multiple: true,
    });
    if (result.canceled || !result.assets?.length) return;
    setIsUploading(true);
    try {
      const files = result.assets.map((a) => ({ uri: a.uri, name: a.name || "fatura.pdf", webFile: a.file }));
      const uploadResult = await bulkUploadInvoices(files);
      const parts = [`${uploadResult.created} fatura yüklendi`];
      if (uploadResult.errors?.length) {
        parts.push(`\n${uploadResult.errors.length} dosyada sorun var:`);
        parts.push(...summarizeErrors(uploadResult.errors));
      }
      Alert.alert("Yükleme tamamlandı", parts.join("\n"));
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Faturalar</Text>
      <Text style={styles.cardDescription}>
        Birden fazla fatura PDF'ini aynı anda seçip yükleyin. Her PDF otomatik olarak okunur (fatura no, tarih,
        vade, tutar).
      </Text>
      <TouchableOpacity style={styles.primaryButton} onPress={handlePick} disabled={isUploading}>
        {isUploading ? (
          <ActivityIndicator color="#0f172a" />
        ) : (
          <Text style={styles.primaryButtonText}>PDF Dosyaları Seç ve Yükle</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

export default function BulkUploadScreen() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing(2) }}>
      <Text style={styles.intro}>
        Excel'de hazırladığınız listeleri "CSV olarak kaydet" ile kaydedip buradan tek seferde yükleyebilirsiniz.
        İlk satır sütun başlıkları olmalı.
      </Text>

      <CsvUploadSection
        title="Hastaneler"
        description="Tüm hastanelerinizi tek CSV dosyasıyla ekleyin. Aynı isimde hastane varsa atlanır."
        columns="name (zorunlu), city, address, contact_person, contact_phone"
        onUpload={bulkUploadHospitals}
      />

      <CsvUploadSection
        title="Ürünler"
        description="Tüm ürün kartlarınızı tek CSV dosyasıyla ekleyin. Aynı ref no'ya sahip ürün varsa atlanır."
        columns="name, reference_no (zorunlu), ubb_no, sut_kodu, manufacturer, unit, notes"
        onUpload={bulkUploadProducts}
      />

      <CsvUploadSection
        title="Stok"
        description="Ürünler ve hastaneler sistemde kayıtlıysa, stok girişlerini toplu ekleyin. hospital_name boş bırakılırsa depo/araç dışı stok olarak eklenir."
        columns="reference_no, lot_no, skt (zorunlu), serial_no, quantity, hospital_name"
        onUpload={bulkUploadStock}
      />

      <InvoiceUploadSection />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  intro: { color: colors.textMuted, fontSize: 13, marginBottom: spacing(2), lineHeight: 18 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing(2),
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing(2),
  },
  cardTitle: { color: colors.text, fontSize: 15, fontWeight: "700", marginBottom: spacing(0.5) },
  cardDescription: { color: colors.textMuted, fontSize: 13, marginBottom: spacing(1), lineHeight: 18 },
  columns: { color: colors.textMuted, fontSize: 11, fontStyle: "italic", marginBottom: spacing(1.5) },
  primaryButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
  },
  primaryButtonText: { color: "#0f172a", fontWeight: "700" },
});
