import React from "react";
import { Text, TouchableOpacity } from "react-native";
import { colors } from "../theme";

export default function HeaderProfileButton({ navigation }: { navigation: any }) {
  return (
    <TouchableOpacity onPress={() => navigation.navigate("Profile")} style={{ marginRight: 16 }}>
      <Text style={{ fontSize: 20 }}>👤</Text>
    </TouchableOpacity>
  );
}
