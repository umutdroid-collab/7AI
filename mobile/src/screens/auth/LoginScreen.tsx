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
import { colors, spacing } from "../../theme";
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
      <Text style={styles.title}>7AI Saha Uygulaması</Text>
      <Text style={styles.subtitle}>Stok, fatura ve klinik asistan tek yerde</Text>

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
  title: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "700",
    textAlign: "center",
  },
  subtitle: {
    color: colors.textMuted,
    fontSize: 14,
    textAlign: "center",
    marginTop: spacing(1),
    marginBottom: spacing(5),
  },
  form: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: spacing(3),
  },
  label: {
    color: colors.textMuted,
    fontSize: 13,
    marginBottom: spacing(0.5),
    marginTop: spacing(2),
  },
  input: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    fontSize: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  rememberRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginTop: spacing(2.5),
  },
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
  checkboxTick: { color: "#0f172a", fontSize: 14, fontWeight: "700", lineHeight: 18 },
  rememberTextWrap: { flex: 1 },
  rememberText: { color: colors.text, fontSize: 14, fontWeight: "600" },
  rememberHint: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  error: {
    color: colors.danger,
    marginTop: spacing(2),
  },
  button: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
    marginTop: spacing(4),
  },
  buttonText: {
    color: "#0f172a",
    fontWeight: "700",
    fontSize: 16,
  },
});
