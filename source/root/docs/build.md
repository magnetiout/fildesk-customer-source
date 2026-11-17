# Derleme

## Kaynak ve izole Linux build
`config/upstream.lock.json` sabit SHA'ları, `branding/patches/` Fil değişikliklerini içerir. Yeni checkout: `python3 scripts/bootstrap-sources.py`. Var olan ağacı otomatik ezmez. `scripts/build-linux.sh` Docker içinde Rust 1.90.0/bookworm image digest'i, `cargo build --locked --release --bin hbbs --bin hbbr`, 2 job/2 CPU/6 GiB/no extra swap ile çalışır. Host'a paket veya Rust kurulmadı. Upstream build.rs src/version.rs yazdığı için yalnız proje server dizini writable bağlanır; ilk read-only denemesi hatası loglanmıştır. SQLx compile sırasında örnek DB dosyasını değiştirebilir; release patch'ine dahil etmeyin.

Çıktılar: `artifacts/server/hbbs`, `hbbr`, `SHA256SUMS`, `manifest.json`. Bunlar Linux ELF'tir, Windows EXE değildir. Runtime ayrı minimal Debian bookworm-slim digest'i kullanır. `scripts/dev-server.sh build|up|status|down` yalnız Fil projesini yönetir.

## Windows native pipeline
`.github/workflows/fil-remote-windows.yml`: yalnız manuel dispatch, contents:read, secrets yok, checkout credentials saklanmaz, action'lar SHA pinned. Root repo yetkili `magnetiout/fil-remote` private hedefinde yayımlandı ve gerçek run'lar başlatıldı. Güncel sonuç, SHA ve loglar `reports/windows-build-results.md` içindedir.

Dispatch `config_json`: environment/profile/id_server/relay_server/public_key alanları. JSON shell koduna interpolasyonla verilmez; environment üzerinden Python parser'a girer. Bridge job üretimi ardından Windows 2022 x64/MSVC runner müşteri ve operatörü sırayla derler. Build araçları: Python 3.11.9; LLVM 15.0.6; Flutter 3.24.5 (dec2ee5c1f98f8e84a7d5380c05eb8a3d0a81668); vcpkg 9e593bb18ea69cc5095e012465dcd675a822ed0d; cargo-expand 1.0.95; flutter_rust_bridge_codegen 1.80.1; Brotli 1.1.0 SHA doğrulamalı wheel.

Upstream flutter-ci.yml/flutter-tag.yml/flutter-nightly.yml → flutter-build.yml; ayrıca bridge.yml ve third-party-RustDeskTempTopMostWindow.yml incelendi. Upstream x64 Rust 1.75, bridge Flutter 3.22.3 (extended_text 13 downgrade), target Flutter 3.24.5; vcpkg CMake hedefi 4.3.0. Fil akışı Sciter dışarıda olduğu için Rust 1.90.0 ve bridge için aynı Flutter 3.24.5 kullanır; bunlar Windows'ta henüz doğrulanmamış uyarlamalardır. Upstream kilidi 3.24.5 ile enforce-lockfile kontrolünde 16 değişiklik gerektirdi; Fil pubspec.lock bu SDK ile yeniden çözüldü ve yeniden enforce edildi. Diff kaynak patch'inde yer alır.

Visual Studio 2022 C++ desktop workload ve Windows SDK runner image'ından gelir. windows-2022 etiketi tek başına immutable VM değildir; ImageVersion/provenance kaydedilir. Tam hermetik/bit-identical Windows build iddiası yoktur. İleride onaylı runner image snapshot ve OS paket envanteri sabitlenmelidir. CMake/vcpkg tool indirmeleri ilgili pinned vcpkg checksum manifestine tabidir.

Custom Flutter engine upstream resmî zip'ten alınır; `config/windows-engine.lock.json` boyut ve SHA256 sabitler. Mutable main URL değişirse hash mismatch ile durur. Windows 7 kapsam dışı olsa da upstream engine kullanılır. Ek USB/printer driver, NVENC/CUDA/--vram işi yok. TopMost injection DLL'i V1 portable paketine eklenmez; UAC/secure desktop sınırlamaları kabul testinde görünür tutulur.

Yerel Windows makinede tüm araçları hazırlayıp bridge üretildikten sonra:
```powershell
./scripts/build-windows.ps1 -Config config/development-customer.local.json
```
PowerShell 7 gerekir. build.py Flutter/Rust build yapar; native bundle ve tek EXE portable packer üretilir. Paket içine lisans ve kaynak bildirimi eklenir. Çıktılar `artifacts/windows/<environment>/<profile>/` altında olur. Güncel gerçek artefact durumu `reports/windows-build-results.md` ile izlenir.

