/**
 * Tasarım token'ları — Figma dosyasındaki değerlerin birebir karşılığı
 * (dosya q78MYqqi5kQqfd9AcJ1nOB, "stok-takip" ve kardeş ekranlar).
 *
 * Ekranlar renk/ölçü değerlerini doğrudan yazmak yerine buradan almalı:
 * tasarım güncellendiğinde 20 ekranı tek tek elden geçirmek yerine
 * token'ları değiştirmek yetiyor.
 */

export const colors = {
  /** Ekran zemini */
  background: "#0b111e",
  /** Sabit yüzeyler: alt gezinme, segment çubuğu (opak) */
  surface: "#0f1829",
  /** Kart, arama kutusu, pasif çip - tasarımda %70 saydam #172337 */
  card: "rgba(23, 35, 55, 0.7)",
  /** İç içe girdiler için opak karşılığı; saydam yüzey üst üste binince koyulaşıyor */
  surfaceAlt: "#172337",

  /** Sabit yüzeylerin kenarlığı */
  border: "#1e293b",
  /** Kartların ince kenarlığı */
  borderSubtle: "rgba(255, 255, 255, 0.07)",

  text: "#f8fafc",
  textMuted: "#94a3b8",
  /** Ayraçlar, pasif sekme etiketi */
  textDim: "#64748b",

  primary: "#00d8f6",
  /** Birincil renkli hap/rozet zemini */
  primaryTint: "rgba(0, 216, 246, 0.11)",
  /** Birincil zemin üzerindeki yazı - camgöbeği açık olduğu için siyah */
  onPrimary: "#000000",

  success: "#10b981",
  successTint: "rgba(16, 185, 129, 0.1)",
  danger: "#ef4444",
  dangerTint: "rgba(239, 68, 68, 0.1)",
  warning: "#f59e0b",
  warningTint: "rgba(245, 158, 11, 0.1)",
};

export const spacing = (n: number) => n * 8;

/** Köşe yarıçapları */
export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  /** Çipler ve hap butonlar */
  pill: 20,
  full: 999,
};

/** Tipografi ölçeği */
export const typography = {
  screenTitle: { fontSize: 22, fontWeight: "700" as const },
  cardTitle: { fontSize: 15, fontWeight: "600" as const },
  body: { fontSize: 13, fontWeight: "400" as const },
  bodyStrong: { fontSize: 13, fontWeight: "600" as const },
  meta: { fontSize: 11, fontWeight: "500" as const },
  badge: { fontSize: 11, fontWeight: "700" as const },
  tabLabel: { fontSize: 10, fontWeight: "600" as const },
};

/** Tasarımdaki tek gölge seviyesi (FAB). iOS/Android/web farklı yorumladığı
 *  için tek seviyeyle sınırlı tutuluyor. */
export const shadow = {
  floating: {
    shadowColor: "#000",
    shadowOpacity: 0.25,
    shadowRadius: 5,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
};

/** Ekran kenar boşluğu ve liste aralığı - tasarımda 16/12 px */
export const layout = {
  screenPadding: 16,
  cardGap: 12,
  cardPadding: 16,
  /** Masaüstü tarayıcıda içerik ortalanmış bir sütunda dursun */
  maxContentWidth: 720,
};
