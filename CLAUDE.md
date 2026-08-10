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
Canlıda doğrulandı (03.08.2026): `email-test` → `provider: "resend"`, mail
ulaştı. Gönderen `7medikal.com` alt alan adı Resend'de doğrulanmış durumda.

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
Tek sorgu da yetmiyor: PubMed terimleri **VE** mantığıyla arıyor ve **ticari
marka adlarını indekslemiyor**, dolayısıyla "Efferon Neo SOFA score" gibi dar
bir sorgu sıfır sonuç döndürüyordu (canlıda ölçüldü). Çeviri artık aynı
çağrıda iki satır üretiyor: spesifik sorgu + marka içermeyen, mekanizma/klinik
durum düzeyinde genel sorgu. İlki boş dönerse ikinciye düşülür.

**Embedding modeli yalnızca İngilizce, bu yüzden vektör araması İngilizce
sorguyla yapılır.** Chroma'nın varsayılanı ONNX all-MiniLM-L6-v2 ve Türkçe
bilmiyor: aynı İngilizce dokümana Türkçe soruyla olan uzaklık 1.75-1.81
çıkarken İngilizce soruyla 0.49-0.70 çıkıyor — alakasız bir soru ise 2.02
(yerel ölçüm). Yani Türkçe soruda doküman araması pratikte rastgele parça
döndürüyordu. PubMed için zaten üretilen çeviri artık vektör aramasında da
kullanılıyor (`dokuman_sorgusu`); ek model çağrısı yok, çeviri iki dalın da
önüne alındı. Çeviri koparsa Türkçe soruya düşülür.

**Asistan iki sebeple fazla reddediyordu**, ikisi de canlı ölçümle yakalandı:
(1) çeviri adımı bilmediği ürünün etken maddesini uyduruyordu — "efferon
hastaların laktat seviyesini düşürür mü" sorgusu `lactate levels acetaminophen`
oluyor, bu sorgu hem PubMed'i hem vektör aramasını zehirliyordu (parçalar
1.05-1.11'e düşüp eleniyordu). Prompt artık ürün adını harfi harfine korumayı,
hiçbir satırda etken madde tahmin etmemeyi şart koşuyor — **ve ürün adının tek
başına yazılmasını da yasaklıyor**: ilk düzeltmede model klinik terimleri atıp
sadece `Efferon` üretti, uzaklık 1.05'ten 1.431'e çıktı. Sorgu ürün adı **ve**
klinik terimleri birlikte içermeli. (2) Sistem promptu
"kaynaklar soruyu tam cevaplamıyorsa reddet" diyordu; en yakın parça 0.594
(açıkça ilgili) olan soru bile reddediliyordu. Ret kriteri iki kez daraltıldı:
"kaynakların hiçbiri ilgili değilse de reddet" maddesi de yetmedi — model
"sorulan parametre (bilirubin) hiçbir kaynakta geçmiyor" durumunu ilgisizlik
sayıp 0.772'lik parçalarla reddetti. Artık ret **yalnızca sorunun kendisine**
bakıyor (alan dışı mı?); kaynakların içeriği bu kararı hiç etkilemiyor.
Sorulan parametre kaynaklarda yoksa model bunu söyleyip aynı ürün/durum için
bildirilen sonuçları özetliyor. Eşiği geçen parça varken yine de ret gelirse
teşhis çıktısında `model_kaynak_varken_reddetti` olarak görünür.

**Vektör aramasının kendi alaka eşiği yok**, bu yüzden `rag.py` uzaklığa göre
eliyor (`DOCUMENT_MAX_DISTANCE`, varsayılan 0.95). Chroma her zaman "en yakın
5"i döner; ilgisiz bir soruda bile 5 parça gelir ve eşik olmadan bunlar ~2000
token'lık bağlam olarak modele gidip boşuna 8-14 saniye beklenirdi. Eşik canlı
ölçümle seçildi: konusu kapsanan soruda 0.595-0.672, kapsanmayan soruda
1.142-1.235. Uzaklıklar teşhis çıktısına **elemeden önce** yazılır, yoksa eşik
ileride ayarlanamaz.

