# 7AI Saha Uygulaması — proje notları

Bu dosya her yeni Claude Code oturumunda otomatik okunur. Amacı: sohbet
geçmişi kaybolduğunda da projenin **nasıl** çalıştığını ve daha önemlisi bazı
kararların **neden** böyle alındığını korumak. Aşağıdaki "neden" notlarının
çoğu canlıda yaşanmış sorunların sonucudur; bilinmeden değiştirilirse aynı
hatalar tekrarlanır.

## Ne yapıyor

Konsinye tıbbi cihaz satan bir firmanın saha ekibi için iç uygulama. Beş sekme:

- **Stok Takip** — hangi ürün (lot/seri/SKT) hangi hastanede ya da kimin
  aracında; hastaneler arası taşıma, "kullanıldı" işaretleme.
- **Fatura Takip** — faturalar EvoBulut'tan otomatik çekilir; vade takibi.
- **Klinik Asistan** — yüklenen klinik çalışmalar + PubMed üzerinden,
  kaynak göstererek yanıt veren RAG asistanı (Qwen).
- **Rapor** — çalışanların günlük check-in'i (fotoğraf + konum).
- **Hedefler** — ürüne bağlı ya da serbest satış/aktivite hedefleri.

Tüm kullanıcı arayüzü metinleri **Türkçe**. Kod ve commit mesajları İngilizce,
kod içi açıklamalar Türkçe.

## Yapı

```
backend/    FastAPI + SQLAlchemy + SQLite   → Railway'de barındırılıyor
mobile/     Expo (React Native) — hem native hem web (PWA) → Netlify
```

- Backend: `https://7ai-production.up.railway.app`
- Web/PWA: `https://saha.7medikal.com` (Netlify; `7medai.netlify.app` da çalışır)
- Depo: `umutdroid-collab/7AI`, geliştirme dalı
  `claude/mobile-app-inventory-invoice-qa-yzmx0q`

## Çalıştırma / test

```bash
cd backend && source .venv/bin/activate && python -m pytest -q   # 64 test
cd mobile  && npx tsc --noEmit -p . && npm run build:web
```

Değişiklik yapınca **her ikisini de** çalıştır. Test paketi bilinçli olarak
gerçek akışları kapsıyor (gerçek PDF'ler, gerçek embedding, gerçek yedek geri
yükleme); bir test düşerse önce gerçekten bir şey mi bozuldu diye bak.

## Bilinmesi gereken kararlar ve tuzaklar

**Migrasyon aracı yok.** Alembic kullanılmıyor; `services/migrations.py`
her açılışta model ile şema farkını kapatır: eksik sütunları ekler
(`server_default` varsa DEFAULT'u da yazar — yoksa mevcut satırlar NULL kalır
ve boolean bayraklar sessizce "kapalı" davranır) ve SQLite'ta artık zorunlu
olmaması gereken sütunlar için tabloyu yeniden kurar (SQLite ALTER COLUMN
desteklemiyor). Model değiştirdiğinde bu dosyanın senaryoyu kapsadığını
doğrula.

**Railway Hobby planı SMTP portlarını (25/465/587/2525) tamamen engelliyor.**
E-posta bu yüzden SMTP ile değil, Resend'in HTTPS API'siyle gönderiliyor
(`services/email.py`). SMTP yolu yedek olarak duruyor ama bulutta çalışmaz.

**Railway Hobby'de Volume yedeği yok.** Bu yüzden yedekleme uygulama içinde
(`services/backup.py`): haftalık .zip (DB + tüm yüklenen dosyalar), son 8
saklanır. SQLite, dosyayı kopyalayarak değil kendi backup API'siyle
alınıyor — yazma anına denk gelen bozuk yedeği önlemek için.

**Yedek geri yükleme vektör dizinini diskte değiştirir.** Chroma istemcileri
süreç içinde yola göre önbelleğe aldığı için `vector_store.reset_client()`
hem kendi değişkenlerini hem `SharedSystemClient.clear_system_cache()`
çağırmak zorunda; yoksa asistan sunucu yeniden başlatılana kadar bozuk kalır.

**`reindex_all()` değişmemiş dokümanları atlar.** Her açılışta tüm PDF'leri
yeniden gömmek doküman sayısıyla orantılı bir açılış süresi demekti ve
platformun açılış zaman aşımını patlatırdı. Vektörler kalıcı diskte; yeniden
üretmeye gerek yok. Tam yeniden kurulum için `reindex_all(force=True)`.

**PubMed İngilizce indeksli.** Türkçe soru doğrudan aratılırsa neredeyse hiç
sonuç dönmez; `rag.py` önce Qwen ile kısa İngilizce anahtar kelimelere
çeviriyor. ("PubMed çalışmıyor" şikâyetinin sebebi buydu, bağlantı değil.)

