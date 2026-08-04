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
