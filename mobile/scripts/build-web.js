/**
 * Web derlemesi. expo export'u doğrudan çağırmak yerine bu sarmalayıcıdan
 * geçiyoruz ki derlenen sürüm bundle'ın içine gömülsün.
 *
 * Neden gerekli: "değişikliğim yayında mı" sorusuna bakarak cevap verecek
 * bir yer yoktu ve bu oturumda üç kez, her seferinde uzun uzun, tarayıcı
 * önbelleği mi yoksa deploy mu diye uğraşıldı. Profil ekranındaki sürüm
 * satırı bunu tek bakışa indiriyor.
 *
 * EXPO_PUBLIC_ önekli değişkenler Expo tarafından derleme anında koda
 * gömülüyor; çalışma anında okunacak bir şey yok.
 */

const { execFileSync, execSync } = require("child_process");

function commitHash() {
  // Cloudflare Pages derlemeyi kendi klonunda yapıyor ve commit'i ortam
  // değişkeninde veriyor; yerelde git'ten okunur.
  if (process.env.CF_PAGES_COMMIT_SHA) {
    return process.env.CF_PAGES_COMMIT_SHA.slice(0, 7);
  }
  try {
    return execSync("git rev-parse --short HEAD", { encoding: "utf8" }).trim();
  } catch {
    return "bilinmiyor";
  }
}

const env = {
  ...process.env,
  EXPO_PUBLIC_BUILD_COMMIT: commitHash(),
  EXPO_PUBLIC_BUILD_DATE: new Date().toISOString().slice(0, 10),
};

console.log(`Derlenen sürüm: ${env.EXPO_PUBLIC_BUILD_COMMIT} (${env.EXPO_PUBLIC_BUILD_DATE})`);

execFileSync("npx", ["expo", "export", "-p", "web", "--output-dir", "dist"], { stdio: "inherit", env });
execFileSync("node", ["scripts/postexport-web.js"], { stdio: "inherit", env });
