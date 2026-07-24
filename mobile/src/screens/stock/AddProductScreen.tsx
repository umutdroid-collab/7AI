import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity } from "react-native";
import Alert from "../../utils/alert";
import { createProduct, updateProduct } from "../../api/services";
import { apiErrorMessage } from "../../api/client";
import { colors, spacing } from "../../theme";
import { Product } from "../../types";

export default function AddProductScreen({ navigation, route }: any) {
  const editingProduct: Product | undefined = route.params?.product;
  const fromAddStock: boolean = !!route.params?.fromAddStock;

  const [name, setName] = useState(editingProduct?.name ?? "");
  const [referenceNo, setReferenceNo] = useState(editingProduct?.reference_no ?? "");
  const [ubbNo, setUbbNo] = useState(editingProduct?.ubb_no ?? "");
  const [sutKodu, setSutKodu] = useState(editingProduct?.sut_kodu ?? "");
  const [manufacturer, setManufacturer] = useState(editingProduct?.manufacturer ?? "");
  const [unit, setUnit] = useState(editingProduct?.unit ?? "");
  const [notes, setNotes] = useState(editingProduct?.notes ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    navigation.setOptions({ title: editingProduct ? "Ürünü Düzenle" : "Yeni Ürün" });
  }, [navigation, editingProduct]);

  async function handleSubmit() {
    if (!name.trim() || !referenceNo.trim()) {
      Alert.alert("Eksik bilgi", "Ürün adı ve ref numarası zorunludur");
      return;
    }
    setIsSubmitting(true);
    try {
      const payload = {
        name: name.trim(),
        reference_no: referenceNo.trim(),
        ubb_no: ubbNo || undefined,
        sut_kodu: sutKodu || undefined,
        manufacturer: manufacturer || undefined,
        unit: unit || undefined,
        notes: notes || undefined,
      };
      if (editingProduct) {
        await updateProduct(editingProduct.id, payload);
        Alert.alert("Başarılı", "Ürün güncellendi", [{ text: "Tamam", onPress: () => navigation.goBack() }]);
      } else {
        const product = await createProduct(payload);
        if (fromAddStock) {
          navigation.navigate("AddStock", { newProduct: product });
        } else {
          Alert.alert("Başarılı", "Ürün eklendi", [{ text: "Tamam", onPress: () => navigation.goBack() }]);
        }
      }
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing(2) }}>
      <Text style={styles.label}>Ürün adı</Text>
      <TextInput style={styles.input} value={name} onChangeText={setName} placeholderTextColor={colors.textMuted} />

      <Text style={styles.label}>Ref numarası</Text>
      <TextInput
        style={styles.input}
        value={referenceNo}
        onChangeText={setReferenceNo}
        placeholderTextColor={colors.textMuted}
      />

      <Text style={styles.label}>ÜBB numarası</Text>
      <TextInput style={styles.input} value={ubbNo} onChangeText={setUbbNo} placeholderTextColor={colors.textMuted} />

      <Text style={styles.label}>SUT kodu</Text>
      <TextInput
        style={styles.input}
        value={sutKodu}
        onChangeText={setSutKodu}
        placeholderTextColor={colors.textMuted}
      />

      <Text style={styles.label}>Üretici</Text>
      <TextInput
        style={styles.input}
        value={manufacturer}
        onChangeText={setManufacturer}
        placeholderTextColor={colors.textMuted}
      />

      <Text style={styles.label}>Birim</Text>
      <TextInput style={styles.input} value={unit} onChangeText={setUnit} placeholderTextColor={colors.textMuted} />

      <Text style={styles.label}>Notlar</Text>
      <TextInput style={styles.input} value={notes} onChangeText={setNotes} placeholderTextColor={colors.textMuted} />

      <TouchableOpacity style={styles.submit} onPress={handleSubmit} disabled={isSubmitting}>
        {isSubmitting ? (
          <ActivityIndicator color="#0f172a" />
        ) : (
          <Text style={styles.submitText}>{editingProduct ? "Güncelle" : "Kaydet"}</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
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
