# 7AI Saha Uygulaması

Şirket çalışanları için konsinye stok takibi, fatura/vade takibi ve klinik
literatür asistanı içeren mobil uygulama. İki parçadan oluşur:

- **`backend/`** — FastAPI ile yazılmış REST API (veritabanı, fatura PDF
  okuma, hatırlatmalar, Qwen tabanlı RAG asistanı).
- **`mobile/`** — Expo (React Native + TypeScript) ile yazılmış, aynı
  kod tabanından hem iOS/Android native uygulama hem de bir **web
  uygulaması (PWA)** olarak çalışabilen istemci. 4 sekme: **Stok Takip**,
  **Fatura Takip**, **Klinik Asistan**, **Çalışan Takip**.

> Çalışanlarınızın telefonlarından erişebileceği şekilde backend'i canlıya
> almak için **`DEPLOYMENT.md`** dosyasındaki adım adım Railway rehberine
> bakın.

## Mobil uygulamayı web (PWA) olarak dağıtma

App Store/Play Store ücreti ödemeden, App Store harici dağıtım
kısıtlamalarına takılmadan çalışanlarınıza ulaştırmanın yolu: uygulamayı
bir web sitesi olarak yayınlamak. Çalışanlar Safari/Chrome'da siteyi açıp
"Ana Ekrana Ekle" dediğinde, telefonlarında gerçek bir uygulama gibi
görünen bir simge oluşur (tarayıcı çerçevesi olmadan tam ekran açılır).

```bash
cd mobile
npm run build:web
```

Bu komut `mobile/dist/` klasörüne statik bir site üretir (HTML/JS/CSS +
`manifest.json` + ikonlar). Bu klasörü herhangi bir statik site
barındırma servisine (Cloudflare Pages, Netlify, Vercel — hepsinin
ücretsiz planı yeterlidir) yükleyebilirsiniz.

Bilinen platform farkları:
- Kamera girişi (Çalışan Takip) tarayıcının kamera izniyle çalışır;
  yerel uygulamadaki kadar sorunsuz ama davranışı tarayıcıya göre
  hafif değişebilir.
- Fatura PDF'i indirme, native'de olduğu gibi paylaşım menüsü yerine
  tarayıcının kendi indirme mekanizmasını kullanır.

## Neden bu mimari?

- Tek bir merkezi backend + tüm çalışanların kullandığı mobil uygulama,
  "hangi ürün hangi hastanede" karmaşasını çözer: her taşıma işlemi
  sunucuda kayıt altına alınır, herkes aynı güncel veriyi görür.
- Fatura klasörü izleme + PDF metin ayrıştırma, çalışanların elle veri
  girmesini ortadan kaldırır; vade tarihi geldiğinde otomatik bildirim
  üretir.
- Klinik asistan yalnızca sizin yüklediğiniz klinik çalışmalara ve
  PubMed'e dayanarak cevap verir; genel/alakasız sorulara cevap vermez.

---

## 1) Stok Takip (Konsinye)

Her ürün; **ref numarası**, **ÜBB numarası**, **lot numarası**, **seri
numarası** ve **SKT** ile tek tek izlenir (`StockItem`). Bir ürün bir
hastaneye gönderildiğinde, başka bir hastaneye taşındığında, bir
çalışanın aracına alındığında veya depoya iade edildiğinde
`POST /stock/{id}/transfer` çağrılır ve bu hareket `StockMovement`
tablosuna geçmiş olarak yazılır — böylece "hangi üründen hangi
hastanede/kimin aracında ne var" sorusu her zaman güncel ve geriye dönük
izlenebilir olur. Çalışanlar ref/ÜBB/lot/seri numarasıyla arama yapıp bir
ürünün o an nerede olduğunu bulabilir. SKT'si yaklaşan/geçen ürünler için
otomatik bildirim üretilir (`SKT_WARNING_DAYS`).

### Yetkiler: admin veri girer, çalışan sahada günceller

- **Sadece admin**: hastane/ürün kartı açma, yeni stok kaydı (lot/seri)
  oluşturma, toplu içe aktarma, fatura yükleme.
- **Tüm çalışanlar**: mevcut bir stok kaydını hastaneler arasında ya da
  kendi aracına/aracından taşıma (`POST /stock/{id}/transfer`,
  `to_vehicle: true` ile "arabama al"), kullanıldı olarak işaretleme ve
  gerekirse bu işareti geri alma.

### Toplu hastane/ürün/stok/fatura girişi (Excel/CSV, tek seferde)

