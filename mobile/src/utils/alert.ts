import { Alert as RNAlert, Platform } from "react-native";

interface AlertButton {
  text: string;
  onPress?: () => void;
  style?: "default" | "cancel" | "destructive";
}

/**
 * react-native-web'in Alert.alert() implementasyonu no-op'tur (static alert() {}),
 * yani web derlemesinde hiçbir onay/başarı diyaloğu gösterilmez ve buton
 * callback'leri hiç çalışmaz. Bu, aynı `Alert.alert(...)` çağrı imzasını koruyan
 * ama web'de window.alert/confirm'e düşen bir yerine geçer.
 */
function alertImpl(title: string, message?: string, buttons?: AlertButton[]) {
  if (Platform.OS !== "web") {
    RNAlert.alert(title, message, buttons as any);
    return;
  }

  const list = buttons && buttons.length > 0 ? buttons : [{ text: "Tamam" } as AlertButton];
  const text = [title, message].filter(Boolean).join("\n\n");

  if (list.length === 1) {
    window.alert(text);
    list[0].onPress?.();
    return;
  }

  const cancelButton = list.find((b) => b.style === "cancel");
  const confirmButton = list.find((b) => b !== cancelButton) ?? list[list.length - 1];

  if (window.confirm(text)) {
    confirmButton?.onPress?.();
  } else {
    cancelButton?.onPress?.();
  }
}

export default { alert: alertImpl };
