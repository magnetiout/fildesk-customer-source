# FilDesk HTTPS indirme entegrasyonu — 16 Kasım güncellemesi

Güncel web/handler sözleşmesi `release-contract.mjs` ve `.d.mts` içindedir.
Schema2, Customer/production, `1.5.0+77` biçimi, açık unsigned karar referansı,
source/evidence hash'leri ve gerçekten kabul edilmiş OS listesi gerekir.
`release.example.json` bilinçli olarak approved=false kalır.

Final metadata yalnız `scripts/prepare-public-download.py --output <yeni-dosya>
--tested-system "Windows 11 x64"` ile hazırlanır. Araç önce mevcut tam
`release-gate.py`yi ve distribution doğrulamasını çalıştırır; eksik kanıtta
dosya üretmez. OS seçeneği gerçek test kaydından verilir. Web schema kontrolü
insan testinin gerçekliğini veya imzayı tek başına kanıtlamaz.

Public dosya adı `FilDesk-Destek-Windows.exe`; unsigned URL
`https://filteknoloji.com/downloads/fildesk/releases/<version>/FilDesk-Destek-Windows.exe`;
build numarası URL'de `+77` yerine `-77` olur. Kaynak aynı release altında
`source/FilDesk-Corresponding-Source.tar.gz` olur. Diskte payload hâlâ
`<release-directory>/<sha256>/FilDesk.exe` olarak hash ile saklanır.
Dosya adı değişikliği yeniden derleme/imza yapmaz; bytes/hash aynı tutulur.

SSR component aynı sözleşmeyi kullanır; unsigned modda verified publisher
göstermez. Yeni unsigned manifest desteklenir; development/unsigned-test,
Operator, eksik source/onay veya hatalı metadata reddedilir. Exporter şu an
unsigned adaptörüdür; eski signed gate'in farklı URL sözleşmesi ayrıca
uzlaştırılmadan signed dosya bu yeni manifest üreticisine geçirilmez.

Testler: `node --test integration/distribution/download.test.mjs`;
`integration/nextjs` içinde `npm run typecheck` ve `npm test`.
Bu kontroller gerçek tarayıcı veya iki-PC kabulü değildir. Route örneği mevcut
siteye uyarlanıp staging'de sınanmalıdır. Canlı deploy bu dosyayla yapılmaz.

## Önceki signed-only tasarım — tarihsel

Yalnız /home/kadir/rust içinde hazırlanmıştır; canlı site, Nginx, PM2, DB veya DNS'e dokunulmaz.
`download.mjs` test edilmiş server-only HTTP referansıdır; `route.example.ts` Next App Router
sarmalayıcısıdır. Yerel örnek manifest approved=false olduğu için503 döner.
Mevcut Next.js indirme component'i artık unsigned public release'i reddeder.

## Yayın akışı

- İmzalama ve gerçek kabul sonrası `python3 scripts/release-gate.py` başarı vermeli.
- Windows imza kanıtından gerçek publisher/signatureStatus, final bytes/SHA256 ve kaynak
  erişim URL'siyle manifest üretilir. `approved=true` bir imza doğrulaması değildir;
  yalnız bütün gate/kanıtlar sonrası yetkili release sürecinin verdiği yayın kararıdır.
- Dosya public webroot dışında, yazımı tamamlanmış salt okunur
  `<release-directory>/<sha256>/FilRemote.exe` nesnesinde tutulur. Hash dizini/nesnesi
  varsa farklı bytes ile üzerine yazmak reddedilir. Yetkili deploy aşamasında object-lock
  veya readonly storage politikası uygulanır; bu görevde storage kurulmadı.
- İndirme URL'si `/downloads/fil-remote/<sha256>/FilRemote.exe`; tarayıcı dosya adı
  Content-Disposition ile FilRemote.exe olur. MIME application/octet-stream;
  X-Content-Type-Options nosniff, Content-Length, SHA256 ETag ve immutable cache verilir.
- DNS/HTTPS sertifikası doğru filteknoloji.com origin'i için site sahibi tarafından sağlanır.
  HTTP'den yalnız HTTPS'e yönlendirme yapılabilir; HTTPS'ten HTTP'ye downgrade yok.
  Proxy request.url'yi doğru HTTPS olarak oluşturmalı; istemcinin kontrolündeki
  X-Forwarded-Proto'ya koşulsuz güvenerek kontrol bypass edilmez.
- Stable indirme düğmesi onaylı hash URL'sini gösterir. `latest.json` kullanılırsa no-store;
  alias redirect kullanılırsa307/no-store. Değişmez nesne URL'sinin içeriği değiştirilmez.
- Rollback yalnız daha önce onaylanmış, hâlâ güvenli imzalı sürümün manifestine atomik
  pointer değişimidir. Revoke edilmiş/açığı bulunan eski sürüme sessiz rollback yok.
- PE download bytes CDN transform/compression/HTML-challenge ile değiştirilmez. HTTPS
  imza yerine geçmez; hash manifesti de tek başına publisher doğrulaması değildir.

Dosya okuması bu referansta hash kontrolünden sonra tamamı buffer'dan sunulur;256MiB
üstü manifest reddedilir. Büyük trafik için aynı immutable nesneyi hash doğrulamasıyla
staging'de kabul edip object storage/CDN'den sunmak gerekir. Range/resume bu örnekte yok;
isteğe tam200 yanıt verir. Proxy/CDN/gerçek Next route entegrasyonu henüz NOT RUN.

`release.example.json` boş alanları tahminle doldurmayın. İlk yayın önkoşulları:
production sunucu bilgisi, güvenilir imzalama, launcher trust hardening,15 RustSec,
Opus CRT, dört tarayıcı Windows kabulü, gerçek operatör E2E ve kaynak/lisans erişimi.
İmzasız development EXE'yi halka açık indirme düğmesine bağlamayın.

Test: pinned Node image ile `node --test integration/distribution/download.test.mjs`.
Bu testler sentetik bytes/metadata kullanır; HTTPS deployment, Authenticode veya gerçek
tarayıcı testi değildir. Bir Next projesine kopyalanmadan import path/type uyarlaması
ve staging'de TLS/header/download kabulü yapılmalıdır.
