# Lisans ve kaynak kod erişimi

Client `LICENCE`, server `LICENSE`: GNU AGPL v3 metni. Mevcut telif bildirimleri korunur. Root eklemeleri aynı AGPL v3 kapsamında dağıtım hazırlığıdır. `libs/` ve bağımlılıklar kendi lisanslarını korur. Bu çalışma hukuki uygunluk onayı değildir.

Değiştirilmiş binary dağıtılırken ilgili tam kaynak, build script'leri, patch'ler, lockfile'lar ve gereken bağımlılık kaynakları sağlanmalıdır. AGPL §13 ağ üzerinden kullanılan değiştirilmiş yazılımda da kullanıcıya kaynak erişimi gerektirebilir. Sadece upstream linki, değişikliklerimizi kapsamaz. Lisans/telif metnini silmeyin; değişiklik ve tarih bilgisini koruyun.

`scripts/package-release.sh` proje ile iki kaynak ağacını ve submodule içeriklerini paketler; özel anahtar/veri/cache dahil edilmez. Bu arşiv üçüncü taraf tüm transitif bağımlılık kaynaklarını kendiliğinden vendor etmez. Tam Corresponding Source yayını için cargo vendor, Flutter pub/git paketleri, vcpkg portları/kaynakları, custom Flutter engine kaynak ve build talimatlarını da sürüm ile eşleştirip erişilebilir tutmak gerekir. Bu kalem doğrulanmadan halka binary sunulmaz.

Yayın kapısı: sürüme ait çalışan HTTPS kaynak indirme adresi, lisanslar ve bağımlılık notice listesi indirme sayfasına eklenmeli; uygulama Hakkında ekranına aynı kaynak erişimi bağlanmalıdır. Henüz onaylanmış/çalışan Fil kaynak URL'si yok; uydurulmadı. Test binary'si paylaşılırken dahi ilgili kaynak ve lisans dosyası birlikte verilmeli.

Fil Remote adı/özgün geçici monogram Fil markalama alanıdır; onaylı şirket logosu değildir. RustDesk ticari markası sahiplik iddiasıyla kullanılmaz. RustDesk OSS atfı korunur. AGPL telif izni, ticari marka izni veya Server Pro kodunu kopyalama yetkisi sağlamaz. Pro bileşen alınmadı, Pro imza/lisans kontrolü kırılmadı.

Kaynaklar: https://www.gnu.org/licenses/agpl-3.0.html ; https://www.gnu.org/licenses/gpl-faq.en.html ; upstream lisans dosyaları. Hukuk danışmanı dağıtım biçimi ve kaynak sunumunu incelemelidir.

## Current private successor: 1.5.0+77

The exact73 functional baseline is retained with a minimal crypto remediation,
independently licensed native helper replacements and display metadata corrections.
`FilDesk76-Corresponding-Source-Base.zip` (unchanged dependency/source base) AND
`FilDesk77-Source-and-Build-Supplement.zip` (full77 application/build source)
accompany the private Customer/Operator pair.
`LICENSES/SOURCE-AVAILABILITY-77.txt` and the release MANIFEST identify both required
archives and their hashes. Provide both to recipients together with the complete notices; a bare upstream
link is not a substitute. Public source/download URLs remain inactive until final
Windows build, physical acceptance and explicit publication approval.

Unsigned distribution is the owner's approved mode; see
[unsigned-release-policy.md](unsigned-release-policy.md). This changes signing
policy only. It does not waive source, third-party rights, artifact integrity,
security review or Windows acceptance.
