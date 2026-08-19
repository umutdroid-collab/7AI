/**
 * Derlenen sürümün kimliği. `scripts/build-web.js` bu değerleri derleme
 * anında EXPO_PUBLIC_ değişkenleriyle koda gömüyor.
 *
 * Amaç teşhis: "değişiklik yayında mı yoksa tarayıcı eski sürümü mü
 * sunuyor" sorusunu tek bakışta cevaplamak. Bu ayrım olmadan her seferinde
 * deploy günlükleriyle tarayıcı önbelleği arasında gidip gelmek gerekiyordu.
 */

/** Kısa commit hash'i; derleme sarmalayıcısından geçmeyen ortamlarda "dev". */
export const BUILD_COMMIT = process.env.EXPO_PUBLIC_BUILD_COMMIT || "dev";

export const BUILD_DATE = process.env.EXPO_PUBLIC_BUILD_DATE || "";

/** Profil ekranında gösterilen tek satır. */
export function buildLabel(): string {
  return BUILD_DATE ? `Sürüm ${BUILD_COMMIT} · ${BUILD_DATE}` : `Sürüm ${BUILD_COMMIT}`;
}
