import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import Alert from "../../utils/alert";
import { createSalesTarget, fetchProducts, fetchUsers } from "../../api/services";
import { Product, User } from "../../types";
import { colors, spacing } from "../../theme";
import { apiErrorMessage } from "../../api/client";

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function toIsoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function currentMonthRange(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return { start: toIsoDate(start), end: toIsoDate(end) };
}

type TargetMode = "product" | "manual";

export default function AddSalesTargetScreen({ navigation }: any) {
  // Hedef ya bir ürüne bağlanır (ilerleme stok kullanımından otomatik sayılır)
  // ya da serbest yazılır (ilerlemeyi yönetici elle girer).
  const [mode, setMode] = useState<TargetMode>("product");
  const [manualTitle, setManualTitle] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [productQuery, setProductQuery] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  const [employees, setEmployees] = useState<User[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<User | null>(null);

  const [quantity, setQuantity] = useState("10");
  const defaultRange = currentMonthRange();
  const [periodStart, setPeriodStart] = useState(defaultRange.start);
  const [periodEnd, setPeriodEnd] = useState(defaultRange.end);
  const [note, setNote] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchUsers()
      .then((users) => setEmployees(users.filter((u) => u.role === "employee")))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!productQuery.trim()) {
      setProducts([]);
      return;
    }
    const timeout = setTimeout(() => {
      fetchProducts(productQuery).then(setProducts).catch(() => {});
    }, 250);
    return () => clearTimeout(timeout);
  }, [productQuery]);

  async function handleSubmit() {
    if (mode === "product" && !selectedProduct) {
      Alert.alert("Eksik bilgi", "Lütfen bir ürün seçin");
      return;
    }
    if (mode === "manual" && !manualTitle.trim()) {
      Alert.alert("Eksik bilgi", "Hedef için bir başlık yazın");
      return;
    }
    const qty = Number(quantity);
    if (!qty || qty <= 0) {
      Alert.alert("Geçersiz miktar", "Hedef adedi 0'dan büyük olmalı");
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(periodStart) || !/^\d{4}-\d{2}-\d{2}$/.test(periodEnd)) {
      Alert.alert("Geçersiz tarih", "Tarihleri YYYY-AA-GG formatında girin (örn. 2026-07-01)");
      return;
    }
    setIsSubmitting(true);
    try {
      await createSalesTarget({
        product_id: mode === "product" ? selectedProduct!.id : null,
        title: mode === "manual" ? manualTitle.trim() : undefined,
        assigned_user_id: selectedEmployee?.id ?? null,
        target_quantity: qty,
        period_start: periodStart,
        period_end: periodEnd,
        note: note || undefined,
      });
      Alert.alert("Başarılı", "Hedef eklendi", [{ text: "Tamam", onPress: () => navigation.goBack() }]);
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing(2) }} keyboardShouldPersistTaps="handled">
      <View style={styles.modeRow}>
        <TouchableOpacity
          style={[styles.modeButton, mode === "product" && styles.modeButtonActive]}
          onPress={() => setMode("product")}
        >
          <Text style={[styles.modeButtonText, mode === "product" && styles.modeButtonTextActive]}>
            Ürüne Bağlı
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.modeButton, mode === "manual" && styles.modeButtonActive]}
          onPress={() => setMode("manual")}
        >
          <Text style={[styles.modeButtonText, mode === "manual" && styles.modeButtonTextActive]}>
            Serbest Hedef
          </Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.modeHint}>
        {mode === "product"
          ? "İlerleme, ürün 'kullanıldı' olarak işaretlendikçe otomatik sayılır."
          : "İlerlemeyi Hedefler ekranındaki + / − düğmeleriyle siz girersiniz."}
      </Text>

      {mode === "manual" ? (
        <>
          <Text style={styles.label}>Hedef başlığı</Text>
          <TextInput
            style={styles.input}
            value={manualTitle}
            onChangeText={setManualTitle}
            placeholder="örn. 10 hastane ziyareti"
            placeholderTextColor={colors.textMuted}
          />
        </>
      ) : (
      <>
      <Text style={styles.label}>Ürün</Text>
          {selectedProduct ? (
            <TouchableOpacity style={styles.selectedBox} onPress={() => setSelectedProduct(null)}>
              <Text style={styles.selectedText}>{selectedProduct.name} ({selectedProduct.reference_no})</Text>
              <Text style={styles.changeText}>Değiştir</Text>
            </TouchableOpacity>
          ) : (
            <>
              <TextInput
                style={styles.input}
                placeholder="Ürün adı veya ref no ara"
                placeholderTextColor={colors.textMuted}
                value={productQuery}
                onChangeText={setProductQuery}
              />
              {products.slice(0, 6).map((p) => (
                <TouchableOpacity key={p.id} style={styles.option} onPress={() => setSelectedProduct(p)}>
                  <Text style={styles.optionText}>{p.name}</Text>
                  <Text style={styles.optionMeta}>
                    {p.reference_no}
                    {p.sut_kodu ? `  •  SUT: ${p.sut_kodu}` : ""}
                  </Text>
                </TouchableOpacity>
              ))}
            </>
          )}
      </>
      )}

      <Text style={styles.label}>Kime atanacak?</Text>
          <View style={styles.scopeRow}>
            <TouchableOpacity
              style={[styles.scopeChip, !selectedEmployee && styles.scopeChipActive]}
              onPress={() => setSelectedEmployee(null)}
            >
              <Text style={[styles.scopeChipText, !selectedEmployee && styles.scopeChipTextActive]}>Tüm Ekip</Text>
            </TouchableOpacity>
            {employees.map((emp) => (
              <TouchableOpacity
                key={emp.id}
                style={[styles.scopeChip, selectedEmployee?.id === emp.id && styles.scopeChipActive]}
                onPress={() => setSelectedEmployee(emp)}
              >
                <Text style={[styles.scopeChipText, selectedEmployee?.id === emp.id && styles.scopeChipTextActive]}>
                  {emp.full_name}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.label}>Hedef adet</Text>
          <TextInput
            style={styles.input}
            value={quantity}
            onChangeText={setQuantity}
            keyboardType="number-pad"
            placeholderTextColor={colors.textMuted}
          />

          <Text style={styles.label}>Başlangıç tarihi (YYYY-AA-GG)</Text>
          <TextInput
            style={styles.input}
            value={periodStart}
            onChangeText={setPeriodStart}
            placeholderTextColor={colors.textMuted}
          />

          <Text style={styles.label}>Bitiş tarihi (YYYY-AA-GG)</Text>
          <TextInput
            style={styles.input}
            value={periodEnd}
            onChangeText={setPeriodEnd}
            placeholderTextColor={colors.textMuted}
          />

          <Text style={styles.label}>Not (opsiyonel)</Text>
          <TextInput
            style={styles.input}
            value={note}
            onChangeText={setNote}
            placeholder="Örn. Temmuz ayı hedefi"
            placeholderTextColor={colors.textMuted}
          />

      <TouchableOpacity style={styles.submit} onPress={handleSubmit} disabled={isSubmitting}>
        {isSubmitting ? <ActivityIndicator color="#0f172a" /> : <Text style={styles.submitText}>Hedefi Kaydet</Text>}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  modeRow: { flexDirection: "row", gap: spacing(1), marginBottom: spacing(1) },
  modeButton: {
    flex: 1,
    paddingVertical: spacing(1.25),
    borderRadius: 10,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  modeButtonActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  modeButtonText: { color: colors.textMuted, fontSize: 13, fontWeight: "700" },
  modeButtonTextActive: { color: "#0f172a" },
  modeHint: { color: colors.textMuted, fontSize: 12, marginBottom: spacing(1.5), lineHeight: 17 },
  container: { flex: 1, backgroundColor: colors.background },
  label: { color: colors.textMuted, fontSize: 13, marginBottom: spacing(1), marginTop: spacing(1.5) },
  input: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  selectedBox: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.primary,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  selectedText: { color: colors.text, fontWeight: "600", flex: 1 },
  changeText: { color: colors.primary, fontSize: 12 },
  option: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: spacing(1.5),
    marginTop: spacing(0.5),
    borderWidth: 1,
    borderColor: colors.border,
  },
  optionText: { color: colors.text, fontWeight: "600" },
  optionMeta: { color: colors.textMuted, fontSize: 12 },
  scopeRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing(1) },
  scopeChip: {
    backgroundColor: colors.surface,
    borderRadius: 20,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1),
    borderWidth: 1,
    borderColor: colors.border,
  },
  scopeChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  scopeChipText: { color: colors.textMuted, fontSize: 13, fontWeight: "600" },
  scopeChipTextActive: { color: "#0f172a" },
  submit: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
    marginTop: spacing(3),
    marginBottom: spacing(4),
  },
  submitText: { color: "#0f172a", fontWeight: "700" },
});
