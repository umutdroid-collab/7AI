import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import { colors, spacing } from "../theme";

/**
 * Web'de expo-image-picker'ın "kameradan çek" seçeneği aslında bir dosya
 * seçici (<input type=file capture>) - tarayıcıya göre kullanıcı yine de
 * galeriden eski bir fotoğraf seçebiliyor. Bu, check-in fotoğrafının o an
 * çekildiğini garanti etme amacını baltalıyor. Bunun yerine burada gerçek
 * kamera akışından (getUserMedia) doğrudan kare yakalayan bir bileşen
 * kullanıyoruz - galeriye hiç erişim yok.
 */
export default function WebCameraModal({
  visible,
  onClose,
  onCapture,
}: {
  visible: boolean;
  onClose: () => void;
  onCapture: (photo: { uri: string; blob: Blob }) => void;
}) {
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const [isReady, setIsReady] = useState(false);
  const [isCapturing, setIsCapturing] = useState(false);

  useEffect(() => {
    if (visible && !permission?.granted) {
      requestPermission();
    }
    if (!visible) {
      setIsReady(false);
    }
  }, [visible]);

  async function handleCapture() {
    if (!cameraRef.current || !isReady) return;
    setIsCapturing(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.5 });
      if (!photo?.uri) return;
      const response = await fetch(photo.uri);
      const blob = await response.blob();
      onCapture({ uri: photo.uri, blob });
    } finally {
      setIsCapturing(false);
    }
  }

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <View style={styles.container}>
        {permission?.granted ? (
          <CameraView
            ref={cameraRef}
            style={styles.camera}
            facing="back"
            onCameraReady={() => setIsReady(true)}
          />
        ) : (
          <View style={styles.permissionBox}>
            <Text style={styles.permissionText}>
              Check-in fotoğrafı için kamera izni gerekiyor.
            </Text>
            <TouchableOpacity style={styles.permissionButton} onPress={requestPermission}>
              <Text style={styles.permissionButtonText}>İzin Ver</Text>
            </TouchableOpacity>
          </View>
        )}

        <View style={styles.controls}>
          <TouchableOpacity style={styles.cancelButton} onPress={onClose}>
            <Text style={styles.cancelButtonText}>Vazgeç</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.captureButton}
            onPress={handleCapture}
            disabled={!isReady || isCapturing}
          >
            {isCapturing ? <ActivityIndicator color="#0f172a" /> : <View style={styles.captureButtonInner} />}
          </TouchableOpacity>
          <View style={styles.spacer} />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  camera: { flex: 1 },
  permissionBox: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing(3) },
  permissionText: { color: colors.text, fontSize: 15, textAlign: "center", marginBottom: spacing(2) },
  permissionButton: {
    backgroundColor: colors.primary,
    borderRadius: 10,
    paddingHorizontal: spacing(3),
    paddingVertical: spacing(1.5),
  },
  permissionButtonText: { color: "#0f172a", fontWeight: "700" },
  controls: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing(3),
    paddingVertical: spacing(3),
    backgroundColor: "#000",
  },
  cancelButton: { width: 80 },
  cancelButtonText: { color: colors.text, fontSize: 15 },
  spacer: { width: 80 },
  captureButton: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "#fff",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 4,
    borderColor: colors.border,
  },
  captureButtonInner: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
  },
});
