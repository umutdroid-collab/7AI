import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import Alert from "../../utils/alert";
import { useAuth } from "../../context/AuthContext";
import {
  changePassword,
  createUser,
  fetchUsers,
  setEmailNotifications,
  setUserActive,
} from "../../api/services";
import { apiErrorMessage } from "../../api/client";
import { User } from "../../types";
import { colors, spacing } from "../../theme";

const ROLE_LABELS: Record<string, string> = { admin: "Yönetici", employee: "Çalışan" };

export default function ProfileScreen() {
  const { user, logout, updateUser } = useAuth();
  const navigation = useNavigation<any>();
  const [isSavingEmailPref, setIsSavingEmailPref] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  const [users, setUsers] = useState<User[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [showAddUser, setShowAddUser] = useState(false);
  const [newFullName, setNewFullName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newRole, setNewRole] = useState<"admin" | "employee">("employee");
  const [isCreatingUser, setIsCreatingUser] = useState(false);

  const loadUsers = useCallback(() => {
    if (user?.role !== "admin") return;
    setIsLoadingUsers(true);
    fetchUsers()
      .then(setUsers)
      .catch(() => {})
      .finally(() => setIsLoadingUsers(false));
  }, [user]);

  useFocusEffect(
    useCallback(() => {
      loadUsers();
    }, [loadUsers])
  );

  async function handleChangePassword() {
    if (!currentPassword || !newPassword) {
      Alert.alert("Eksik bilgi", "Mevcut ve yeni şifreyi girin");
      return;
    }
    if (newPassword.length < 8) {
      Alert.alert("Şifre çok kısa", "Yeni şifre en az 8 karakter olmalı");
      return;
    }
    if (newPassword !== confirmPassword) {
      Alert.alert("Şifreler eşleşmiyor", "Yeni şifre ile onay alanı aynı olmalı");
      return;
    }
    setIsChangingPassword(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      Alert.alert("Başarılı", "Şifreniz güncellendi");
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsChangingPassword(false);
    }
  }

  async function handleCreateUser() {
    if (!newFullName || !newEmail || !newUserPassword) {
      Alert.alert("Eksik bilgi", "Ad, e-posta ve şifre gerekli");
      return;
    }
    setIsCreatingUser(true);
    try {
      await createUser({ full_name: newFullName, email: newEmail, password: newUserPassword, role: newRole });
      setNewFullName("");
      setNewEmail("");
      setNewUserPassword("");
      setNewRole("employee");
      setShowAddUser(false);
      loadUsers();
      Alert.alert("Başarılı", "Kullanıcı eklendi");
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsCreatingUser(false);
    }
  }

  async function handleToggleActive(target: User) {
    const nextActive = !target.is_active;
    Alert.alert(
      nextActive ? "Aktifleştir" : "Pasifleştir",
      `${target.full_name} kullanıcısını ${nextActive ? "aktifleştirmek" : "pasifleştirmek"} istiyor musunuz?`,
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: "Onayla",
          onPress: async () => {
            try {
              await setUserActive(target.id, nextActive);
              loadUsers();
            } catch (e) {
              Alert.alert("Hata", apiErrorMessage(e));
            }
          },
        },
      ]
    );
  }

  async function handleToggleEmailNotifications(enabled: boolean) {
    setIsSavingEmailPref(true);
    try {
      const updated = await setEmailNotifications(enabled);
      updateUser(updated);
    } catch (e) {
      Alert.alert("Hata", apiErrorMessage(e));
    } finally {
      setIsSavingEmailPref(false);
    }
  }

  function handleLogout() {
    Alert.alert("Çıkış yap", `${user?.full_name} olarak çıkış yapmak istiyor musunuz?`, [
      { text: "Vazgeç", style: "cancel" },
      { text: "Çıkış yap", style: "destructive", onPress: logout },
    ]);
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: spacing(2) }}>
      <View style={styles.card}>
        <Text style={styles.name}>{user?.full_name}</Text>
        <Text style={styles.email}>{user?.email}</Text>
        <View style={styles.roleBadge}>
          <Text style={styles.roleBadgeText}>{ROLE_LABELS[user?.role ?? ""] ?? user?.role}</Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>Bildirimler</Text>
      <View style={styles.card}>
        <View style={styles.prefRow}>
          <View style={{ flex: 1, marginRight: spacing(2) }}>
            <Text style={styles.prefTitle}>Günlük e-posta özeti</Text>
            <Text style={styles.prefSubtitle}>
              Her sabah vadesi yaklaşan/geçmiş faturalar ve SKT'si yaklaşan stoklar {user?.email} adresine
              gönderilir.
            </Text>
          </View>
          {isSavingEmailPref ? (
            <ActivityIndicator color={colors.primary} />
          ) : (
            <Switch
              value={user?.email_notifications_enabled ?? true}
              onValueChange={handleToggleEmailNotifications}
              trackColor={{ false: colors.border, true: colors.primary }}
              thumbColor="#f1f5f9"
            />
          )}
        </View>
      </View>

      <Text style={styles.sectionTitle}>Şifre Değiştir</Text>
      <View style={styles.card}>
        <TextInput
          style={styles.input}
          placeholder="Mevcut şifre"
          placeholderTextColor={colors.textMuted}
          secureTextEntry
          value={currentPassword}
          onChangeText={setCurrentPassword}
        />
        <TextInput
          style={styles.input}
          placeholder="Yeni şifre (en az 8 karakter)"
          placeholderTextColor={colors.textMuted}
          secureTextEntry
          value={newPassword}
          onChangeText={setNewPassword}
        />
        <TextInput
          style={styles.input}
          placeholder="Yeni şifre (tekrar)"
          placeholderTextColor={colors.textMuted}
          secureTextEntry
          value={confirmPassword}
          onChangeText={setConfirmPassword}
        />
        <TouchableOpacity style={styles.primaryButton} onPress={handleChangePassword} disabled={isChangingPassword}>
          {isChangingPassword ? (
            <ActivityIndicator color="#0f172a" />
          ) : (
            <Text style={styles.primaryButtonText}>Şifreyi Güncelle</Text>
          )}
        </TouchableOpacity>
      </View>

      {user?.role === "admin" && (
        <>
          <Text style={styles.sectionTitle}>Toplu Veri Ekleme</Text>
          <TouchableOpacity style={styles.bulkUploadCard} onPress={() => navigation.navigate("BulkUpload")}>
            <View style={{ flex: 1 }}>
              <Text style={styles.bulkUploadTitle}>Hastane, ürün, stok ve fatura yükle</Text>
              <Text style={styles.bulkUploadSubtitle}>CSV veya PDF dosyalarıyla tek seferde toplu ekleme yapın</Text>
            </View>
            <Text style={styles.bulkUploadChevron}>›</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.bulkUploadCard} onPress={() => navigation.navigate("Backups")}>
            <View style={{ flex: 1 }}>
              <Text style={styles.bulkUploadTitle}>Yedekler</Text>
              <Text style={styles.bulkUploadSubtitle}>Haftalık otomatik yedekleri görüntüle, indir veya geri yükle</Text>
            </View>
            <Text style={styles.bulkUploadChevron}>›</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.bulkUploadCard} onPress={() => navigation.navigate("ClinicalDocuments")}>
            <View style={{ flex: 1 }}>
              <Text style={styles.bulkUploadTitle}>Klinik Çalışmalar</Text>
              <Text style={styles.bulkUploadSubtitle}>Asistanın kullandığı çalışmaları görüntüle, ekle veya sil</Text>
            </View>
            <Text style={styles.bulkUploadChevron}>›</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.bulkUploadCard} onPress={() => navigation.navigate("AuditLog")}>
            <View style={{ flex: 1 }}>
              <Text style={styles.bulkUploadTitle}>İşlem Günlüğü</Text>
              <Text style={styles.bulkUploadSubtitle}>Kim neyi sildi, değiştirdi veya geri yükledi</Text>
            </View>
            <Text style={styles.bulkUploadChevron}>›</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.bulkUploadCard} onPress={() => navigation.navigate("FollowUps")}>
            <View style={{ flex: 1 }}>
              <Text style={styles.bulkUploadTitle}>Hatırlatıcılar</Text>
              <Text style={styles.bulkUploadSubtitle}>
                Toplantıda takip edilecek notlar; tarihi gelince günlük özette hatırlatılır
              </Text>
            </View>
            <Text style={styles.bulkUploadChevron}>›</Text>
          </TouchableOpacity>

          <View style={styles.sectionHeaderRow}>
            <Text style={styles.sectionTitle}>Kullanıcılar</Text>
            <TouchableOpacity onPress={() => setShowAddUser((v) => !v)}>
              <Text style={styles.addUserToggle}>{showAddUser ? "Kapat" : "+ Yeni Kullanıcı"}</Text>
            </TouchableOpacity>
          </View>

          {showAddUser && (
            <View style={styles.card}>
              <TextInput
                style={styles.input}
                placeholder="Ad Soyad"
                placeholderTextColor={colors.textMuted}
                value={newFullName}
                onChangeText={setNewFullName}
              />
              <TextInput
                style={styles.input}
                placeholder="E-posta"
                placeholderTextColor={colors.textMuted}
                autoCapitalize="none"
                keyboardType="email-address"
                value={newEmail}
                onChangeText={setNewEmail}
              />
              <TextInput
                style={styles.input}
                placeholder="Geçici şifre"
                placeholderTextColor={colors.textMuted}
                secureTextEntry
                value={newUserPassword}
                onChangeText={setNewUserPassword}
              />
              <View style={styles.roleRow}>
                <TouchableOpacity
                  style={[styles.roleChip, newRole === "employee" && styles.roleChipActive]}
                  onPress={() => setNewRole("employee")}
                >
                  <Text style={[styles.roleChipText, newRole === "employee" && styles.roleChipTextActive]}>Çalışan</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.roleChip, newRole === "admin" && styles.roleChipActive]}
                  onPress={() => setNewRole("admin")}
                >
                  <Text style={[styles.roleChipText, newRole === "admin" && styles.roleChipTextActive]}>Yönetici</Text>
                </TouchableOpacity>
              </View>
              <TouchableOpacity style={styles.primaryButton} onPress={handleCreateUser} disabled={isCreatingUser}>
                {isCreatingUser ? (
                  <ActivityIndicator color="#0f172a" />
                ) : (
                  <Text style={styles.primaryButtonText}>Kullanıcıyı Ekle</Text>
                )}
              </TouchableOpacity>
            </View>
          )}

          {isLoadingUsers ? (
            <ActivityIndicator color={colors.primary} style={{ marginTop: spacing(2) }} />
          ) : (
            <FlatList
              data={users}
              keyExtractor={(u) => String(u.id)}
              scrollEnabled={false}
              renderItem={({ item }) => (
                <View style={styles.userRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.userName}>{item.full_name}</Text>
                    <Text style={styles.userEmail}>{item.email}</Text>
                    <Text style={styles.userMeta}>
                      {ROLE_LABELS[item.role]} · {item.is_active ? "Aktif" : "Pasif"}
                    </Text>
                  </View>
                  {item.id !== user?.id && (
                    <TouchableOpacity
                      style={[styles.toggleButton, item.is_active ? styles.deactivateButton : styles.activateButton]}
                      onPress={() => handleToggleActive(item)}
                    >
                      <Text style={styles.toggleButtonText}>{item.is_active ? "Pasifleştir" : "Aktifleştir"}</Text>
                    </TouchableOpacity>
                  )}
                </View>
              )}
            />
          )}
        </>
      )}

      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <Text style={styles.logoutButtonText}>Çıkış Yap</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing(2),
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing(2),
  },
  name: { color: colors.text, fontSize: 18, fontWeight: "700" },
  email: { color: colors.textMuted, fontSize: 13, marginTop: 2 },
  roleBadge: {
    alignSelf: "flex-start",
    backgroundColor: colors.surfaceAlt,
    borderRadius: 8,
    paddingHorizontal: spacing(1),
    paddingVertical: spacing(0.5),
    marginTop: spacing(1),
  },
  roleBadgeText: { color: colors.primary, fontSize: 12, fontWeight: "700" },
  sectionTitle: { color: colors.text, fontSize: 15, fontWeight: "700", marginBottom: spacing(1) },
  prefRow: { flexDirection: "row", alignItems: "center" },
  prefTitle: { color: colors.text, fontSize: 14, fontWeight: "700" },
  prefSubtitle: { color: colors.textMuted, fontSize: 12, marginTop: 4, lineHeight: 17 },
  sectionHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing(1),
  },
  addUserToggle: { color: colors.primary, fontSize: 13, fontWeight: "700" },
  bulkUploadCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing(2),
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing(2),
  },
  bulkUploadTitle: { color: colors.text, fontSize: 14, fontWeight: "700" },
  bulkUploadSubtitle: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  bulkUploadChevron: { color: colors.textMuted, fontSize: 22, marginLeft: spacing(1) },
  input: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: 10,
    paddingHorizontal: spacing(2),
    paddingVertical: spacing(1.5),
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing(1.5),
  },
  primaryButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
  },
  primaryButtonText: { color: "#0f172a", fontWeight: "700" },
  roleRow: { flexDirection: "row", gap: spacing(1), marginBottom: spacing(1.5) },
  roleChip: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: 8,
    paddingVertical: spacing(1),
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  roleChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  roleChipText: { color: colors.textMuted, fontSize: 13, fontWeight: "600" },
  roleChipTextActive: { color: "#0f172a" },
  userRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: spacing(1.5),
    marginBottom: spacing(1),
    borderWidth: 1,
    borderColor: colors.border,
  },
  userName: { color: colors.text, fontWeight: "700", fontSize: 14 },
  userEmail: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  userMeta: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  toggleButton: { borderRadius: 8, paddingHorizontal: spacing(1.25), paddingVertical: spacing(0.75) },
  deactivateButton: { backgroundColor: "rgba(248, 113, 113, 0.15)" },
  activateButton: { backgroundColor: "rgba(74, 222, 128, 0.15)" },
  toggleButtonText: { color: colors.text, fontSize: 11, fontWeight: "700" },
  logoutButton: {
    backgroundColor: colors.surface,
    borderRadius: 10,
    paddingVertical: spacing(1.75),
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.danger,
    marginTop: spacing(1),
    marginBottom: spacing(4),
  },
  logoutButtonText: { color: colors.danger, fontWeight: "700" },
});
