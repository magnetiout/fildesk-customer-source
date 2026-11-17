# Upstream seçimi

2026-10-12 GitHub API sorgusunda yayımlanmış kararlı client 1.5.0 (2026-09-30), server 1.1.16 (2026-07-20) seçildi. Nightly/master seçilmedi. Etiket bilgileri `reports/*-releases-latest.json`, kimlikler `config/upstream.lock.json` içinde.

| Kaynak | Commit |
|---|---|
| rustdesk/rustdesk 1.5.0 | fada664df7a294d1d1a9ca3e7cd3637069122f17 |
| client hbb_common | 229b904508364c8997aad0fb5af57effac859f60 |
| rustdesk/rustdesk-server 1.1.16 | 73523b31cfd25d77dee862e6fc9f5e1fb5e485ef |
| server hbb_common | 83419b6549636ee39dacef7776c473f5802e08d6 |

Her repo `upstream` remote ve `fil/v0.1.0-dev` yerel dalını korur. Başka hesaba fork açılmadı. Repo sahibi/organizasyon belirli değil, gh yok. Root kaynak hazırlama aracı sabit etiketin SHA'sını doğrular, recursive submodule'leri alır, kaydedilen patch'leri uygular. Yerel Fil commit'leri upstream'de bulunmaz; bunları upstream URL'sinden fetch etmeye çalışmayın.

İki hbb_common sürümü farklıdır. Rendezvous protobuf alan numaraları ve hbbs/hbbr akışı incelendi; gerçek wire testleri sunucu sürümüyle yapıldı. Bu inceleme Windows 1.5.0 ↔ 1.1.16 uçtan uca uyumluluk sertifikası değildir. Yayın öncesi gerçek iki uç testi şarttır.

Resmî repository security-advisories API sonuçları boş listeydi; bu güvenlik açığı yok anlamına gelmez. RustSec lockfile denetimi ayrı raporlanır. Dondurulan upstream güvenli kabul edilip halka dağıtılmamalıdır; ilgili açıklar triage edilmelidir.

Kaynaklar: https://github.com/rustdesk/rustdesk/releases/tag/1.5.0 ; https://github.com/rustdesk/rustdesk-server/releases/tag/1.1.16 ; her iki repository'nin LICENSE/LICENCE ve workflow kaynakları.