**Web'de kamera.** `expo-image-picker`'ın "kamera" seçeneği web'de aslında
dosya seçicidir; kullanıcı galeriden eski bir fotoğraf seçebiliyordu ve bu
check-in fotoğrafının amacını boşa çıkarıyordu. Web'de `WebCameraModal`
(expo-camera) canlı kameradan kare yakalar; galeriye erişim yolu yok.
Native'de `launchCameraAsync` zaten sadece kamera.

**iOS'ta web push güvenilir değil** (16.4+ ve ana ekrana ekleme şartı, simge
silinince susar). Vade/SKT uyarıları bu yüzden push değil, her sabah
`DIGEST_HOUR`'da gönderilen tek bir **e-posta özeti** (`daily_digest.py`).
Bildirilecek bir şey yoksa e-posta gönderilmez.

**EvoBulut PDF'leri `invoice_folder/evobulut/` altına iner.** Kök klasör,
elle bırakılan PDF'ler için watchdog tarafından (recursive=False) izleniyor;
köke inseydi aynı PDF bir de OCR ile, daha düşük güvenle işlenip API'den
gelen doğru verinin üzerine yazardı.

**EvoBulut API biçimi** (`services/evobulut.py`): tek uç, `cmd` ile
yönlendirme; login `cmd:euas` → `veri.Ana[0].UID`; token hem body'de `UID`
hem `X-ClientId` header'ında. Satış faturaları `cmd:jq_list, tur:31`,
sayfa başına 30 kayıt. `Kalan == 0` → ödendi. `eFaturaPdfGetir` PDF'i değil
**indirme URL'si** döner. `G.a_sbelge_seri_no` "GÖNDERİLMEDİ" ise fatura no
yok demektir.

**Bildirim okundu durumu kişi bazlı** (`notification_reads` tablosu). Eskiden
tek global bayraktı ve bir çalışan zili temizleyince herkesinki temizleniyordu.

**İşlem günlüğü** (`services/audit.py`): kayıt, çağıranın oturumuna commit
edilmeden eklenir — işlem geri alınırsa günlük de geri alınır. Tek istisna
yedek geri yükleme: veritabanının üzerine yazdığı için kayıt sonradan ayrı
bir oturumda yazılır. Günlüğe yazamamak asıl işlemi bozmamalı.

**Stokta SKT ve hedeflerde ürün zorunlu değil.** SKT boş bırakılabilir
(yazılıp okunamıyorsa hata verilir); SKT'siz kayıtlar listede sona düşer.
Hedefler ürüne bağlı (ilerleme stok kullanımından otomatik) ya da serbest
(başlıklı, ilerleme yönetici tarafından +/− ile) olabilir; ürüne bağlı
hedeflerde elle giriş otomatik sayının üstüne eklenir.

**Stok CSV'sinde bilinmeyen ref no otomatik ürün açar.** Ref no zaten varsa
mevcut ürün kullanılır — stok listesinde her zaman **ürün listesindeki ad**
görünür, CSV'de farklı yazılmış olsa bile.

## Ortam değişkenleri (Railway → Variables)

Tam liste ve açıklamalar: `backend/.env.example`. Kritik olanlar:

| Değişken | Not |
|---|---|
| `SECRET_KEY`, `SEED_ADMIN_PASSWORD` | Ayarlı olduklarını doğrula; yoksa depoda görünen varsayılanlar kullanılır |
| `DATABASE_URL` | `sqlite:////app/data/app.db` (Volume) |
| `RESEND_API_KEY`, `SMTP_FROM` | E-posta özeti için |
| `EVOBULUT_USERNAME/PASSWORD/APP_NAME` | Fatura senkronizasyonu (saatte bir) |
| `QWEN_BASE_URL/API_KEY/MODEL` | Alibaba Model Studio (token başına ücretli) |
| `CORS_ORIGINS` | Şu an `*`; `https://saha.7medikal.com` ile daraltılabilir |

## Teşhis uçları (hepsi admin)

Bir şey "çalışmıyor" dendiğinde önce bunlara bak — gerçek hatayı gösterirler,
normal akışta hatalar sessizce yutulur:

- `GET /invoices/evobulut-diagnostics` ve `.../pdf/{id}`
- `GET /assistant/pubmed-diagnostics`
- `POST /notifications/email-test`, `POST /notifications/digest-run`
- `POST /invoices/evobulut-sync` (senkronizasyonu elle tetikler)

## Açık işler

- **Resend**: alan adı doğrulandı; `RESEND_API_KEY` + `SMTP_FROM` Railway'e
  girilip `POST /notifications/email-test` ile doğrulanacak.
- Yedeklerin dış depoya (örn. Cloudflare R2) otomatik kopyalanması — şu an
  yedekler yalnızca Railway diskinde.
- Asistanın EvoBulut'a canlı sorgu sorabilmesi ("bu ay ne kadar fatura
  kestik").
- Yönetici panosu (grafikler/özetler).
- `api.7medikal.com` gibi kendi alan adı — operatörler `*.railway.app` gibi
  paylaşımlı adresleri filtreleyebiliyor (Netlify'da bu sorun yaşandı, kendi
  alan adına geçilerek çözüldü).
