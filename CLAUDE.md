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

- Backend: `https://api.7medikal.com` (Railway custom domain; Railway'in kendi
  `*.up.railway.app` adresi de çalışmaya devam eder — geri dönüş yolu)
- Web/PWA: `https://saha.7medikal.com` (Netlify'dan **Cloudflare Pages**'e
  taşınıyor — sebep: Netlify ücretsiz planında krediler bitince *production
  deploy'lar tamamen duruyor*, elle yükleme dahil. İki kez yaşandı ve iş
  durdu. Cloudflare Pages ayarları: kök dizin `mobile`, komut
  `npm run build:web`, çıktı `dist`, watch path `mobile/*`. Netlify sitesi geri
  dönüş için bir süre ayakta bırakılmalı.)

**Paylaşımlı platform alan adları Türkiye'de filtreleniyor — kendi alan adı
şart.** `*.pages.dev` ofis ağından `ERR_CONNECTION_TIMED_OUT` veriyor (aynı
soru işareti daha önce `*.railway.app` ve Netlify'da da yaşandı). Aynı adres
mobil veriden açılıyor, yani site sağlam; engel ağ seviyesinde. Sonucu:
**yayını `pages.dev` üzerinden test etmeye çalışmayın**, kendi alan adınızda
geçici bir alt alan adı (`yeni.7medikal.com`) açıp orada test edin. Zaman
aşımını "deploy bozuk" sanmak kolay — deploy bozuk olsaydı Cloudflare'in 404
sayfası gelirdi, bağlantı hiç kurulamıyorsa sebep filtredir.
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

**Yedeğin ikinci kopyası dış depoda** (`services/offsite_backup.py`): yalnızca
Railway diskinde duran yedek, diskin ya da servisin gittiği senaryoda —yani
yedeğin asıl gerekli olduğu anda— işe yaramaz. Her yedek oluşturulduktan sonra
S3 uyumlu bir depoya kopyalanır ve son `BACKUP_S3_KEEP_COUNT` kopya bırakılır.
Sağlayıcıdan bağımsız (R2/B2/S3 aynı alanlarla çalışır, endpoint değişir).
Yapılandırılmamışsa sessizce atlanır; **yükleme başarısız olursa hata
yükseltilmez** — dış kopya alınamadı diye yerel yedeklemeyi başarısız saymak
yanlış olurdu. Gerçek hatayı görmek için `GET /backups/offsite/status`.

**Dış depodan geri dönüş yolu da olmalı.** Geri yükleme yalnızca yerel
klasördeki dosyayı okuyor; dış kopya bir süre yalnızca *dışarı* giden bir
yoldu, yani tasarlandığı senaryoda (Railway diski gitti) elde kopya olup
sisteme verilemiyordu. `POST /backups/offsite/{dosya}/pull` uzaktaki kopyayı
yerel klasöre indirir, `POST /backups/upload` elde tutulan bir .zip'i
sisteme koyar; ikisinin de ardından normal `restore` çağrılır. Yüklemenin
aksine indirme **hata yükseltir**: kullanıcı bilinçli bir geri yükleme
başlatıyor, sessizce başarısız olması tehlikeli.

**Kodun yedeği git'tir, yedek .zip'i değil.** Zip yalnızca veritabanı ve
yüklenen dosyaları taşır. Kurulumun kendisi (Railway/Cloudflare/R2 ayarları,
hangi ortam değişkeni nereden alınır, sıfırdan kurtarma adımları)
`DEPLOYMENT.md`'de; kod değiştiğinde orayı da güncelleyin — eskimiş bir
kurtarma rehberi kurtarma anında fark edilir. **Sırlar hiçbir yerde
yedeklenmiyor**, yalnızca Railway → Variables içinde durur; hepsi yeniden
üretilebilir ama nereden alınacağı bilinmeli (DEPLOYMENT.md bölüm 3).

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

**Asistan şirket verisi sorularını modele hiç sormadan cevaplıyor**
(`services/business_qa.py`). "Bu ay ne kadar fatura kestik", "Efferon stokta
kaç adet var", "hedefler ne durumda" gibi sorular klinik yola girmeden,
veritabanından deterministik olarak cevaplanıyor. Üç sebep: (1) finansal bir
rakamı Qwen'e paraflattırmak yuvarlama/uydurma riski demek — yanlış bir sayı
cevap alamamaktan kötü; (2) kaynak aramanın anlamı yok; (3) cevap anında
geliyor, klinik yoldaki 8-14 saniye yok.

**Yönlendirme bilinçli olarak muhafazakâr.** Yalnızca GÜÇLÜ iş sinyalleri
tetikliyor (`fatura`, `ciro`, `vade`, `hedef`, `stokta`, `kaç adet`);
`ürün` ve `hastane` gibi zayıf kelimeler klinik sorularda da geçiyor
("Efferon ürünü SOFA skorunu düşürür mü") ve onları kaçırmak asıl özelliği
bozardı. Şüphede kalınca klinik yola düşülür. Beş gerçek klinik soru bu
kuralı test olarak koruyor. Yönlendirme kararı teşhiste
`kaynaklar.is_verisi_konusu` olarak görünür.

**Dönem her cevapta yazılı.** Belirtilmezse "bu ay" varsayılıyor ama bu bir
tahmin; hangi tarih aralığının kullanıldığı yazılmazsa yönetici kafasındaki
başka bir aralıkla eşleştirebilir. Türkçe dönem çözümlemesi deterministik
(`bugün`, `bu hafta`, `geçen ay`, ay adları); ay adı henüz gelmemişse geçen
yılın aynı ayı kastediliyor sayılıyor.

**Veri EvoBulut'tan değil yerel veritabanından okunuyor.** Faturalar zaten
saatte bir senkronize ediliyor; canlı API çağrısı saniyeler ekler ve EvoBulut
erişilemezse cevap hiç gelmez. Son bir saati de görmek gerekirse
`POST /invoices/evobulut-sync`.

**Pano ve asistan aynı hesap katmanını kullanıyor** (`services/metrics.py`).
İkisi de aynı soruları soruyor; hesap iki yerde yazılsaydı zamanla ayrışır ve
aynı soruya iki farklı rakam dönerdi.

**Yönetici panosu Profil ekranının altında, ayrı bir sekme değil**
(`screens/profile/DashboardScreen`, `GET /dashboard/summary`). Altıncı sekme
telefonda alt çubuğu sıkıştırıyordu; pano günde bir bakılan bir ekran, sürekli
erişim gerektirmiyor. Rakamların tamamı **tek çağrıda** dönüyor: dört ayrı
istek mobil veride hem yavaş hem de kısmi yüklenmiş bir ekran demekti.

Panonun asıl riski yanlış rakam göstermesi — yanlış bir sayı, hiç sayı
göstermemekten kötüdür çünkü karara girer. Bu yüzden üç kural: **para
birimleri toplanmaz** (faturalar TRY/USD/EUR karışık, tek bir "toplam"
uydurma bir sayı olurdu — her tutar para birimi bazında ayrı döner),
**ödenmiş faturalar vade rakamlarına girmez** (fatura listesindeki kuralla
aynı, ikisi ayrışmasın) ve **satır değil `quantity` toplanır** (bir stok
satırı birden fazla adet taşıyabiliyor). Hedef ilerlemesi
`sales_targets._with_progress` ile hesaplanır; kopyalanmaz, çünkü hesap
ürüne bağlı/manuel ayrımını ve elle düzeltmeyi içeriyor ve iki yerde
tutulursa zamanla ayrışır.

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

**`app.json` değişikliği yerelde derlerken önbellekten atlanabilir.**
`expo.extra.apiBaseUrl` derleme anında bundle'ın içine gömülüyor; Metro
önbelleği duruyorsa `npm run build:web` aynı bundle'ı (aynı hash'le) yeniden
üretir ve değişiklik çıktıya girmez — "değiştirdim ama olmadı" böyle olur.
Yerelde doğrularken `rm -rf dist .expo node_modules/.cache` ile derleyin ve
çıktıdaki adresi `grep apiBaseUrl dist/_expo/static/js/web/*.js` ile
gerçekten görün. Cloudflare Pages her seferinde temiz klondan derlediği için
orada bu sorun yok.

