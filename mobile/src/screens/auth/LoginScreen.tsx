import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useAuth } from "../../context/AuthContext";
import { apiErrorMessage } from "../../api/client";
import { colors, layout, radius, spacing, typography } from "../../theme";
import Icon from "../../components/Icon";
import {
  clearRememberedLogin,
  loadRememberedLogin,
  saveRememberedLogin,
} from "../../utils/rememberedLogin";

export default function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    loadRememberedLogin().then((saved) => {
      if (!saved.remember) return;
      setRemember(true);
      setEmail(saved.email);
      setPassword(saved.password);
    });
  }, []);

  async function handleSubmit() {
    setError(null);
    if (!email || !password) {
      setError("E-posta ve şifre gerekli");
      return;
    }
    setIsSubmitting(true);
    try {
      await login(email.trim(), password);
      // Kayıt yalnızca giriş BAŞARILI olduktan sonra yapılır; yanlış yazılmış
      // bir şifreyi saklayıp her açılışta tekrar denetmenin anlamı yok.
      if (remember) {
        await saveRememberedLogin(email.trim(), password);
      } else {
        await clearRememberedLogin();
      }
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleToggleRemember() {
    const next = !remember;
    setRemember(next);
    // İşaret kaldırıldığı anda saklananlar silinsin - kullanıcı "artık
    // hatırlama" dediğinde bir sonraki girişi beklemek gerekmemeli.
    if (!next) await clearRememberedLogin();
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.brand}>
        <View style={styles.brandMark}>
          <Icon name="stock" size={26} color={colors.primary} />
        </View>
        <Text style={styles.title}>7AI Saha Uygulaması</Text>
        <Text style={styles.subtitle}>Stok, fatura ve klinik asistan tek yerde</Text>
      </View>

      <View style={styles.form}>
        <Text style={styles.label}>E-posta</Text>
        <TextInput
          style={styles.input}
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
          placeholder="ornek@sirket.com"
          placeholderTextColor={colors.textMuted}
        />

        <Text style={styles.label}>Şifre</Text>
        <TextInput
          style={styles.input}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          placeholder="••••••••"
          placeholderTextColor={colors.textMuted}
        />

        <TouchableOpacity
          style={styles.rememberRow}
          onPress={handleToggleRemember}
          accessibilityRole="checkbox"
          accessibilityState={{ checked: remember }}
        >
          <View style={[styles.checkbox, remember && styles.checkboxChecked]}>
            {remember && <Text style={styles.checkboxTick}>✓</Text>}
          </View>
          <View style={styles.rememberTextWrap}>
            <Text style={styles.rememberText}>Beni hatırla</Text>
            <Text style={styles.rememberHint}>
              Giriş bilgileriniz bu cihazda saklanır ve oturumunuz 24 saat açık kalır.
            </Text>
          </View>
        </TouchableOpacity>

        {error && <Text style={styles.error}>{error}</Text>}

        <TouchableOpacity style={styles.button} onPress={handleSubmit} disabled={isSubmitting}>
          {isSubmitting ? (
            <ActivityIndicator color={colors.background} />
          ) : (
            <Text style={styles.buttonText}>Giriş Yap</Text>
          )}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: "center",
    paddingHorizontal: spacing(3),
  },
  brand: { alignItems: "center", marginBottom: spacing(4) },
  brandMark: {
    width: 56,
    height: 56,
    borderRadius: radius.lg,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primaryTint,
    borderWidth: 1,
    borderColor: colors.primary,
    marginBottom: spacing(2),
  },
  title: { color: colors.text, fontSize: 24, fontWeight: "700", textAlign: "center" },
  subtitle: {
    ...typography.body,
    color: colors.textMuted,
    textAlign: "center",
    marginTop: spacing(0.5),
  },
  form: {
    // Masaüstünde form tüm pencereye yayılmasın.
    width: "100%",
    maxWidth: 420,
    alignSelf: "center",
    backgroundColor: colors.card,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    padding: spacing(3),
  },
  label: {
    ...typography.meta,
    color: colors.textMuted,
    marginBottom: spacing(0.75),
    marginTop: spacing(2),
  },
  input: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    paddingHorizontal: layout.cardPadding,
    paddingVertical: spacing(1.5),
    color: colors.text,
    fontSize: 15,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  rememberRow: { flexDirection: "row", alignItems: "flex-start", marginTop: spacing(2.5) },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing(1.5),
  },
  checkboxChecked: { backgroundColor: colors.primary, borderColor: colors.primary },
  checkboxTick: { color: colors.onPrimary, fontSize: 14, fontWeight: "700", lineHeight: 18 },
  rememberTextWrap: { flex: 1 },
  rememberText: { ...typography.bodyStrong, color: colors.text },
  rememberHint: { ...typography.meta, color: colors.textMuted, marginTop: 2, lineHeight: 16 },
  error: { color: colors.danger, ...typography.body, marginTop: spacing(2) },
  button: {
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: spacing(1.75),
    alignItems: "center",
    marginTop: spacing(3),
  },
  buttonText: { color: colors.onPrimary, fontWeight: "700", fontSize: 15 },
});
