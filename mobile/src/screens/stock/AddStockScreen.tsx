import React, { useCallback, useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import Alert from "../../utils/alert";
import { useFocusEffect } from "@react-navigation/native";
import { createStockItem, fetchHospitals, fetchProducts } from "../../api/services";
import { Hospital, Product } from "../../types";
import { colors, spacing } from "../../theme";
import { apiErrorMessage } from "../../api/client";
import HospitalPickerModal from "../../components/HospitalPickerModal";

export default function AddStockScreen({ navigation, route }: any) {
  const [products, setProducts] = useState<Product[]>([]);
  const [productQuery, setProductQuery] = useState("");
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [searchState, setSearchState] = useState<"idle" | "searching" | "done" | "error">("idle");

  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [selectedHospitalId, setSelectedHospitalId] = useState<number | null>(null);
  const [isPickerVisible, setIsPickerVisible] = useState(false);

  const [lotNo, setLotNo] = useState("");
  const [serialNo, setSerialNo] = useState("");
  const [skt, setSkt] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useFocusEffect(
    useCallback(() => {
      fetchHospitals().then(setHospitals).catch(() => {});
    }, [])
  );

  useEffect(() => {
    if (route.params?.newProduct) {
      setSelectedProduct(route.params.newProduct);
    }
  }, [route.params?.newProduct]);

  useEffect(() => {
    if (!productQuery.trim()) {
      setProducts([]);
      setSearchState("idle");
      return;
    }
    setSearchState("searching");
    const timeout = setTimeout(() => {
      fetchProducts(productQuery)
        .then((found) => {
          setProducts(found);
          setSearchState("done");
        })
        .catch(() => {
          setProducts([]);
          // Hata da sessiz kalmamalı: eskiden arama patlasa bile ekranda
          // "sonuç yok" ile aynı boşluk görünüyordu.
          setSearchState("error");
        });
    }, 250);
    return () => clearTimeout(timeout);
  }, [productQuery]);

  async function handleSubmit() {
    if (!selectedProduct) {
      Alert.alert("Eksik bilgi", "Lütfen bir ürün seçin");
      return;
    }
    if (!lotNo) {
      Alert.alert("Eksik bilgi", "Lot numarası zorunludur");
      return;
    }
    // SKT opsiyonel; ama girildiyse formatı doğru olmalı.
    if (skt && !/^\d{4}-\d{2}-\d{2}$/.test(skt)) {
      Alert.alert("Geçersiz tarih", "SKT tarihini YYYY-AA-GG formatında girin (örn. 2026-12-31)");
      return;
    }
    setIsSubmitting(true);
    try {
      await createStockItem({
        product_id: selectedProduct.id,
        lot_no: lotNo,
        serial_no: serialNo || undefined,
        skt: skt || undefined,
        quantity: Number(quantity) || 1,
        hospital_id: selectedHospitalId,
      });
      Alert.alert("Başarılı", "Stok kaydı eklendi", [{ text: "Tamam", onPress: () => navigation.goBack() }]);
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.label}>Ürün</Text>
      {selectedProduct ? (
        <TouchableOpacity style={styles.selectedProduct} onPress={() => setSelectedProduct(null)}>
          <Text style={styles.selectedProductText}>{selectedProduct.name} ({selectedProduct.reference_no})</Text>
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
          {/* FlatList yerine düz View: React Native Web'de iç içe listeler
              yükseklik alamayıp görünmez olabiliyor (aynı sorun fatura filtre
              çiplerinde de yaşanmıştı). Sonuç sayısı zaten küçük. */}
          {products.length > 0 && (
            <ScrollView style={styles.productList} keyboardShouldPersistTaps="handled" nestedScrollEnabled>
              {products.map((item) => (
                <TouchableOpacity
                  key={item.id}
                  style={styles.productOption}
                  onPress={() => setSelectedProduct(item)}
                >
                  <Text style={styles.productOptionText}>{item.name}</Text>
                  <Text style={styles.productOptionMeta}>
                    {item.reference_no}
                    {item.sut_kodu ? `  •  SUT: ${item.sut_kodu}` : ""}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          )}

          {/* Eskiden sonuç yokken ekranda hiçbir şey görünmüyordu; kullanıcı
              "ürün yok" ile "arama bozuk"u ayırt edemiyordu. */}
          {searchState === "searching" && <Text style={styles.searchHint}>Aranıyor...</Text>}
          {searchState === "error" && (
            <Text style={styles.searchError}>Ürün araması başarısız oldu. Bağlantınızı kontrol edin.</Text>
          )}
          {searchState === "done" && products.length === 0 && (
            <Text style={styles.searchHint}>
              "{productQuery.trim()}" için ürün bulunamadı. Ürün listesinde kayıtlı değilse aşağıdan
              ekleyebilirsiniz.
            </Text>
          )}

          <TouchableOpacity
            style={styles.addProductButton}
            onPress={() =>
              navigation.navigate("AddProduct", {
                fromAddStock: true,
                // Aranan metni ref no olarak taşı - kullanıcı aynı kodu ikinci
                // kez yazmak zorunda kalmasın.
                initialReferenceNo: productQuery.trim(),
              })
            }
          >
            <Text style={styles.addProductButtonText}>+ Yeni Ürün Ekle</Text>
          </TouchableOpacity>
        </>
      )}

      <Text style={styles.label}>Lot numarası</Text>
      <TextInput style={styles.input} value={lotNo} onChangeText={setLotNo} placeholderTextColor={colors.textMuted} />

      <Text style={styles.label}>Seri numarası (opsiyonel)</Text>
      <TextInput style={styles.input} value={serialNo} onChangeText={setSerialNo} placeholderTextColor={colors.textMuted} />

      <Text style={styles.label}>SKT (YYYY-AA-GG) — opsiyonel</Text>
      <TextInput
        style={styles.input}
        value={skt}
        onChangeText={setSkt}
        placeholder="2026-12-31 (bilinmiyorsa boş bırakın)"
        placeholderTextColor={colors.textMuted}
      />

      <Text style={styles.label}>Miktar</Text>
      <TextInput
        style={styles.input}
        value={quantity}
        onChangeText={setQuantity}
        keyboardType="number-pad"
        placeholderTextColor={colors.textMuted}
      />

      <Text style={styles.label}>Konum</Text>
      <TouchableOpacity style={styles.hospitalSelect} onPress={() => setIsPickerVisible(true)}>
        <Text style={styles.hospitalSelectText}>
          {selectedHospitalId ? hospitals.find((h) => h.id === selectedHospitalId)?.name : "Depo"}
        </Text>
        <Text style={styles.hospitalSelectChevron}>▾</Text>
      </TouchableOpacity>

      <HospitalPickerModal
        visible={isPickerVisible}
        hospitals={hospitals}
        onSelect={setSelectedHospitalId}
        onClose={() => setIsPickerVisible(false)}
        extraOptions={[{ id: null, name: "Depo" }]}
      />

      <TouchableOpacity style={styles.submit} onPress={handleSubmit} disabled={isSubmitting}>
        <Text style={styles.submitText}>Kaydet</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing(2) },
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
  selectedProduct: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.primary,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  selectedProductText: { color: colors.text, fontWeight: "600", flex: 1 },
  changeText: { color: colors.primary, fontSize: 12 },
  productList: { maxHeight: 200 },
  searchHint: { color: colors.textMuted, fontSize: 12, marginTop: spacing(0.5), lineHeight: 17 },
  searchError: { color: colors.danger, fontSize: 12, marginTop: spacing(0.5) },
  productOption: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: spacing(1.5),
    marginTop: spacing(0.5),
    borderWidth: 1,
    borderColor: colors.border,
  },
  productOptionText: { color: colors.text, fontWeight: "600" },
  productOptionMeta: { color: colors.textMuted, fontSize: 12 },
  addProductButton: {
    borderRadius: 10,
    paddingVertical: spacing(1.5),
    alignItems: "center",
    marginTop: spacing(1),
    borderWidth: 1,
    borderColor: colors.primary,
    borderStyle: "dashed",
  },
  addProductButtonText: { color: colors.primary, fontWeight: "700", fontSize: 13 },
  hospitalSelect: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    borderWidth: 1,
    borderColor: colors.border,
  },
  hospitalSelectText: { color: colors.text, fontSize: 14, fontWeight: "600" },
  hospitalSelectChevron: { color: colors.textMuted },
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