**Profil ekranındaki sürüm satırı bir teşhis aracı.** `scripts/build-web.js`
derleme anında commit hash'ini `EXPO_PUBLIC_BUILD_COMMIT` ile bundle'a gömüyor
(Cloudflare'de `CF_PAGES_COMMIT_SHA`, yerelde `git rev-parse`). Sebep: "değişiklik
yayında mı yoksa tarayıcı eski sürümü mü sunuyor" sorusu üç kez uzun uzun
araştırıldı — iOS'ta ana ekrana eklenmiş PWA, uygulama **tamamen kapatılana
kadar** sayfayı yeniden yüklemiyor, sayfa yenilemek yetmiyor. Profil ekranının
altındaki hash bu ayrımı tek bakışa indiriyor.

**Yönlendirme ve başlıklar `netlify.toml`'da değil, derleme çıktısında.**
`postexport-web.js` her derlemede `dist/_redirects` (SPA catch-all) ve
`dist/_headers` (içerik özetli dosyalara uzun önbellek, `index.html`'e
bilerek yok) üretir. Sebep: `netlify.toml` yalnızca Netlify kendi derlemesini
yaparken okunuyor; hazır çıktı elle yüklendiğinde ya da başka bir platforma
geçildiğinde devre dışı kalıyordu. `_redirects`/`_headers` ikisi de Netlify ve
Cloudflare Pages tarafından okunuyor. Node sürümü `mobile/.nvmrc` ile sabit.

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

**Fatura PDF'leri de küçültülür ama koşullu** (`services/pdf_compress.py`).
Fotoğraftan farkı: kazanç garanti değil. EvoBulut'tan gelen e-faturalar metin
tabanlıdır, içlerinde küçültülecek görüntü yoktur; taranıp elle bırakılan
faturalar ise sayfa başına birkaç MB'lık görüntü taşır ve asıl kazanç
oradadır (ölçüm: 300 DPI A4 tarama 138 KB → 34 KB, görüntü 2480 px'ten
1600 px'e inip DCTDecode'a çevrilerek). Bu yüzden **sonuç en az %10 küçük
değilse dosya hiç değiştirilmez** — aksi halde her `rescan` çağrısında zaten
optimum olan PDF'ler boşuna yeniden yazılırdı. Şeffaflık/maske taşıyan
görüntülere dokunulmaz (JPEG'e çevrilirse bozulurlar) ve hata hâlinde
orijinal korunur. Küçültme **metin çıkarımından sonra** çağrılır ve zaten
metni etkilemez; fatura alanları aynı okunur. Tek bağlama noktası
`invoice_watcher.ingest_pdf` (yükleme, toplu yükleme ve `rescan` hepsi oradan
geçer) + `evobulut_sync._download_pdf` (o PDF'ler watchdog'un görmediği
`evobulut/` alt klasörüne indiği için ingest'ten geçmez). Birikmişler için
`POST /invoices/compress-existing`.

**Haftalık yedek sabit saatte alınır, açılışta gecikme telafi edilir.**
Eskiden `interval, weeks=1` kullanılıyordu; bu, ilk çalışmayı açılıştan bir
hafta *sonraya* koyuyor ve Railway her deploy'da süreci yeniden başlattığı
için sayaç sürekli sıfırlanıyordu. Haftada birden sık deploy edildiğinde
yedek **hiç alınmıyordu** — canlıda görüldü (17.08.2026: `size-report` →
`yerel_yedek_sayisi: 0`; dış depo kurulmuştu ama kopyalayacak bir şey yoktu).
Şimdi her pazar 03:00 cron'u var, ayrıca açılışta diskteki en yeni yedeğe
bakılıp 7 günden eskiyse iki dakika sonrasına tek seferlik telafi işi
konuyor. Ölçü bellekteki sayaç değil **diskteki dosya** olduğu için süreç kaç
kez yeniden başlarsa başlasın fazladan yedek alınmaz. Telafi tarihi
**saat dilimi bilinçli** üretilmeli: zamanlayıcı Europe/Istanbul'da, container
UTC; naive tarih üç saat geçmişe düşüp işi tam açılış anında tetikliyordu.

**Vektör indeksi yedeğin en büyük kalemi ve sıkıştırılamıyor.** Canlı ölçüm
(17.08.2026): 205 MB'lık verinin 127.51'i `vectorstore`, bunun 92.82'si
`chroma.sqlite3`, 33.63'ü HNSW `data_level0.bin`. İlk hipotez "Chroma'nın
budanmayan yazma günlüğü" idi ve **yanlış çıktı**: `embeddings_queue` boş,
çünkü 0.5.15 sıfırdan kurulan sistemlerde `automatically_purge`'ü zaten açık
başlatıyor. Tablo kırılımı (yerel, 6000 parça) yeri kimin kapladığını
gösteriyor: 28.1 MB'ın 23'ü `embedding_metadata` + `embedding_fulltext_search_*`,
yani parça metinleri ve hiç kullanmadığımız tam metin arama indeksi. Bunlar
gerçek veri; `POST /assistant/vacuum-index` yalnızca boş sayfaları geri verir
(~%14).

**Bu yüzden vektör indeksi yedeğe konmuyor** (`backup.FOLDER_ARCNAMES` içinde
yok). Tamamı klinik PDF'lerden türetiliyor; yedeklemek, zaten yedeklenen
veriden üretilen bir şeyi 20 kopya taşımak olurdu. Karşılığında geri yükleme
onu kurmak zorunda ve burada iki tuzak var: (1) `reindex_all(force=True)`
şart — normal çağrı veritabanı kaydına bakıp "zaten indeksli" der, kayıtlar
da yedekten geldiği için dosyalar indeksli görünür ama vektör yoktur;
(2) dizin önce **silinir**, yoksa geri yüklenen veriyle ilgisi olmayan eski
parçalar indekste kalır. Üretim dakikalar sürebildiği için arka planda
çalışır: `restore` yanıtı `vektor_indeksi_yeniden_uretiliyor` döner ve
`GET /backups/restore-status` ilerlemeyi gösterir — arka plan işini görünür
kılmazsak "geri yükleme tamam" denip asistan sessizce boş kalırdı. Eski
yedeklerde indeks varsa (bkz. `LEGACY_ARCNAMES`) o kullanılır.

**Yedekte kazanılan yer katlanarak sayılır**: her .zip *tüm* yüklenen
dosyaları içeriyor ve yerelde `BACKUP_KEEP_COUNT` (8), dış depoda
`BACKUP_S3_KEEP_COUNT` (12) kopya tutuluyor — yani tek dosyada kazanılan
megabayt yirmiyle çarpılıyor. Neyin baskın olduğunu tahmin etmeyin:
`GET /backups/size-report` klasör kırılımını, sıkıştırılmamış toplamı ve son
yedeğin gerçek boyutunu döner. (Zip'in kendi DEFLATE'i PDF/JPEG için hiçbir
şey kazandırmaz — dosyaların içi zaten sıkıştırılmış.)

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

**SQLite'ın `lower()`'ı yalnızca ASCII, bu yüzden `ilike` Türkçe'de
yanlış çalışıyordu.** SQLAlchemy `ilike`'ı `lower(sutun) LIKE lower(?)` olarak
derliyor ve SQLite "Ü", "İ", "Ş"yi küçültmüyor: "düz" araması yalnızca
Title-Case yazılmış ürünleri, "DÜZ" araması yalnızca BÜYÜK yazılmışları
buluyordu (canlıda "ürün araması çalışmıyor" olarak bildirildi). Çözüm tek
noktada: `database.py` bağlantı açılırken SQLite'ın `lower()` fonksiyonunu
Türkçe bilen bir sürümle değiştiriyor, böylece `ilike` kullanan tüm aramalar
(ürün, stok, fatura) tek seferde düzeliyor — SQL'de `lower()` başka hiçbir
yerde kullanılmıyor, davranış değişikliği aramayla sınırlı. Fonksiyon ayrıca
diyakritikleri sadeleştiriyor ("duz vaskuler" → "Düz Vasküler"): saha ekibi
telefondan çoğunlukla Türkçe karakter yazmıyor. Python'un kendi `str.lower()`'ı
burada YETMEZ — "İ".lower() araya birleşen bir nokta karakteri koyar ve
"medipol" ile "MEDİPOL" eşleşmez.

**Alt sekme çubuğunun yüksekliğine güvenli alan payı elle eklenir.**
React Navigation'da `tabBarStyle.height` bir sayıysa o değer TOPLAM yükseklik
sayılıyor ve alt çentik payı üstüne eklenmiyor (`BottomTabBar.js`: `customHeight`
varsa inset atlanıyor), ama çubuk yine içeriden `insets.bottom` kadar padding
uyguluyor. iPhone'da 34px'lik ana ekran çubuğu 64px'lik sekme sırasının
içinden yiyor ve etiketler alttan kesiliyordu. `useSafeAreaInsets()` ile
`height: 64 + insets.bottom` veriliyor.

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
| `BACKUP_S3_ENDPOINT/BUCKET/ACCESS_KEY/SECRET_KEY` | Yedeklerin dış depo kopyası; boşsa yedek yalnızca Railway diskinde kalır |

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
- `POST /assistant/vacuum-index` (vektör veritabanında VACUUM; kazanç ~%14)
- `POST /assistant/documents/compress-existing` (klinik PDF'leri küçültür ve
  kayıttaki boyutu günceller — güncellenmezse `_already_indexed` dosyayı
  değişmiş sanıp her açılışta tüm külliyatı yeniden gömer)
- `POST /invoices/compress-existing` (birikmiş fatura PDF'lerini küçültür;
  `taranan_pdf` > `islenen_pdf` normaldir — metin tabanlı e-faturalarda kazanç
  eşiğin altında kalır ve dosyaya dokunulmaz)
- `GET /backups/size-report` (neyin ne kadar yer kapladığı; `yedege_dahil`
  alanı klasörün yedeğe girip girmediğini söyler — sıkıştırmayı doğru yere
  uygulamak için önce buna bakın)
- `GET /backups/restore-status` (geri yüklemeden sonra vektör indeksinin
  yeniden üretimi sürüyor mu; sürerken asistan doküman bulamaz)
- `GET /backups/offsite/status` (dış depoya erişimi sınar), `GET /backups/offsite`
  (uzaktaki kopyalar), `POST /backups/{dosya}/offsite-upload` (elle gönderir),
  `POST /backups/offsite/{dosya}/pull` (uzaktaki kopyayı geri indirir),
  `POST /backups/upload` (elde tutulan .zip'i sisteme koyar)

## Açık işler

- (şimdilik boş)
