import { Platform } from "react-native";

/**
 * Tarayıcının kendi konuşma tanıma motoru (Web Speech API) üzerinden sesi
 * yazıya çevirir.
 *
 * Neden bu yol: ücretsiz, ek bağımlılık yok, sunucuya ses göndermiyoruz.
 * Native uygulamada kullanılmaz - orada klavyenin kendi mikrofon tuşu zaten
 * aynı işi görüyor ve ek bir kütüphane native derleme gerektirirdi.
 *
 * Sınırlar: Chrome/Edge (Android + masaüstü) ve Safari 14.5+ destekler,
 * Firefox desteklemez. Chrome tanımayı kendi sunucusunda yaptığı için
 * internet gerekir. Desteklenmeyen yerlerde isSupported() false döner ve
 * arayüzde mikrofon tuşu hiç gösterilmez.
 */

type RecognitionHandle = { stop: () => void };

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
}

function getConstructor(): (new () => SpeechRecognitionLike) | null {
  if (Platform.OS !== "web" || typeof window === "undefined") return null;
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function isSupported(): boolean {
  return getConstructor() !== null;
}

export interface SpeechCallbacks {
  /** Tanınan metin; konuşma sürerken birden çok kez çağrılabilir. */
  onText: (text: string, isFinal: boolean) => void;
  onError: (message: string) => void;
  onEnd: () => void;
}

export function startListening({ onText, onError, onEnd }: SpeechCallbacks): RecognitionHandle | null {
  const Recognition = getConstructor();
  if (!Recognition) return null;

  const recognition = new Recognition();
  recognition.lang = "tr-TR";
  // continuous=false: kullanıcı susunca kendiliğinden biter. Sürekli dinlemek
  // sahada telefonu cebe koyup unutmaya ve boşuna pil harcamaya yol açıyor.
  recognition.continuous = false;
  recognition.interimResults = true;

  recognition.onresult = (event: any) => {
    let text = "";
    let isFinal = false;
    for (let i = event.resultIndex; i < event.results.length; i++) {
      text += event.results[i][0].transcript;
      if (event.results[i].isFinal) isFinal = true;
    }
    onText(text, isFinal);
  };

  recognition.onerror = (event: any) => {
    const messages: Record<string, string> = {
      "not-allowed": "Mikrofon izni verilmedi. Tarayıcı ayarlarından izin vermeniz gerekiyor.",
      "service-not-allowed": "Mikrofon izni verilmedi.",
      "no-speech": "Ses algılanamadı, tekrar deneyin.",
      network: "Konuşma tanıma için internet bağlantısı gerekiyor.",
    };
    onError(messages[event.error] ?? "Ses yazıya çevrilemedi, tekrar deneyin.");
  };

  recognition.onend = onEnd;

  try {
    recognition.start();
  } catch {
    onError("Ses kaydı başlatılamadı.");
    return null;
  }

  return { stop: () => recognition.stop() };
}
