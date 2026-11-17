# FilDesk Customer — yayımlanmış kaynak kodları

Fil Teknoloji'nin **1.5.0+77 Windows portable Customer** sürümünün seçilmiş
uygulama ve derleme kaynaklarıdır. FilDesk, RustDesk açık kaynak kodundan türetilmiştir.
Bu depo RustDesk'in resmî deposu veya RustDesk Server Pro dağıtımı değildir.

## İndirme ve sürüm kimliği

- [FilDesk destek sayfası](https://filteknoloji.com/uzak-destek)
- [Windows Customer EXE](https://filteknoloji.com/downloads/fildesk/releases/1.5.0-77/FilDesk-Destek-Windows.exe)
- EXE boyutu: **24.320.512 bayt**.
- EXE SHA-256: `23f95978b4de73c1d59b7f978f44f06ed77bbd3a282fd3816e4594183a487a68`.
- [Tam karşılık gelen kaynak/bağımlılık/lisans arşivi](https://filteknoloji.com/downloads/fildesk/releases/1.5.0-77/source/FilDesk-Corresponding-Source.tar.gz)
- Tam arşiv boyutu: **1.115.622.877 bayt**.
- Tam arşiv SHA-256: `5ec7467b7eb9914d88857aeb37d46ff287da47ff9065da9e6f3420ec6f6ce850`.

Bu kimlikler yayımlanmış v77 dosyalarını belirtir. Farklı dosya veya imzalanmış
gelecek sürüm aynı hash'e sahip olmaz. Yeni sürüm yeni kimlik ve URL almalıdır.

## Depo yapısı ve kapsamı

| Konum | İçerik |
|---|---|
| `source/client/` | Customer'ın kullandığı ortak Rust/Flutter istemci kaynakları |
| `source/root/` | Eşleşen seçilmiş derleme betikleri, yapılandırma ve bildirimler |
| `PUBLIC-SOURCE-IDENTITY.json` | Seçilen 2.088 dosyanın yayımlanmış manifestteki SHA-256 kimlikleri |
| `LICENSE`, `NOTICE` | Lisans metni ve üst proje bildirimi; alt dizin bildirimleri de geçerlidir |

Seçilmiş 2.088 dosya tam arşivin `SOURCE-MANIFEST.json` envanteriyle bayt bayt
karşılaştırılmıştır. Bu küçük depo bütün motor/üçüncü taraf bağımlılık kaynaklarını
vendörlemez; **tam Corresponding Source için yukarıdaki tam arşivi kullanın**.
Özel git geçmişi, özel CI bundle'ları, üretim kimlik bilgileri ve Operator EXE'si
bu depoda dağıtılmaz. Ortak istemci ağacında Operator rolüyle ilgili kaynak kod
bulunur; yalnız Customer'a ait bağımsız bir kod tabanı olduğu iddia edilmez.

## Kaynağı inceleme ve derleme

1. İlgili sürümün tam kaynak arşivini indirin ve SHA-256 değerini doğrulayın.
2. Arşivdeki README, kaynak tabanı açıklamaları ve manifesti okuyun. Seçilmiş
   kaynaklar ile sabitlenmiş motor/bağımlılık girdilerini birlikte kullanın.
3. Customer profilini ve eşleşen sürüm/derleme girdilerini seçin. Tarihsel bir
   bootstrap betiğini bu kaynakların üzerine çalıştırarak eski girdileri geri
   yüklemeyin. Bu depodaki eski platform yolları taşınabilir kurulum garantisi değildir.
4. Kendi ortamınızda belirtilen bağımlılıkları ve araç zincirini hazırlayın;
   kaynak incelemesi, testler ve yerel kullanıcı onaylı fiziksel kabulü ayrı ölçün.
   Bu depo otomatik CI kurulumu veya yeniden üretilebilir bit düzeyi derleme
   garantisi sunmaz.

Windows'ta indirilen dosyanın kimliğini doğrulamak için:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\FilDesk-Destek-Windows.exe'
```

Hash eşleşmesi yalnız yayımlanan dosyayla aynı baytları doğrular; güvenlik
sertifikası veya Windows yayımlayıcı doğrulaması değildir.

## Güvenlik ve kullanım sınırları

Mevcut v77 EXE **dijital olarak imzasızdır**. Windows/tarayıcı güvenlik uyarısı
gösterebilir; Smart App Control çalıştırmayı engelleyebilir. Kaynağın açık olması
veya antivirüs taramasının olumlu sonucu Windows yayımlayıcı güveni oluşturmaz,
gelecekteki tehditleri dışlamaz ve güvenlik garantisi değildir. Korumaları
kapatmak veya UAC'yi atlatmak bu projenin önerdiği çözüm değildir.

Uzaktan destek yalnız yetkili ve rızası olan cihazlarda kullanılmalıdır.
Geçici parola, müşteri onayı ve yerel Windows yönetici onayı akışlarını koruyun.
Üretim parolası, token, özel anahtar, geçici FilDesk parolası veya kişisel tanı
kaydını public issue'ya eklemeyin. Kullanıcı desteği için
[Fil Teknoloji iletişim sayfasını](https://filteknoloji.com/iletisim) kullanın.

## Lisans ve üçüncü taraf hakları

GNU Affero General Public License v3 metni için [LICENSE](LICENSE) ve istemci
lisansı için [source/client/LICENCE](source/client/LICENCE) dosyasına bakın.
RustDesk ve üçüncü taraf telif/lisans bildirimleri korunmuştur. Alt bileşenler
kendi lisanslarını taşıyabilir; yalnız kök LICENSE'a bakarak bütün bağımlılıkların
aynı lisansa sahip olduğunu varsaymayın. Tam kaynak arşivi ilgili kaynakları ve
bildirimleri birlikte sunar. Yeniden dağıtım ve değişikliklerde ilgili lisansın
kaynak sağlama, bildirim ve diğer koşullarını yerine getirin.

FilDesk/Fil Teknoloji markaları veya RustDesk markası için lisans metninden
bağımsız marka izni verilmiş sayılmaz. `NOTICE` ve kaynak içindeki tarihsel
belgeler korunmuştur; tarihsel geliştirme/pending kayıtları güncel yayın durumu
veya bütün platformlar için kabul garantisi olarak okunmamalıdır.

## English summary

This repository contains the exact selected application/build source already
published for FilDesk portable Customer 1.5.0+77. All 2,088 selected files match
the complete corresponding-source inventory. Shared client source includes
role-specific Operator code, but no Operator executable or private repository
history is distributed. Download the complete source archive linked above for
engine/dependency sources, build inputs and notices. Preserve the AGPL-3.0 and
third-party notices. The current executable is unsigned; source availability,
hash matching and antivirus results are not a guarantee of safety or publisher trust.
