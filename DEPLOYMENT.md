# Backend'i Railway'de Yayına Alma (adım adım)

Bu rehber, teknik bilgi gerektirmeden, backend'i çalışanlarınızın
telefonlarının her yerden erişebileceği bir adrese (`https://...up.railway.app`)
taşımanız için gerekli adımları içerir. Railway'i seçtik çünkü tamamen
tıklama tabanlı bir arayüzü var, ücretsiz kredi ile başlayıp aylık birkaç
dolara devam edebiliyorsunuz ve kalıcı disk (Volume) desteği var — bu bizim
için önemli çünkü fatura PDF'leri, klinik çalışmalar ve veritabanı kalıcı
olarak saklanmalı.

## 1) Railway hesabı açın

[railway.app](https://railway.app) adresine gidin, "Login" ile GitHub
hesabınızla giriş yapın (aynı GitHub hesabı, kodun bulunduğu
`umutdroid-collab/7ai` deposuna erişimi olmalı).

## 2) Yeni proje oluşturun

- "New Project" → "Deploy from GitHub repo" seçin.
- `umutdroid-collab/7ai` deposunu seçin (ilk kullanımda Railway'in GitHub
  hesabınıza erişim izni istemesi normaldir, onaylayın).

## 3) Servisin kök klasörünü ayarlayın

Depoda hem `backend/` hem `mobile/` var; Railway'e yalnızca `backend/`
klasörünü build etmesini söylememiz gerekiyor:

- Oluşan servise tıklayın → **Settings** → **Source** → **Root Directory**
  alanına `backend` yazın → kaydedin.
- Railway, `backend/Dockerfile`'ı otomatik algılayıp onunla build edecek.

## 4) Kalıcı disk (Volume) ekleyin

Bu adım olmadan her yeniden başlatmada veritabanınız ve yüklediğiniz
dosyalar silinir:

- **Settings** → **Volumes** → **Add Volume**
- Mount path: `/app/data`
- Kaydedin.

## 5) Ortam değişkenlerini girin

Servis sayfasında **Variables** sekmesine girip aşağıdakileri tek tek
ekleyin (soldaki isim, sağdaki değer):

| Değişken | Değer |
|---|---|
| `SECRET_KEY` | Aşağıdaki notta verilen değeri kullanın (veya kendi rastgele uzun bir metin yazın) |
| `DATABASE_URL` | `sqlite:////app/data/app.db` |
| `INVOICE_FOLDER` | `/app/data/invoices` |
| `CLINICAL_DOCS_FOLDER` | `/app/data/clinical_docs` |
| `VECTOR_DB_DIR` | `/app/data/vectorstore` |
| `CORS_ORIGINS` | `*` |
| `SEED_ADMIN_EMAIL` | Kendi yönetici e-postanız, örn. `admin@sirketiniz.com` |
| `SEED_ADMIN_PASSWORD` | **Kendi belirleyeceğiniz güçlü bir şifre** (aşağıya bakın) |
| `QWEN_BASE_URL` | Aşağıdaki "Qwen'i bağlama" bölümüne bakın |
| `QWEN_API_KEY` | Aşağıdaki "Qwen'i bağlama" bölümüne bakın |
| `QWEN_MODEL` | Aşağıdaki "Qwen'i bağlama" bölümüne bakın |
| `PUBMED_EMAIL` | Kendi e-postanız (NCBI kuralları gereği önerilir) |

> ⚠️ **Önemli güvenlik notu**: `backend/.env.example` dosyasında (herkese
> açık kod deposunda) örnek bir varsayılan yönetici şifresi yazılıdır.
> `SEED_ADMIN_EMAIL` ve `SEED_ADMIN_PASSWORD` değişkenlerini **mutlaka**
> kendi değerlerinizle burada belirtin — belirtmezseniz uygulama herkesin
> depoda görebileceği varsayılan şifreyle bir yönetici hesabı oluşturur.

> 🔑 **SECRET_KEY için önerilen değer** (bu oturuma özel üretildi, kimseyle
> paylaşmadım, doğrudan kullanabilirsiniz):
> `c9de468f1ae2c5cb206cc9b0bfcc1b31795372283bb8c849cb1fad634181a2dc`

## 6) Qwen'i bağlama

Qwen'i çalıştırmanın en basit (kendi sunucu/GPU gerektirmeyen) yolu
Alibaba Cloud'un yönetilen **DashScope** servisidir:

1. [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com) adresinden ücretsiz bir hesap açın (yeni hesaplara genelde deneme kredisi tanımlanır).
2. Bir API anahtarı oluşturun.
3. Değişkenleri şöyle girin:
   - `QWEN_BASE_URL` = `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
   - `QWEN_API_KEY` = oluşturduğunuz anahtar
   - `QWEN_MODEL` = `qwen-plus` (daha ucuz/hızlı için `qwen-turbo`, daha güçlü için `qwen-max`)

Alternatif olarak kendi sunucunuzda Ollama ile Qwen çalıştırıp
`QWEN_BASE_URL`'i o adrese yönlendirebilirsiniz, ancak bu ayrı bir sunucu
ve teknik kurulum gerektirir — küçük ölçekte DashScope daha pratiktir.

## 7) Deploy edin ve genel adresi alın

- **Deploy** butonuna basın (Root Directory ve Volume ayarlarını
  kaydettiğinizde Railway otomatik olarak yeniden deploy eder).
- Build tamamlandığında **Settings** → **Networking** → **Generate Domain**
  butonuna basın. Size `https://xxxxx.up.railway.app` gibi bir adres
  verecek — bu, backend'inizin herkese açık adresi.
- O adres + `/docs` (örn. `https://xxxxx.up.railway.app/docs`) açıldığında
  API dokümantasyonunu görüyorsanız her şey çalışıyor demektir.

## 8) Mobil uygulamayı bu adrese yönlendirin

`mobile/app.json` içindeki `expo.extra.apiBaseUrl` değerini Railway'in
verdiği adresle değiştirin:

```json
"extra": {
  "apiBaseUrl": "https://xxxxx.up.railway.app"
}
```

Bu değişikliği yapıp uygulamayı yeniden yayınladığınızda (veya Expo Go
ile test ederken `npx expo start` çalıştırdığınızda) mobil uygulama artık
her yerden bu backend'e bağlanabilir.

## 9) İlk giriş ve kullanıma başlama

1. `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` ile giriş yapın.
2. `POST /auth/users` ile (veya ileride ekleyeceğimiz bir yönetim ekranıyla)
   çalışan hesapları oluşturun.
3. Hastaneleri ve ürünleri tanımlayın.
4. Artık fatura ve klinik çalışma PDF'lerini **sunucuya SSH ile girmenize
   gerek yok** — mobil uygulamada Fatura Takip ve Klinik Asistan
   sekmelerindeki 📤 yükleme butonlarını (yalnızca yönetici hesabında
   görünür) kullanarak doğrudan telefonunuzdan/bilgisayarınızdan
   yükleyebilirsiniz.

## Sonradan güncelleme

Kod deposuna (`umutdroid-collab/7ai`) yeni bir şey push edildiğinde Railway
`backend/` klasöründe değişiklik varsa otomatik olarak yeniden deploy eder;
Volume'daki veriler (veritabanı, PDF'ler) korunur.
