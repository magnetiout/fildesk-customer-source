> Güncel transparan/tema rafinesi: [logo_polish.md](logo_polish.md); yeni Windows adayı ve SCP: [logo_polish_windows_test.md](logo_polish_windows_test.md). Aşağıdaki beyaz plaka ve önceki run bilgileri tarihsel sürüme aittir.

# Güncel resmî logo

Fil Teknoloji ana sayfasındaki gerçek SVG artık kullanılıyor. Kaynak, varyantlar ve üretim: [official_logo.md](official_logo.md). Önceki FD/placeholder notları aşağıda tarihsel kayıt olarak tutulur; güncel adayda geçerli değildir.

## FilDesk GUI düzeltmesi

Client fce845ee3: ana ekranda FilDesk / Fil Teknoloji ve ortak FD geçici ürün işareti kullanılır. Eksik Flutter assets/icon.png eklendi; tab/tray SVG fallback tutarsızlığı giderildi. Native ICO, launcher, Flutter PNG aynı özgün FD kaynağına dayanır. Onaylı gerçek şirket logosu hâlâ gerekli; başka şirket/proje görseli alınmadı. RustDesk OSS/AGPL/telif/kaynak Hakkında ve dağıtım bildirimlerinde korunur. Gerçek Windows shell/tray kabulü NOT RUN; PNG/ICO byte doğrulaması görsel kabul değildir.

# Güncel marka: FilDesk

Ürün adı FilDesk, yayıncı metni Fil Teknoloji; profil etiketleri FilDesk Customer/FilDesk Operator. İki portable indirme de FilDesk.exe. Özgün FD monogramı scripts/brand-assets.py ile üretilir; şirketin onaylı kurumsal logosu olduğu iddia edilmez. Windows/tray/Flutter assetleri aynı FD kaynağındandır. RustDesk AGPL/telif bildirimleri korunur. AppData/service kimliği ve veri koruma: [geçiş](fildesk_migration.md). Eski GitHub repository/branch adları teknik izlenebilirlik için değişmez.

## Önceki markalama notları — tarihsel

# Markalama

Fil Remote başlık/metin, Fil Teknoloji atfı, sade açık yüzeyli upstream Flutter GUI. Ana sayfa merkezinde ID, 10 karakter geçici parola ve yenileme; müşteri profili uzak ID panelini gizler. Operatör mevcut bağlantı panelini kullanır. Türkçe varsayılandır; upstream diller korunur, eklenen Fil metinleri V1'de Türkçedir.

`branding/assets/fil-remote-placeholder.svg` özgün geometrik F monogramıdır; kurumsal onay gerektirir. `scripts/brand-assets.py` aynı geometriden PNG/çok çözünürlüklü ICO üretir. Windows app/tray/resource ikonları değiştirilir; Hakkında RustDesk telif ve AGPL atfı korunur. Marka onayı/Windows görsel QA: NOT RUN.

APP_NAME: development `Fil Remote Dev`, operator `Fil Remote Dev Operator`; production `Fil Remote` / `Fil Remote Operator`. Veri dizinleri ayrıdır. EXE dış adı FilRemote.exe; native engine DLL adı librustdesk.dll korunur. Ürün metadata 0.1.0-dev; protokol uyumluluğu için upstream uygulama sürümü 1.5.0 kalır.

Müşteri portable uygulamasındaki upstream Install akışı açıktır. Teknik uygulama/servis/ARP kimliği `FilRemote-Dev` (production `FilRemote`), operatör son eki `-Operator`; Windows installer yalnız ASCII harf/rakam/tire kabul ettiği için boşluk kullanılmaz. Ana GUI ürün başlığı Fil Remote kalır. ARP Publisher kaynağı Fil Teknoloji olarak ayarlandı. Kurulum/kaldırma ve servis Windows üzerinde NOT RUN. Ayrı MSI paketi üretilmedi; MSI yayını ayrıca UpgradeCode ve test gerektirir. CompanyName metadata'sı Authenticode Publisher doğrulaması değildir.

Patch'ler tek yerde `branding/patches/` altında; geri alınabilir ve sabit upstream'e uygulanır. `fil_build_config.rs` public build çıktısıdır; kaynak paketinde çalışmayan şablon bulunur, yayın config'i açıkça verilmelidir.

Son izin sertleştirmesi: access-mode=custom sabittir; full erişim modu per-feature kısıtları aşamaz. Privacy mode, block-input, kamera, remote restart ve kayıt izni kapalıdır. Böylece yerel ekran/girdi görünürlüğü hedefi korunur; gerçek Windows gözlemi hâlâ gereklidir.
