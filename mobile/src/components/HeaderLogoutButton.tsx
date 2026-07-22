import React from "react";
import { Alert, Text, TouchableOpacity } from "react-native";
import { useAuth } from "../context/AuthContext";
import { colors } from "../theme";

export default function HeaderLogoutButton() {
  const { logout, user } = useAuth();

  function confirmLogout() {
    Alert.alert("Çıkış yap", `${user?.full_name} olarak çıkış yapmak istiyor musunuz?`, [
      { text: "Vazgeç", style: "cancel" },
      { text: "Çıkış yap", style: "destructive", onPress: logout },
    ]);
  }

  return (
    <TouchableOpacity onPress={confirmLogout} style={{ marginRight: 16 }}>
      <Text style={{ color: colors.primary, fontWeight: "600" }}>Çıkış</Text>
    </TouchableOpacity>
  );
}