**Asistan hızı: soru başına dört ağ turu var** (vektör araması, Qwen çevirisi,
NCBI, Qwen cevabı) ve eskiden hepsi sırayla çalışıp süreleri toplanıyordu.
Şimdi doküman araması ile PubMed dalı `_gather_sources()` içinde eş zamanlı
çalışıyor; çeviri `lru_cache` ile tekrar eden sorularda hiç modele gitmiyor.
Ölçüm `answer_question(..., timings)` ile her yolda tutulur ve loga düşer —
"yavaş" denildiğinde `POST /assistant/timing-diagnostics` ile hangi aşamanın
baskın olduğuna bak, tahminle optimize etme. Kalan süre neredeyse tamamen
Qwen'in cevabı üretmesidir; oradaki kollar kod değil **ayar**:
`QWEN_MAX_TOKENS` (üretilen token sayısı süreyle doğru orantılı — ama Türkçe
token açısından pahalı: 600'de 1715 karakterlik bir cevap cümle ortasında
kesildi, 1200 uygun bir taban. Sınıra takılan cevap `finish_reason: "length"`
ile yakalanıp hem kullanıcıya bildiriliyor hem teşhiste `cevap_kesildi`
olarak görünüyor; sessizce yarım klinik cevap göstermek tehlikeliydi),
`QWEN_MODEL` (küçük/hızlı model) ve Qwen3 ailesindeyseniz
`QWEN_DISABLE_THINKING=true` (varsayılan "düşünme" modu cevaptan önce
görünmeyen uzun bir muhakeme üretir). `QWEN_TIMEOUT_SECONDS` de eklendi:
OpenAI istemcisinin varsayılanı 10 dakikaydı, model susarsa kullanıcı o kadar
bekliyordu.

**Embedding modeli açılışta ısıtılır** (`vector_store.warm_up()`, arka planda
bir thread). ONNX MiniLM ilk kullanımda indirilip yükleniyor ve bu bedeli
günün ilk sorusunu soran kullanıcı ödüyordu.

**Web'de kamera.** `expo-image-picker`'ın "kamera" seçeneği web'de aslında
dosya seçicidir; kullanıcı galeriden eski bir fotoğraf seçebiliyordu ve bu
check-in fotoğrafının amacını boşa çıkarıyordu. Web'de `WebCameraModal`
(expo-camera) canlı kameradan kare yakalar; galeriye erişim yolu yok.
Native'de `launchCameraAsync` zaten sadece kamera.

**Hatırlatıcılar (`follow_ups`) yöneticinin toplantı defteri.** Çalışanın
check-in yorumunda dikkat çeken bir şey listede aşağı kaydıkça kayboluyordu;
kart üzerindeki "Takibe Al" o yorumu bağımsız bir kayda dönüştürür. Tarihi
gelen (veya geçen) açık notlar **günlük özet e-postasının en üstünde** çıkar —
hatırlatmanın yapıldığı yer orası, ayrı bir bildirim kanalı yok. Tamamlananlar
listeden düşer ama silinmez; `include_done=true` ile görülür. Notun doğduğu
check-in silinirse not kalır, bağlantı boşa düşer.

**Check-in notunda dikte tarayıcının kendi motoruyla** (`utils/speechToText.ts`,
Web Speech API): ücretsiz, ek bağımlılık yok, ses bizim sunucumuza gitmiyor.
Native'de tuş gösterilmez — klavyenin mikrofon tuşu zaten aynı işi görüyor ve
bir dikte kütüphanesi native derleme gerektirirdi. Firefox desteklemiyor,
Chrome tanımayı kendi sunucusunda yaptığı için internet şart; desteklenmeyen
yerde `isSupported()` false döner ve tuş hiç çizilmez.

**Oturum 24 saat, "Beni hatırla" varsayılan kapalı.** Token süresi
`ACCESS_TOKEN_EXPIRE_MINUTES` (varsayılan 1440); **Railway'de bu değişken ayrıca
tanımlıysa varsayılan geçersizdir**, süre değişmiyorsa önce oraya bakın (aynı
tuzak geliştirme makinesindeki `.env` için de geçerli). "Beni hatırla"
işaretlenirse e-posta + şifre `secureStorage`'a yazılır: native'de
Keychain/Keystore, **web'de localStorage** — yani tarayıcıda düz metin durur ve
aynı kaynaktaki her betik okuyabilir. Bu yüzden kutu varsayılan olarak kapalı,
kayıt yalnızca başarılı girişten sonra yapılıyor ve işaret kaldırıldığı anda
saklananlar siliniyor.

