import { Platform } from "react-native";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import Alert from "./alert";
import { api, API_BASE_URL, TOKEN_KEY } from "../api/client";
import secureStorage from "./secureStorage";

/**
 * Korumalı bir API dosyasını indirir. Web'de blob alınıp tarayıcının indirme
 * mekanizması tetiklenir; native'de dosya önbelleğe indirilip paylaşım
 * menüsü açılır (kullanıcı WhatsApp/e-posta/Dosyalar'a kaydedebilsin diye).
 */
export async function downloadFile(apiPath: string, filename: string): Promise<void> {
  if (Platform.OS === "web") {
    const response = await api.get(apiPath, { responseType: "blob" });
    const blobUrl = URL.createObjectURL(response.data as Blob);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(blobUrl);
    return;
  }

  const token = await secureStorage.getItemAsync(TOKEN_KEY);
  const localUri = `${FileSystem.cacheDirectory}${filename}`;
  const result = await FileSystem.downloadAsync(`${API_BASE_URL}${apiPath}`, localUri, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(result.uri);
  } else {
    Alert.alert("İndirildi", `Dosya kaydedildi: ${result.uri}`);
  }
}

export function dateStampedFilename(prefix: string, extension: string): string {
  return `${prefix}-${new Date().toISOString().slice(0, 10)}.${extension}`;
}