Onlarca/yüzlerce kaydı telefondan tek tek eklemek yerine, admin
bilgisayarında bir tablo hazırlayıp CSV olarak (`/docs` üzerinden,
Excel'den "CSV olarak kaydet" → "Try it out" ile dosya seçerek)
yükleyebilir (virgül veya noktalı virgülle ayrılmış her iki format da
desteklenir):

- **`POST /hospitals/bulk-upload`** — sütunlar: `name` (zorunlu), `city`,
  `address`, `contact_person`, `contact_phone`. Aynı isimde hastane
  varsa o satır sessizce atlanır.
- **`POST /products/bulk-upload`** — sütunlar: `name`, `reference_no`
  (zorunlu), `ubb_no`, `manufacturer`, `unit`, `notes`. Aynı ref no'ya
  sahip ürün varsa o satır atlanır.
- **`POST /stock/bulk-upload`** — sütunlar: `reference_no`, `lot_no`,
  `skt` (zorunlu; `2026-12-31` veya `31.12.2026` formatında), `serial_no`,
  `quantity`, `hospital_name` (opsiyonel; boşsa depo). `reference_no` daha
  önce eklenmiş bir ürünle, `hospital_name` daha önce eklenmiş bir
  hastaneyle eşleşmelidir — önce ürünleri/hastaneleri ekleyin.
- **`POST /invoices/bulk-upload`** — CSV değil, birden fazla PDF dosyasını
  aynı anda seçip (`files` alanına) yükler; her biri ayrı ayrı okunur.

Hepsi `{"created": N, "skipped": N, "errors": [...]}` benzeri bir özet
döner; `errors` listesi hangi satırda/dosyada ne sorun olduğunu gösterir.
Mobil uygulamada henüz bu toplu yüklemeler için bir ekran yok — sadece
tek tek yükleme (fatura/klinik çalışma PDF'i, hastane/ürün) mobilde var.

## 2) Fatura Takip

İki şekilde fatura ekleyebilirsiniz:

- **Klasöre atarak** — backend'i kendi sunucunuzda/bilgisayarınızda
  çalıştırıyorsanız `backend/data/invoices/` klasörüne bir fatura PDF'i
  attığınızda arka planda çalışan klasör izleyici (`watchdog`) dosyayı
  yakalar.
- **Uygulamadan yükleyerek** — backend bulutta barındırılıyorsa (bkz.
  `DEPLOYMENT.md`) sunucunun dosya sistemine erişiminiz olmaz; bu durumda
  mobil uygulamada Fatura Takip sekmesindeki 📤 butonuyla (yalnızca
  yönetici hesabında görünür) PDF'i doğrudan yükleyebilirsiniz
  (`POST /invoices/upload`).

Her iki yolda da PDF metni çıkarılır (`pdfplumber`) ve **fatura no /
fatura tarihi / vade tarihi / tutar / firma** bilgileri regex tabanlı bir
ayrıştırıcıyla otomatik doldurulur. Alanlardan biri okunamazsa fatura
"kontrol edilmeli" (`needs_review`) durumuna düşer ve elle düzeltilebilir
(`PATCH /invoices/{id}`). Çalışanlar uygulamadan faturanın PDF'ini
indirebilir/paylaşabilir. Vade tarihi yaklaşan/geçen faturalar için
6 saatte bir çalışan zamanlayıcı otomatik bildirim üretir
(`INVOICE_REMINDER_DAYS`).

> Not: PDF ayrıştırma, yaygın Türkçe e-Fatura/e-Arşiv etiketlerini
> ("Fatura No", "Fatura Tarihi", "Vade Tarihi", "Ödenecek Tutar", ...)
> arayan regex kurallarına dayanır. Kullandığınız e-fatura entegratörünün
> çıktısı farklı bir şablon kullanıyorsa `backend/app/services/invoice_parser.py`
> içindeki `*_LABELS` listelerine kendi etiketlerinizi eklemeniz gerekebilir.

## 3) Klinik Asistan (Qwen + RAG + PubMed)

Klinik çalışma PDF'lerini de fatura PDF'leri gibi iki şekilde
ekleyebilirsiniz: backend'in çalıştığı makinedeyseniz
`backend/data/clinical_docs/` klasörüne atarak, bulutta barındırıyorsanız
mobil uygulamada Klinik Asistan sekmesindeki 📤 "Çalışma Yükle" butonuyla
(yalnızca yönetici hesabında görünür, `POST /assistant/documents/upload`).
Her iki durumda da PDF, uygulama açılışında veya `POST /assistant/reindex`
çağrısında otomatik olarak parçalanıp yerel bir vektör veritabanına
(Chroma, tamamen yerel embedding — harici API anahtarı gerektirmez)
indekslenir. Bir çalışan soru sorduğunda:

1. Sorusuyla en alakalı doküman parçaları vektör aramasıyla bulunur.
2. Aynı anda PubMed'de (NCBI E-utilities, ücretsiz) ilgili güncel yayınlar
   aranır.
3. Bulunanlar **Qwen** modeline (herhangi bir OpenAI-uyumlu uç nokta —
   yerel Ollama, Alibaba DashScope veya kendi barındırdığınız vLLM)
   bağlam olarak verilir; model yalnızca bu kaynaklara dayanarak,
   kaynak göstererek cevap verir.
4. Ne yerel dokümanlarda ne PubMed'de ilgili bir şey bulunamazsa veya soru
   ürün/hastalık konusuyla alakasızsa, model soruyu yanıtlamayı reddeder.

Qwen'i bağlamak için `.env` dosyasında `QWEN_BASE_URL`, `QWEN_API_KEY`,
`QWEN_MODEL` değişkenlerini kendi ortamınıza göre ayarlamanız yeterli
(bkz. `backend/.env.example`).

## 4) Çalışan Takip

Çalışanlar sabah hastaneye vardıklarında bu sekmeden hastaneyi seçip
kamerayla bir fotoğraf çekerek giriş yapar (`POST /checkins`); isterlerse
o hastaneyle ilgili bir not da ekleyebilirler. Kayıt anı otomatik olarak
"işe başlama saati", seçilen hastane de "o an nerede oldukları" olarak
tutulur. Çalışanlar yalnızca kendi geçmişlerini görür; yönetici hesabı
"Tüm Ekip" görünümüyle herkesin ne zaman hangi hastanede giriş yaptığını
ve yazdıkları notları görebilir.

---

## Kurulum

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # değerleri kendi ortamınıza göre düzenleyin
uvicorn app.main:app --reload
```

İlk açılışta `admin@sirket.com` / `DegistirilecekSifre123!` (veya
`.env`'de belirlediğiniz `SEED_ADMIN_EMAIL`/`SEED_ADMIN_PASSWORD`) ile bir
yönetici hesabı otomatik oluşturulur — **ilk girişten sonra şifreyi
değiştirin** ve `POST /auth/users` ile çalışan hesapları ekleyin.

API dokümantasyonu: `http://localhost:8000/docs`

### Mobil uygulama

```bash
cd mobile
npm install
```

`app.json` içindeki `expo.extra.apiBaseUrl` değerini backend'inizin
adresine göre güncelleyin (telefondan test ederken `localhost` çalışmaz;
bilgisayarınızın yerel ağ IP'sini kullanın, örn. `http://192.168.1.20:8000`).

```bash
npx expo start
```

Expo Go uygulamasıyla QR kodu okutarak telefonda test edebilir, ya da
`npx expo run:ios` / `npx expo run:android` ile native build alabilirsiniz.

---

## Ortam değişkenleri (backend/.env)

Tüm değişkenler ve açıklamaları `backend/.env.example` dosyasında.
Öne çıkanlar:

| Değişken | Açıklama |
|---|---|
| `INVOICE_FOLDER` | İzlenen fatura PDF klasörü |
| `INVOICE_REMINDER_DAYS` | Vade tarihinden kaç gün önce hatırlatma başlasın |
| `SKT_WARNING_DAYS` | SKT'den kaç gün önce uyarı başlasın |
| `CLINICAL_DOCS_FOLDER` | İndekslenen klinik çalışma PDF klasörü |
| `QWEN_BASE_URL` / `QWEN_API_KEY` / `QWEN_MODEL` | Qwen'in sunulduğu OpenAI-uyumlu uç nokta |
| `PUBMED_EMAIL` / `PUBMED_API_KEY` | NCBI E-utilities için (opsiyonel ama önerilir) |
| `CHECKIN_PHOTOS_FOLDER` | Çalışan giriş fotoğraflarının saklandığı klasör |

## Sonraki adımlar / bilinmesi gerekenler

- **Push bildirimleri**: Şu an bildirimler uygulama içi listedir (API
  polling). Telefona push bildirim göndermek için Firebase Cloud
  Messaging / Expo Push kurulumu ve ilgili kimlik bilgileri gerekir —
  bu depoya dahil edilmemiştir.
- **Veritabanı**: Varsayılan SQLite, küçük/orta ölçekli kullanım için
  yeterlidir. Üretimde `DATABASE_URL`'i Postgres'e çevirebilirsiniz.
  Şema `Base.metadata.create_all` ile otomatik oluşturulur; şema
  değişikliklerinde gerçek bir migration aracı (Alembic) eklemeniz
  önerilir.
- **Dış ağ erişimi**: Fatura klasörü izleme ve klinik doküman indeksleme
  tamamen yerelde çalışır; yalnızca Qwen çağrıları ve PubMed aramaları
  dışa ağ erişimi gerektirir.