**Check-in fotoğrafları sunucuda küçültülür** (`services/images.py`), istemcide
değil: eski uygulama sürümleri, farklı tarayıcılar ve doğrudan API'ye yapılan
istekler yine ham dosya gönderir, o yüzden küçültme yükleme anında ve şartsız
yapılır. Ham dosya saklanmaz — 12 MP telefon fotoğrafı 2.4 MB'tan ~540 KB'a
iner (1280 px, JPEG q72), ayrıca ~10 KB'lık bir önizleme üretilir. Liste
kartları önizlemeyi (`?boyut=onizleme`), büyütünce açılan görüntüleyici tam
boyu ister; listede her kart için tam boy indirmek mobil veride pahalıydı.
EXIF yönü uygulanır (yoksa fotoğraflar yan yatık görünür) ve EXIF taşınmaz
(yer + konum sızıntısı). Küçültme başarısız olursa dosya olduğu gibi kalır;
check-in kaydı fotoğraf yüzünden kaybedilmemeli. Birikmiş eski fotoğraflar
için `POST /checkins/compress-existing` (admin) var.

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
| `SECRET_KEY`, `SEED_ADMIN_PASSWORD` | Railway'de ayarlı (doğrulandı 03.08.2026); yoksa depoda görünen varsayılanlara düşer |
| `DATABASE_URL` | `sqlite:////app/data/app.db` (Volume) |
| `RESEND_API_KEY`, `SMTP_FROM` | E-posta özeti için |
| `EVOBULUT_USERNAME/PASSWORD/APP_NAME` | Fatura senkronizasyonu (saatte bir) |
| `QWEN_BASE_URL/API_KEY/MODEL` | Alibaba Model Studio (token başına ücretli) |
| `QWEN_MAX_TOKENS` (900), `QWEN_TIMEOUT_SECONDS` (60), `QWEN_DISABLE_THINKING` (false) | Asistan hızının ayarla çevrilen kolları |
| `CORS_ORIGINS` | `https://saha.7medikal.com` ile daraltıldı |

## Teşhis uçları (hepsi admin)

Bir şey "çalışmıyor" dendiğinde önce bunlara bak — gerçek hatayı gösterirler,
normal akışta hatalar sessizce yutulur:

- `GET /invoices/evobulut-diagnostics` ve `.../pdf/{id}`
- `GET /assistant/pubmed-diagnostics`
- `POST /assistant/timing-diagnostics` (gövde: `{"question": "..."}`) — asistan
  yanıtının hangi aşamada ne kadar beklediğini milisaniye olarak döner
- `POST /notifications/email-test`, `POST /notifications/digest-run`
- `POST /invoices/evobulut-sync` (senkronizasyonu elle tetikler)
- `POST /checkins/compress-existing` (eski fotoğrafları toplu küçültür, kaç MB
  kazanıldığını döner)

## Açık işler

- Eski `SMTP_HOST/USERNAME/PASSWORD` değişkenleri Railway'de duruyorsa
  silinmeli: Resend anahtarı varken kullanılmıyorlar ama anahtar bir gün
  kaldırılırsa sistem sessizce Railway'de çalışmayan SMTP yoluna düşer.
- Yedeklerin dış depoya (örn. Cloudflare R2) otomatik kopyalanması — şu an
  yedekler yalnızca Railway diskinde.
- Asistanın EvoBulut'a canlı sorgu sorabilmesi ("bu ay ne kadar fatura
  kestik").
- Yönetici panosu (grafikler/özetler).
- `api.7medikal.com` gibi kendi alan adı — operatörler `*.railway.app` gibi
  paylaşımlı adresleri filtreleyebiliyor (Netlify'da bu sorun yaşandı, kendi
  alan adına geçilerek çözüldü).
