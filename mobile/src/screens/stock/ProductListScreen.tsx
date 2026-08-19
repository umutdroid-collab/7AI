import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import Alert from "../../utils/alert";
import { bulkDeleteProducts, fetchProducts } from "../../api/services";
import { Product } from "../../types";
import { contentColumn } from "../../components/ui";
import { colors, spacing } from "../../theme";
import { apiErrorMessage } from "../../api/client";
import ErrorRetry from "../../components/ErrorRetry";

export default function ProductListScreen({ navigation }: any) {
  const [products, setProducts] = useState<Product[]>([]);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);

  const load = useCallback(async (q?: string) => {
    setError(null);
    try {
      const data = await fetchProducts(q || undefined);
      setProducts(data);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load(query);
    }, [load])
  );

  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsLoading(true);
      load(query);
    }, 300);
    return () => clearTimeout(timeout);
  }, [query, load]);

  const allSelected = useMemo(
    () => products.length > 0 && products.every((p) => selectedIds.has(p.id)),
    [products, selectedIds]
  );

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    setSelectedIds(allSelected ? new Set() : new Set(products.map((p) => p.id)));
  }

  function handleBulkDelete() {
    const count = selectedIds.size;
    if (count === 0) return;
    Alert.alert(
      "Ürünleri sil",
      `${count} ürün kalıcı olarak silinecek. Stok kaydı bulunan ürünler atlanacak. Emin misiniz?`,
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: "Sil",
          style: "destructive",
          onPress: async () => {
            setIsDeleting(true);
            try {
              const result = await bulkDeleteProducts(Array.from(selectedIds));
              setSelectedIds(new Set());
              await load(query);
              const parts = [`${result.deleted} ürün silindi`];
              if (result.errors.length) parts.push(`${result.errors.length} ürün atlandı (stok kaydı var)`);
              Alert.alert("Tamamlandı", parts.join("\n"));
            } catch (e) {
              Alert.alert("Hata", apiErrorMessage(e));
            } finally {
              setIsDeleting(false);
            }
          },
        },
      ]
    );
  }

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <TouchableOpacity style={styles.addButton} onPress={() => navigation.navigate("AddProduct")}>
          <Text style={styles.addButtonText}>+ Yeni Ürün</Text>
        </TouchableOpacity>

        <TextInput
          style={styles.search}
          placeholder="Ürün adı, ref no, ÜBB veya SUT kodu ara"
          placeholderTextColor={colors.textMuted}
          value={query}
          onChangeText={setQuery}
        />

        {products.length > 0 && (
          <View style={styles.selectRow}>
            <TouchableOpacity onPress={toggleSelectAll}>
              <Text style={styles.selectAllText}>{allSelected ? "Seçimi Kaldır" : "Tümünü Seç"}</Text>
            </TouchableOpacity>
            {selectedIds.size > 0 && (
              <TouchableOpacity style={styles.deleteSelectedButton} onPress={handleBulkDelete} disabled={isDeleting}>
                {isDeleting ? (
                  <ActivityIndicator color={colors.danger} size="small" />
                ) : (
                  <Text style={styles.deleteSelectedText}>Seçilenleri Sil ({selectedIds.size})</Text>
                )}
              </TouchableOpacity>
            )}
          </View>
        )}

        {isLoading ? (
          <ActivityIndicator color={colors.primary} style={{ marginTop: spacing(4) }} />
        ) : error ? (
          <ErrorRetry message={error} onRetry={() => load(query)} />
        ) : products.length === 0 ? (
          <Text style={styles.empty}>Ürün bulunamadı</Text>
        ) : (
          products.map((p) => (
            <View key={p.id} style={styles.row}>
              <TouchableOpacity style={styles.checkbox} onPress={() => toggleSelect(p.id)}>
                <View style={[styles.checkboxBox, selectedIds.has(p.id) && styles.checkboxBoxChecked]}>
                  {selectedIds.has(p.id) && <Text style={styles.checkboxMark}>✓</Text>}
                </View>
              </TouchableOpacity>
              <TouchableOpacity style={{ flex: 1 }} onPress={() => navigation.navigate("AddProduct", { product: p })}>
                <Text style={styles.name}>{p.name}</Text>
                <Text style={styles.meta}>
                  {p.reference_no}
                  {p.ubb_no ? `  •  ÜBB: ${p.ubb_no}` : ""}
                  {p.sut_kodu ? `  •  SUT: ${p.sut_kodu}` : ""}
                </Text>
              </TouchableOpacity>
            </View>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { ...contentColumn, padding: spacing(2) },
  addButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.5),
    alignItems: "center",
    marginBottom: spacing(2),
  },
  addButtonText: { color: "#0f172a", fontWeight: "700" },
  search: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing(1.5),
  },
  selectRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing(1.5),
  },
  selectAllText: { color: colors.primary, fontSize: 13, fontWeight: "700" },
  deleteSelectedButton: {
    borderRadius: 8,
    paddingHorizontal: spacing(1.5),
    paddingVertical: spacing(0.75),
    borderWidth: 1,
    borderColor: colors.danger,
  },
  deleteSelectedText: { color: colors.danger, fontSize: 12, fontWeight: "700" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: spacing(1.5),
    marginBottom: spacing(1),
    borderWidth: 1,
    borderColor: colors.border,
  },
  checkbox: { paddingRight: spacing(1.5), paddingVertical: spacing(0.5) },
  checkboxBox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  checkboxBoxChecked: { backgroundColor: colors.primary, borderColor: colors.primary },
  checkboxMark: { color: "#0f172a", fontSize: 14, fontWeight: "700" },
  name: { color: colors.text, fontWeight: "700", fontSize: 14 },
  meta: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  empty: { color: colors.textMuted, textAlign: "center", marginTop: spacing(4) },
});