## Tekrarlanabilirlik ve cache
Cargo.lock, Flutter pubspec.lock, npm package-lock.json, upstream/submodule/action/image pin'leri saklanır. Linux kaynakta upstream tarih üretimi vardır; byte-for-byte determinism doğrulanmadı. Git SHA + patch hash + toolchain + binary hash provenance'dır, bit reproducibility kanıtı değildir. Proje cargo/pub/npm cache'leri `build/` içinde; başka projenin cache'i silinmez. CI bridge artifact 7 gün, test EXE 14 gün; yayın deposu ayrı onaylı retention gerektirir. Private data/key cache'e alınmaz.

`scripts/package-release.sh` dev kaynak/artifact paketi, `scripts/check-artifact.sh` Linux hash/format kontrolü. Üretim imzalama ve güvenlik kapıları `docs/security.md` içinde.

## Yerel Flutter ve politika kontrolleri
`scripts/prepare-linux-tools.sh` yeni proje container'ında gereken paketleri ve pinned rustfmt/codegen'i hazırlar; host apt yoktur. Ubuntu manifest URL'si ilk sorguda 404 döndüğü için SDK resmî Flutter git tag/SHA'sından alındı, engine sürümüne bağlı Dart bootstrap ile çalıştı. Flutter analiz/bridge için CLI telemetry kapalıdır. `scripts/generate-bridge-local.sh`, `scripts/check-flutter.sh`, `scripts/test-client-policy.sh` mevcut isolated toolchain'i kullanır. OS paket listesi `reports/logs/client-tooling-packages.log` içinde; yerel tooling image ID config'te. Apt repository snapshot tam sabitlenmediği için bu araç image'ı hermetik değildir.
Windows çıktı kontrolü `scripts/check-windows-artifact.ps1`: PE32+ AMD64 header, dosya boyutu, manifest SHA256 ve gerçek Authenticode NotSigned durumunu karşılaştırır. Kontrolün gerçek Windows koşum sonucu `reports/windows-build-results.md` içinde ayrıca raporlanır. Upstream engine zip içeriği yerelde incelendi; dosyalar zip kökünden engine dizinine kopyalanır.

## İndirme düzeltmesi (2026-10-12)
Flutter release manifest/archive HTTP404 verdiğinden CI `scripts/setup-flutter.py` ile resmî GitHub 3.24.5 tag'ini alır ve `dec2ee5c1f98f8e84a7d5380c05eb8a3d0a81668` SHA'sını doğrular. Engine-pinned Dart bootstrap korunur. Sürüm değiştirilmedi. Linux source bootstrap ve analiz/test çalıştı; Windows bootstrap/native build sonucu gerçek Actions run kayıtlarında ayrıca izlenir. HTTP kanıtları ve ayrıştırılan nedenler `reports/download_diagnosis.md` içindedir.

## Güvenlik adayını ayrı üretmek
`bash scripts/build-linux.sh --candidate` güncel server kaynaklarını artifacts/server-candidate içine yazar. Mevcut development image/binary'leri değiştirmek için dev-server build/up çalıştırılmadı. `scripts/test-server-security.sh` ve `scripts/test-server-candidate.sh` ayrı test yollarıdır. Windows yetki ve yayın sırası docs/windows_build_readiness.md içinde.

## Windows checkout ve indirme doğrulaması
`.gitattributes` Git binary patch dosyalarını byte-preserving tutar; Windows core.autocrlf=true checkout regresyonu test edilir. Kaynak bootstrap komutları autocrlf=false kullanır. İndirilen iki profile ait portable/bundle EXE’leri `python3 scripts/verify-downloaded-windows.py artifacts/windows/RUN_DIRECTORY --commit ROOT_RUN_SHA --config config/development-customer.local.json` ile yerelde kaynak pinleri, patch/lock hash, PE32+ AMD64, SHA256/boyut ve sertifika tablosu bakımından doğrulanır. Windows GUI/E2E kabulü bu statik kontrolden ayrıdır.

## İmzalama hazırlığı eki

Mevcut unsigned Windows workflow korunur. `scripts/build-windows.ps1` isteğe bağlı
`-SigningConfig` ile ayrı fresh staging içinde imzalı development candidate
paketleyebilir; public selectors/tool hashes için `config/signing.example.json`.
[İmzalama pipeline](signing_pipeline.md) ve [kullanıcı adımları](signing_owner_actions.md).
CA/HSM/Artifact Signing erişimi olmadan bu yol BLOCKED; production release gate
atlanmaz. `.github/workflows/fil-portable-security.yml` manuel Windows kernel,
PE loader policy, embedded signed fixture ve Opus CRT testlerini çalıştırır.
