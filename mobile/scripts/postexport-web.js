// expo export -p web ürettiği statik siteye PWA dosyalarını (manifest,
// Apple "Add to Home Screen" meta etiketleri, ikonlar) ekler. Expo'nun
// Metro tabanlı web derleyicisi bunları kendiliğinden üretmiyor.
const fs = require("fs");
const path = require("path");

const OUT_DIR = path.join(__dirname, "..", "dist");
const ASSETS_DIR = path.join(__dirname, "..", "assets", "pwa");

const manifest = {
  name: "7AI Saha Uygulaması",
  short_name: "7AI",
  start_url: "/",
  display: "standalone",
  background_color: "#0f172a",
  theme_color: "#0f172a",
  icons: [
    { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
    { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
  ],
};

fs.writeFileSync(path.join(OUT_DIR, "manifest.json"), JSON.stringify(manifest, null, 2));

for (const file of ["icon-192.png", "icon-512.png", "apple-touch-icon.png"]) {
  fs.copyFileSync(path.join(ASSETS_DIR, file), path.join(OUT_DIR, file));
}

// SPA yönlendirmesi çıktı klasörünün İÇİNE yazılır. Aynı kural netlify.toml'da
// da duruyor ama orası yalnızca Netlify'ın kendi derlemesinde okunur; hazır
// dist klasörü elle yüklendiğinde (kredi harcamamak için yaptığımız yöntem)
// devreye girmez ve alt adreslerin yenilenmesi 404 döner. _redirects dosyası
// yayın klasöründen okunduğu için her iki yolda da geçerli olur.
fs.writeFileSync(path.join(OUT_DIR, "_redirects"), "/*    /index.html   200\n");

// Önbellek ve güvenlik başlıkları. _headers dosyası hem Netlify hem Cloudflare
// Pages tarafından okunuyor; netlify.toml gibi tek platforma bağlı değil.
//
// _expo/static ve assets altındaki dosya adları içerik özetini taşıyor (içerik
// değişince ad da değişir), bu yüzden uzun süreli önbellek güvenli - saha ekibi
// mobil veride çalıştığı için bu her açılışta yeniden indirmeyi engelliyor.
// index.html bilerek dışarıda: her zaman taze gelmeli, yoksa yeni yayın
// kullanıcıya ulaşmaz.
fs.writeFileSync(
  path.join(OUT_DIR, "_headers"),
  [
    "/_expo/static/*",
    "  Cache-Control: public, max-age=31536000, immutable",
    "",
    "/assets/*",
    "  Cache-Control: public, max-age=31536000, immutable",
    "",
    "/*",
    "  X-Content-Type-Options: nosniff",
    "  Referrer-Policy: strict-origin-when-cross-origin",
    "  X-Frame-Options: SAMEORIGIN",
    "",
  ].join("\n")
);

const indexPath = path.join(OUT_DIR, "index.html");
let html = fs.readFileSync(indexPath, "utf8");

// viewport-fit=cover olmadan iOS, standalone (Ana Ekrana Ekle) modunda
// safe-area-inset-* CSS değerlerini hiç raporlamaz; bu da React Navigation'ın
// alt sekme çubuğunu güvenli alanı hesaba katmadan (dolayısıyla küçük/yanlış
// boyutlu) çizmesine yol açar.
html = html.replace(
  '<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />',
  '<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no, viewport-fit=cover" />'
);

const extraHead = `
<link rel="manifest" href="/manifest.json" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<meta name="apple-mobile-web-app-title" content="7AI" />
<meta name="mobile-web-app-capable" content="yes" />
</head>`;

html = html.replace("</head>", extraHead);
fs.writeFileSync(indexPath, html);

console.log("PWA dosyaları eklendi:", OUT_DIR);

// --- İkon fontlarını temiz bir yola taşı ---
//
// @expo/vector-icons TTF'leri çıktıya "assets/node_modules/@expo/vector-icons/
// .../Fonts/Feather.<hash>.ttf" gibi bir yola koyuyor. Yol içinde node_modules
// geçtiği için bazı barındırma platformları bu dosyaları yayına hiç almıyor;
// font 404 olunca tarayıcı ikonların yerine boş kutu (tofu) çiziyor.
//
// Çözüm: fontları /fonts altına kopyalayıp @font-face'i doğrudan index.html'e
// yazmak. İkon bileşenleri zaten fontFamily: "Feather" ile çiziyor, CSS'ten
// tanımlanan yüz onları karşılıyor - expo-font'un ürettiği varlık yoluna hiç
// ihtiyaç kalmıyor ve sonuç her platformda aynı.
function collectIconFonts(dir, found = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) collectIconFonts(full, found);
    else if (entry.name.endsWith(".ttf")) found.push(full);
  }
  return found;
}

const assetsDir = path.join(OUT_DIR, "assets");
if (fs.existsSync(assetsDir)) {
  const fontsOut = path.join(OUT_DIR, "fonts");
  fs.mkdirSync(fontsOut, { recursive: true });

  const faces = [];
  for (const source of collectIconFonts(assetsDir)) {
    // "Feather.ca4b48e0....ttf" -> "Feather"
    const family = path.basename(source).split(".")[0];
    fs.copyFileSync(source, path.join(fontsOut, `${family}.ttf`));
    faces.push(
      `@font-face{font-family:"${family}";src:url("/fonts/${family}.ttf") format("truetype");font-display:block}`
    );
  }

  if (faces.length) {
    const withFonts = fs
      .readFileSync(indexPath, "utf8")
      .replace("</head>", `<style>${faces.join("")}</style>\n</head>`);
    fs.writeFileSync(indexPath, withFonts);
    console.log(`İkon fontları /fonts altına alındı: ${faces.length} aile`);
  }
}
