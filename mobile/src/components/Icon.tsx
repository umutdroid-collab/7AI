import React from "react";
import Feather from "@expo/vector-icons/Feather";
import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { colors } from "../theme";

/**
 * Tasarımdaki ikonlar Lucide setinden. Lucide, Feather'ın türevi olduğu için
 * glifler neredeyse birebir örtüşüyor ve Feather Expo ile hazır geliyor —
 * `lucide-react-native` ise `react-native-svg` bağımlılığı isterdi.
 *
 * Feather'da karşılığı olmayan iki glif MaterialCommunityIcons'tan alınıyor.
 * Eşleme burada tek yerde durduğu için çağrı yerleri hangi setten geldiğini
 * bilmek zorunda değil.
 */
type FeatherName = React.ComponentProps<typeof Feather>["name"];
type MaterialName = React.ComponentProps<typeof MaterialCommunityIcons>["name"];

const FEATHER: Record<string, FeatherName> = {
  stock: "box", // Lucide "cuboid"
  invoice: "file-text",
  assistant: "message-square",
  location: "map-pin",
  targets: "trending-up",
  search: "search",
  chevronDown: "chevron-down",
  chevronRight: "chevron-right",
  settings: "settings",
  file: "file",
  upload: "upload",
  folder: "folder",
  bell: "bell",
  send: "send",
  camera: "camera",
  trash: "trash-2",
  plus: "plus",
  target: "target",
  check: "check",
  close: "x",
  edit: "edit-2",
  download: "download",
  mic: "mic",
  logOut: "log-out",
  alert: "alert-circle",
  refresh: "refresh-cw",
  user: "user",
  calendar: "calendar",
};

const MATERIAL: Record<string, MaterialName> = {
  hospital: "hospital-building", // Lucide "building"
  sparkles: "auto-fix", // Lucide "sparkles" - asistan rozetinde
};

export type IconName = keyof typeof FEATHER | keyof typeof MATERIAL;

export default function Icon({
  name,
  size = 20,
  color = colors.textMuted,
}: {
  name: IconName;
  size?: number;
  color?: string;
}) {
  const material = MATERIAL[name as keyof typeof MATERIAL];
  if (material) {
    return <MaterialCommunityIcons name={material} size={size} color={color} />;
  }
  return <Feather name={FEATHER[name as keyof typeof FEATHER]} size={size} color={color} />;
}
