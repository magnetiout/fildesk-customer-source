# Güvenlik kararları ve yayın engelleri

Ürün görünür uzaktan destek içindir. Kullanıcı uygulamayı açar, yetkili operatöre ID/geçici parola verir, görünür bağlantı penceresinden oturumu sonlandırır. Üçüncü kişiye parola paylaşma uyarısı UI ve indirme sayfasındadır. Habersiz kurulum/persistence/güvenlik ürünü bypass yoktur.

## Uygulanan politika
- Müşteri: `verification-method=use-both-passwords` değiştirilebilir varsayılan; 10 karakter geçici parola ve kullanıcının açıkça oluşturacağı kalıcı parola desteklenir. Başlangıçta kalıcı parola yoktur; ortak/gömülü parola yoktur. Operatör geçici parola politikası korunur. Kalıcı parola upstream saklama/doğrulama işlevlerini kullanır.
- `approve-mode=password`: parole ile doğrulama. Upstream password-click/Both, parola VE tıklama değil, alternatif yöntemlerdir. V1 çift faktörlü yerel onay iddia etmez. Bilgiyi bilinçli paylaşma kullanıcı rızası akışıdır.
- Upstream thread_rng ile parola üretimi ve bağlantı rate limit'leri korunur. Upstream src/server/connection.rs başarılı yetkilendirmede geçici parolayı döndürür; reconnect session cache davranışı ayrıca Windows'ta test edilmelidir.
- `allow-hide-cm=N`; tray/izin/sonlandırma görünürlüğü korunur. Müşteri X kapatma yolu bağlantıları kapatıp UI uygulamasından çıkar; açık rızayla kurulmuş servis çalışmayı sürdürebilir. Ana ekran bu durumu açıklar; Ayarlar > Genel hizmet durdurma ve kaldırma yolları korunur. Windows process/service testi henüz yapılmadı.
- Müşteride dosya/pano Y, ses N; yerel kullanıcı değiştirebilir. Görünür Windows kurulum/servis desteği açık; kendiliğinden kurulum yok. Operatörde dosya/pano/ses N ve kurulum kapalı. Terminal/tunnel/direct-IP/LAN discovery, hesap ve adres defteri kapalı. Güvenlik/oturum izin ayarları gizlenmez.
- Ağ/key build-time sabittir; filename ile override önlenir. Pro API register-device=N; upstream update kontrolü kapalı; sunucu update HTTP isteği kaldırıldı. Yeni telemetry eklenmedi. Tüm olası upstream egress yollarının dinamik ağ gözlemi NOT RUN.
- TLS insecure fallback N; peer şifreleme ve doğrulama protokolüne müdahale edilmedi. Server private key sadece data volume içinde 0600; public key dağıtılabilir. Public key bir kullanıcı parolası değildir; key possession müşteri operatör kimliği anlamına gelmez.

## Sunucu
Non-root, read-only rootfs, cap_drop ALL, no-new-privileges, PID/CPU/RAM/swap limitleri, küçük tmpfs, 5 MiB × 3 log/container. hbbs/hbbr ortak key volume'u erişimi kısıtlıdır. 21118/21119 publish edilmez. Runtime loopback test; internetten erişim testi yoktur.

Protokol relay probu açık test baytlarını taşır: istemci uçtan uca şifreleme testi değildir. Kaynak lockfile taramasında bulunan açıklar `reports/security_results.md` içinde; sürüm kararlı diye güvenli varsayılmadı. Tarama bulguları triage/onarım ve regresyon testi bitmeden production'a çıkmayın.

## Authenticode
Sertifika yok, dosya varsa unsigned-test olarak etiketlenir. CompanyName ile imza Publisher farklıdır. Kurumsal OV/EV CA veya uygun bölge/kuruluş şartlarında Microsoft Artifact Signing değerlendirilebilir. Özel anahtar HSM/sertifika sağlayıcısında tutulmalı; Git/secrets dökümü içine yazılmamalı. İleride korumalı release environment, kısa ömürlü kimlik, SHA256 digest, RFC3161 timestamp ve `signtool verify /pa /all /v` kontrolü eklenir. İmza EXE/DLL'lerde paketlemeden önce, dış portable EXE'de paketlemeden sonra uygulanmalıdır. Untrusted PR'lara signing erişimi verilmez.

OV/EV veya imza SmartScreen itibarını garanti etmez; Defender/SmartScreen/UAC kapatılmaz. Microsoft kaynağı: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation ; https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options .

## KVKK / veri minimizasyonu
ID, IP, bağlantı zamanı ve gerekli operasyon metadatası kişisel veri olabilir. Ekran/dosya/pano içeriği destek sırasında işlenebilir; kaydetme varsayılan kapalı. Parola ve müşteri ekranı loglanmamalıdır. Upstream logları IP/ID içerebilir; prod düşük log seviyesi, yetkili erişim, belgelenmiş kısa saklama ve silme politikası gerektirir.

Fil Teknoloji veri sorumlusu/işleyen rolleri, aydınlatma, hukuki işleme şartı, operatör yetkilendirmesi ve sözleşmeleri hukuk danışmanıyla belirlemelidir. Singapur VPS ile yurt dışına aktarım; şifreleme tek başına hukuki istisna değildir. Güncel KVKK md.9 mekanizmaları ve varsa standart sözleşme/bildirim yükümlülükleri değerlendirilmelidir. Hukuki uyumluluk PASS değildir.

Resmî kaynak: https://www.kvkk.gov.tr/Icerik/8142/Kisisel-Verilerin-Yurt-Disina-Aktarilmasi-Rehberi ; https://www.kvkk.gov.tr/Icerik/7938/Standart-Sozlesmeler-ve-Baglayici-Sirket-Kurallarina-Iliskin-Dokumanlar-Hakkinda-Kamuoyu-Duyurusu .

Son izin sertleştirmesi: access-mode=custom sabittir; full erişim modu per-feature kısıtları aşamaz. Privacy mode, block-input, kamera, remote restart ve kayıt izni kapalıdır. Böylece yerel ekran/girdi görünürlüğü hedefi korunur; gerçek Windows gözlemi hâlâ gereklidir.
