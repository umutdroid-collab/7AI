# Kurulum ve Felaket Kurtarma

Bu belge iki soruyu cevaplar: sistemi **sıfırdan nasıl kurarsınız** ve her şey
kaybolursa **nasıl geri getirirsiniz**. İkisi aynı adımlar olduğu için tek
belgede tutuluyor — ayrı tutulsa biri güncellenip diğeri eskirdi.

> Bu belgeyi kod değiştiğinde güncelleyin. Eskimiş bir kurtarma rehberi,
> olmayan bir rehberden daha tehlikelidir: kurtarma anında fark edilir.

---

## 1. Neyin nerede durduğu

| Parça | Nerede | Kaybolursa |
|---|---|---|
| **Kod** (backend + mobil) | GitHub: `umutdroid-collab/7AI`, dal `claude/mobile-app-inventory-invoice-qa-yzmx0q` | Klonlanmış her kopyada tüm geçmiş var (git dağıtık) |
| **Veri** (DB + yüklenen dosyalar) | Railway Volume `/app/data` + haftalık .zip + S3/R2 kopyası | Bkz. bölüm 4 |
| **Sırlar** (API anahtarları, şifreler) | **Yalnızca Railway → Variables** | Yeniden üretilmeli — bkz. bölüm 3 |
| **Platform ayarları** | Railway / Cloudflare / R2 panellerinde | Bu belgeden yeniden kurulur — bkz. bölüm 2 |
| **Alan adları ve DNS** | Cloudflare DNS (`7medikal.com`) | Kayıt firmasındaki hesap |

**Sırlar hiçbir yerde yedeklenmiyor** — bilinçli bir tercih (koda girmemeleri
için), ama bedeli şu: Railway projesi silinirse değerler gider. Hepsi yeniden
üretilebilir; hangisinin nereden alınacağı bölüm 3'te.

Yedek .zip'i **kodu içermez**. Kodun yedeği git'tir; ikisini karıştırmayın.

---

## 2. Sıfırdan kurulum

### 2.1 Backend — Railway

