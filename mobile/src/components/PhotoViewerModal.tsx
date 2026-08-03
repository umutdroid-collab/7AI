import React from "react";
import {
  ActivityIndicator,
  Image,
  Modal,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { colors, spacing } from "../theme";

/**
 * Check-in fotoğrafını tam ekran gösterir. Listede fotoğraf 64 pikselde
 * duruyor ve orada ne olduğu seçilemiyordu; kartta küçük önizleme, burada
 * tam boy dosya kullanılır.
 */
export default function PhotoViewerModal({
  visible,
  uri,
  nativeHeaders,
  title,
  subtitle,
  onClose,
}: {
  visible: boolean;
  uri: string | null;
  /** Native'de fotoğraf ucu yetkilendirme ister; web'de blob URL kullanıldığı
   *  için gerekmez. */
  nativeHeaders?: Record<string, string>;
  title?: string;
  subtitle?: string;
  onClose: () => void;
}) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      {/* Fotoğrafın dışına dokununca kapansın - tam ekranda kapatma düğmesini
          aramak zorunda kalmamak için. */}
      <TouchableOpacity style={styles.backdrop} activeOpacity={1} onPress={onClose}>
        <View style={styles.header}>
          <View style={styles.headerText}>
            {title && <Text style={styles.title}>{title}</Text>}
            {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
          </View>
          <TouchableOpacity style={styles.closeButton} onPress={onClose}>
            <Text style={styles.closeButtonText}>✕</Text>
          </TouchableOpacity>
        </View>

        {uri ? (
          <Image source={{ uri, headers: nativeHeaders }} style={styles.photo} resizeMode="contain" />
        ) : (
          <ActivityIndicator color={colors.primary} />
        )}
      </TouchableOpacity>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(2, 6, 23, 0.95)",
    justifyContent: "center",
    paddingHorizontal: spacing(1),
  },
  header: {
    position: "absolute",
    top: Platform.OS === "web" ? spacing(2) : spacing(6),
    left: spacing(2),
    right: spacing(2),
    flexDirection: "row",
    alignItems: "flex-start",
  },
  headerText: { flex: 1 },
  title: { color: colors.text, fontWeight: "700", fontSize: 15 },
  subtitle: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  closeButton: {
    paddingHorizontal: spacing(1.5),
    paddingVertical: spacing(0.5),
    borderRadius: 999,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  closeButtonText: { color: colors.text, fontSize: 16, fontWeight: "700" },
  photo: { width: "100%", height: "80%" },
});