1. [railway.app](https://railway.app) → GitHub ile giriş.
2. **New Project** → **Deploy from GitHub repo** → `umutdroid-collab/7AI`.
3. Servis → **Settings** → **Source** → **Root Directory**: `backend`
   (depoda `mobile/` de var; Railway yalnızca backend'i build etmeli).
   `backend/Dockerfile` otomatik algılanır.
4. **Settings** → **Volumes** → **Add Volume**, mount path **`/app/data`**.
   Bu adım atlanırsa her yeniden başlatmada veritabanı ve yüklenen dosyalar
   silinir.
5. **Variables** sekmesine bölüm 3'teki değişkenleri girin.
6. **Settings** → **Networking** → **Generate Domain**.
   `https://<ad>.up.railway.app/docs` açılıyorsa backend ayakta.

> Operatörler paylaşımlı alan adlarını (`*.railway.app`) filtreleyebiliyor.
> Kalıcı kurulumda kendi alt alan adınızı (`api.7medikal.com`) bağlayın.

### 2.2 Web/PWA — Cloudflare Pages

1. Cloudflare → **Workers & Pages** → **Create** → **Pages** →
   **Connect to Git** (Workers akışına girmeyin; orada "Deploy command:
   npx wrangler deploy" yazar, yanlış yoldasınız demektir).
2. Depo: `umutdroid-collab/7AI`, dal: geliştirme dalı.
3. Build ayarları:
   - Root directory: `mobile`
   - Build command: `npm run build:web`
   - Output directory: `dist`
   - Watch path: `mobile/*`
4. **Custom domains** → `saha.7medikal.com`.

Yönlendirme (SPA catch-all) ve önbellek başlıkları `netlify.toml`'dan değil,
her derlemede `mobile/scripts/postexport-web.js` tarafından üretilen
`dist/_redirects` ve `dist/_headers` dosyalarından gelir; ikisini de hem
Netlify hem Cloudflare Pages okur. Node sürümü `mobile/.nvmrc` ile sabit.

> `*.pages.dev` adresi Türkiye'deki bazı ağlardan `ERR_CONNECTION_TIMED_OUT`
> veriyor. Yayını oradan test etmeye çalışmayın; kendi alan adınızda geçici
> bir alt alan adı açın. Deploy bozuk olsaydı Cloudflare'in 404 sayfası
> gelirdi — bağlantı hiç kurulamıyorsa sebep ağ filtresidir.

### 2.3 Mobil uygulamanın backend adresi

`mobile/app.json` → `expo.extra.apiBaseUrl`. Şu an
`https://7ai-production.up.railway.app`. Backend adresi değişirse burayı
güncelleyip yeniden derleyin.

### 2.4 Dış yedek deposu — Cloudflare R2

1. Cloudflare → **R2** → **Create bucket** (örn. `7ai-yedekler`).
2. R2 ana sayfasındaki **hesap ID**'sini not edin (endpoint için).
3. **Manage API tokens** → **Create API token** → izin **Object Read & Write**,
   yalnızca bu bucket'a kapsamlı. Secret bir daha gösterilmez.
4. Bölüm 3'teki `BACKUP_S3_*` değişkenlerini girin.
5. Doğrulama: `GET /backups/offsite/status` → `erisim: true`.

### 2.5 E-posta — Resend

Railway'in Hobby planı giden SMTP portlarını (25/465/587/2525) tamamen
engelliyor; e-posta bu yüzden SMTP ile değil Resend'in HTTPS API'siyle
gidiyor. Resend'de gönderen alan adı (`7medikal.com` alt alan adı)
doğrulanmış olmalı. Doğrulama: `POST /notifications/email-test`.

---

## 3. Ortam değişkenleri

Railway → servis → **Variables**. Tam liste ve açıklamalar için
`backend/.env.example`.

### Zorunlu

| Değişken | Değer / nereden alınır |
|---|---|
| `DATABASE_URL` | `sqlite:////app/data/app.db` (dört eğik çizgi — mutlak yol) |
| `SECRET_KEY` | Uzun rastgele bir metin. Üretmek için: `openssl rand -hex 32`. Değiştirilirse tüm oturumlar düşer (zararsız). |
| `SEED_ADMIN_EMAIL` | Yönetici e-postanız |
| `SEED_ADMIN_PASSWORD` | Güçlü bir şifre. **Girilmezse** uygulama depodaki varsayılanla yönetici açar. |
| `INVOICE_FOLDER` | `/app/data/invoices` |
| `CLINICAL_DOCS_FOLDER` | `/app/data/clinical_docs` |
| `VECTOR_DB_DIR` | `/app/data/vectorstore` |
| `CHECKIN_PHOTOS_FOLDER` | `/app/data/checkins` |
| `BACKUP_DIR` | `/app/data/backups` |
| `CORS_ORIGINS` | `https://saha.7medikal.com` (virgülle birden fazla) |

### Klinik asistan

| Değişken | Nereden |
|---|---|
| `QWEN_BASE_URL` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `QWEN_API_KEY` | Alibaba Model Studio konsolundan yeni anahtar |
| `QWEN_MODEL` | `qwen-plus` |
| `QWEN_MAX_TOKENS` | `1200` (600'de Türkçe cevaplar cümle ortasında kesildi) |
| `QWEN_TIMEOUT_SECONDS` | `60` |
| `PUBMED_EMAIL` | Kendi e-postanız (NCBI kuralı) |

### Entegrasyonlar

| Değişken | Nereden |
|---|---|
| `EVOBULUT_USERNAME` / `EVOBULUT_PASSWORD` | EvoBulut hesabınız |
| `RESEND_API_KEY` | resend.com → API Keys → yeni anahtar |
| `SMTP_FROM` | Resend'de doğrulanmış alan adınızdaki gönderen adresi |
| `BACKUP_S3_ENDPOINT` | `https://<hesap-id>.r2.cloudflarestorage.com` |
| `BACKUP_S3_BUCKET` | R2 bucket adı |
| `BACKUP_S3_ACCESS_KEY` / `BACKUP_S3_SECRET_KEY` | R2 API token'ı |

Eski `SMTP_HOST` / `SMTP_USERNAME` / `SMTP_PASSWORD` tanımlıysa silin: Resend
anahtarı varken kullanılmıyorlar, ama anahtar bir gün kaldırılırsa sistem
sessizce Railway'de çalışmayan SMTP yoluna düşer.

---

## 4. Felaket kurtarma

### Senaryo A — Railway servisi/diski gitti, R2 duruyor

1. Bölüm 2.1'i uygulayıp yeni bir servis kurun, bölüm 3'teki değişkenleri
   girin (özellikle `BACKUP_S3_*`).
2. `GET /backups/offsite` → dış depodaki kopyaları listeler, en yenisi başta.
3. `POST /backups/offsite/{dosya}/pull` → o kopyayı yerel klasöre indirir.
4. `POST /backups/{dosya}/restore?confirm=true` → veritabanı ve tüm yüklenen
   dosyalar geri gelir. Geri yükleme, üzerine yazmadan **önce** mevcut
   durumun bir güvenlik yedeğini alır.

### Senaryo B — Elinizde yalnızca indirilmiş bir .zip var

1. Yeni servisi kurun.
2. `POST /backups/upload` ile zip'i yükleyin (geçerli bir arşiv değilse
   reddedilir).
3. `POST /backups/{dosya}/restore?confirm=true`.

### Senaryo C — Yalnızca kod lazım

`git clone https://github.com/umutdroid-collab/7AI` — tüm geçmiş gelir.
Yerel bir klon zaten varsa deponun kendisi silinse bile o klon tam bir
yedektir; `git push` ile yeni bir uzak depoya aktarılabilir.

### Geri yükleme sonrası kontrol listesi

- [ ] Giriş yapılabiliyor mu (`SEED_ADMIN_*` yeni kurulumda yeni yönetici
      açar; **eski kullanıcılar yedekten gelir**, eski şifreleriyle)
- [ ] Beş sekme de veri getiriyor mu
- [ ] Klinik asistan cevap veriyor mu — vermezse vektör indeksi bozulmuştur,
      geri yükleme onu diskte değiştirir; servisi bir kez yeniden başlatın
- [ ] `GET /invoices/evobulut-diagnostics` → `ok: true`
- [ ] `POST /notifications/email-test` → mail geliyor mu
- [ ] `GET /backups/offsite/status` → `erisim: true`
- [ ] `GET /backups/size-report` → veri boyutları beklendiği gibi mi

---

## 5. Yedekleme nasıl çalışıyor

- Her **pazar 03:00** (Europe/Istanbul) bir .zip üretilir: veritabanı +
  fatura PDF'leri + klinik çalışmalar + check-in fotoğrafları + vektör
  indeksi. Ayrıca açılışta diskteki en yeni yedeğe bakılır, 7 günden eskiyse
  iki dakika sonrasına tek seferlik telafi işi konur.
- Yerelde son `BACKUP_KEEP_COUNT` (8), dış depoda son `BACKUP_S3_KEEP_COUNT`
  (12) kopya tutulur.
- Veritabanı dosya kopyalanarak değil SQLite'ın kendi backup API'siyle
  alınır — yazma anına denk gelen bozuk yedeği önlemek için.
- Dış depoya yükleme **başarısız olursa hata yükseltilmez**; yerel yedek
  yine geçerlidir. Gerçek hatayı görmek için `GET /backups/offsite/status`.

Elle çalıştırma: `POST /backups/run`. Liste: `GET /backups`.

---

## 6. Sonradan güncelleme

Geliştirme dalına push edildiğinde Railway (backend'de değişiklik varsa) ve
Cloudflare Pages (mobile'da değişiklik varsa) otomatik yeniden deploy eder.
Volume'daki veriler korunur. Migrasyon aracı yok; `services/migrations.py`
her açılışta model ile şema farkını kapatır.
