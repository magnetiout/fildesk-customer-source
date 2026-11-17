#!/usr/bin/env python3
"""Preserve baseline and report every advisory; never creates an audit exception."""
import ast,hashlib,json,pathlib,re,subprocess
R=pathlib.Path(__file__).resolve().parents[1]
notes={
'crossbeam-channel':('Yüksek (bellek güvenliği)','Kanalların Drop yarış durumu; thread/mesaj yolları potansiyel erişim. Semver uyumlu 0.5.15.'),
'idna':('Yüksek (koşullu isim kontrolü)','URL/host normalizasyonu; sabit endpoint riski azaltır fakat bütün çağrılar kapalı değil. url2.5.4/idna1.1.'),
'libgit2-sys':('Yüksek','Linux keepawake → build dependency shadow-rs → git2. Normal Windows çalışma yolu değil; build girdileri etkilenebilir. keepawake/shadow-rs yükseltmesi ve Linux build regresyonu gerekir.'),
'openssl':('Yüksek (koşullu UAF)','Native TLS/derleme zinciri; fetch(properties) ve select_next_proto özel çağrı koşulları. openssl0.10.72 ile düzeltildi; C OpenSSL ayrı audit kapsamıdır.'),
'quick-xml':('Yüksek (DoS)','0.30 Windows tauri-winrt-notification yalnız escape kullanıyor; kaynakta Reader/NsReader çağrısı görülmedi. 0.31 macOS plist; 0.37 Linux wayland-scanner build XML. Namespace/attribute saldırı koşulu bu yollarda kanıtlanmış değil. Lock bulgusu AÇIK; üst bağımlılıklarda >=0.41 geçişi ve platform build testi gerekir.'),
'ringbuf':('Yüksek (koşullu bellek güvenliği)','İstemci ses buffer türü HeapRb<f32>; f32 Drop panic üretmez. Bildirilen panic-on-Drop koşulu bu çağrı yolunda görülmedi; diğer/transitif yollar için tam kanıt yok, kapatılmadı. >=0.5.2 API geçişi ve ses/Windows regresyonu gerekir.'),
'rustls':('Orta TLS sınırları / Yüksek complete_io DoS','TLS handshake; sertifika doğrulaması atlanmadı. 0.23.45 düzeltmesi; eski0.20 SQLx SQLite geçişiyle kaldırıldı. complete_io ve tokio kullanım ayrımı tek başına bulguyu kapatmak için kullanılmadı.'),
'rustls-webpki':('Yüksek (koşullu sertifika doğrulama/DoS)','DNS/URI name constraints için imzalı fakat yanlış verilmiş sertifika; CRL bulguları için CRL kullanımı gerekir. Tam dinamik erişilebilirlik kanıtlanmadı. 0.103.15 düzeltildi; server0.102.8 hbb_common platform-verifier0.3.4 nedeniyle AÇIK. Resmî verifier>=0.6 ve hbb_common TLS API geçişi, güven/ret sertifika regresyonu gerekir; std özelliği yalnız derleme uyumluluğudur.'),
'time':('Orta (koşullu DoS/Unix segfault)','0.3 RFC2822 nested yorum parse:0.3.47 düzeltildi. 0.1.45 eski macOS bağımlılık yolunda; advisory Windows etkilenmez diyor. Lock bulgusu kapatılmadı; eski transitif ebeveyn güncellenmeli.'),
'users':('Yüksek (koşullu yetki)','Linux kullanıcı/grup sorguları. Yanlış root grup ekleme erişim kararına taşınırsa yükseltme riski. Windows hedefi değil; host build graph Linux olabilir. Uzers geçişi hem base hem pinned hbb_common için ayrı API/izin testleri gerektirir; patched sürüm yok.'),
'axum-core':('Yüksek (bellek DoS)','Kaynakta axum handler kullanımı bulunmadı. Kullanılmayan doğrudan axum/tower-http/headers/http bağımlılıkları kaldırıldı; yalnız false-positive işaretleme yapılmadı.'),
'bytes':('Yüksek (bellek güvenliği)','Ağ tamponları; aşırı reserve uzunluğu release overflow koşulu. 1.11.1 güncellemesi.'),
'crossbeam-epoch':('Yüksek (koşullu geçersiz pointer)','Concurrent yapılarda format pointer koşulu. 0.9.20 güncellemesi; exploit gösterilmedi.'),
'h2':('Düşük (advisory) / DoS','HTTP2 boş DATA kuyruğu. Kullanılmayan axum ve devre dışı update-check reqwest zinciri kaynak/manifestten kaldırıldı; h2 artık yok.'),
'libsqlite3-sys':('Yüksek (bellek/DoS)','SQLite printf büyük girdi koşulu; ID veritabanı çalışma zamanı kullanımı. sqlx0.8.6 → libsqlite3-sys0.30.1 güncellemesi, kayıt/restart protokol testleri.'),
'protobuf':('Yüksek (uzak DoS)','Ağdan gelen protobuf mesajları; bilinmeyen grup alanlarında recursion. Runtime/codegen/parse/support birlikte3.7.2, parser regresyonu gerekli ve çalıştırılan kanıtlar ayrı listeli.'),
'remove_dir_all':('Yüksek (koşullu dosya silme)','Yerel saldırganın değiştirdiği klasör ağacını ayrıcalıklı temizleme. tempfile3.10.1 geçişiyle bağımlılık kaldırıldı.'),
'ring':('Orta (koşullu DoS)','Overflow checks + QUIC ya da çok büyük tek AEAD girdisi. 0.17.12 güncellendi;0.16 eski reqwest/SQLx/JWT zincirleri kaldırıldı. Release overflow kapalı diye exception eklenmedi.'),
'sqlx':('Yüksek (koşullu protokol enjeksiyonu)','Proje SQLite kullanıyor; advisory PostgreSQL kanıtlı, SQLite için görünür exploit yok diyor. False-positive sayılmadı;0.8.6 yükseltildi, varsayılan network DB/TLS özellikleri kapalı; gerçek SQLite kayıt/restart testi yapıldı.'),
 'tungstenite':('Yüksek (DoS)','WebSocket header parse. 21118/21119 publish edilmemesi erişimi azaltır; kod yine derlenir.0.20.1 yükseltildi; V1 klasik relay testi yapıldı, web-client kapsam dışı.'),
'webpki':('Yüksek (CPU DoS)','Patolojik sertifika zinciri.0.22.2 ara düzeltmesi; eski TLS zinciri kaldırıldığından final lock içinde yok.'),
'whoami':('Yüksek (hedefe bağlı bellek güvenliği)','Advisory Solaris/illumos ve belirtilen BSD sürümleri; Linux/Windows kapsam dışı açıkça belirtilmiş. Buna rağmen1.5.0 güncellendi, false-positive waiver yok.'),
'rsa':('Yüksek (koşullu zamanlama sızıntısı)','YENİ transitif lock kaydı: sqlx-mysql opsiyonel RSA. SQLite-only normal Linux/Windows dependency tree içinde yok. Bleichenbacher timing; patched sürüm yok. Kullanılmayan özellik lock kaydını gate görmezden gelmiyor; upstream düzeltme/bağımlılık mimarisi incelemesi gerekir.')}
def packages(repo):
    out=[]
    for s in (R/repo/'Cargo.lock').read_text().split('[[package]]')[1:]:
        n=re.search(r'^name = "([^"]+)"',s,re.M);v=re.search(r'^version = "([^"]+)"',s,re.M)
        dep=re.search(r'dependencies = (\[.*?\])',s,re.S)
        out.append((n[1],v[1],ast.literal_eval(dep[1]) if dep else []))
    return out
def targets(repo,pkg,version):
    out=[]
    for label,target in [('Windows','x86_64-pc-windows-msvc'),('Linux','x86_64-unknown-linux-gnu')]:
        a=(R/f'reports/logs/{repo}-current-tree-{target}-normal.log').read_text()
        b=(R/f'reports/logs/{repo}-current-tree-{target}-normal,build.log').read_text()
        pattern=rf'\b{re.escape(pkg)} v{re.escape(version)}(?:[ \n]|$)'
        out.append(label+(': normal graph' if re.search(pattern,a) else ': yalnız host/build graph' if re.search(pattern,b) else ': seçili graph dışında'))
    return '; '.join(out)
allrows=[]
for repo in ('client','server'):
    base=json.loads((R/f'reports/security-baseline/{repo}-audit.json').read_text())
    now=json.loads((R/f'reports/{repo}-audit.json').read_text())
    current={(x['advisory']['id'],x['package']['name'],x['package']['version']) for x in now['vulnerabilities']['list']}
    findings={ (x['advisory']['id'],x['package']['name'],x['package']['version']):x for x in base['vulnerabilities']['list']}
    findings.update({(x['advisory']['id'],x['package']['name'],x['package']['version']):x for x in now['vulnerabilities']['list']})
    pkgs=packages(repo)
    rows=[]
    for key,v in findings.items():
        aid,name,version=key;a=v['advisory'];severity,note=notes[name]
        parents=[n+'@'+ver for n,ver,deps in pkgs if any(d.split()[0]==name for d in deps)]
        row={'repo':repo,'id':aid,'aliases':a['aliases'],'package':name,'baseline_or_current_version':version,'remaining':key in current,'current_versions':[ver for n,ver,_ in pkgs if n==name],'targets':targets(repo,name,version),'severity_engineering':severity,'official_cvss':a['cvss'],'affected_constraints':v['affected'],'runtime_review':note,'parents_current_lock':parents,'patched':v['versions']['patched'],'source':f'https://rustsec.org/advisories/{aid}.html'}
        rows.append(row)
    allrows+=rows
    header=f'# {repo} RustSec triage\n\nBaseline {base["vulnerabilities"]["count"]}, güncel {now["vulnerabilities"]["count"]} vulnerability kaydı. Ham baseline korunur. DÜZELTİLDİ yalnız lock çözümüdür; Windows çalıştırma testi değildir. Graph üyeliği exploit kanıtı değildir. Advisory cvss null ise sayı uydurulmadı; önem mühendislik önceliğidir. Hiçbir waiver/ignore eklenmedi.\n\n'
    header+='| RUSTSEC / CVE | Paket / eski sürüm → güncel | Durum | Etkilenen sürümün güncel hedef graph üyeliği | Önem | Erişilebilirlik ve düzeltme |\n|---|---|---|---|---|---|\n'
    for r in rows:
        aliases=', '.join(x for x in r['aliases'] if x.startswith('CVE')) or 'CVE belirtilmemiş'
        header+=f'| [{r["id"]}]({r["source"]}) / {aliases} | {r["package"]} {r["baseline_or_current_version"]} → {", ".join(r["current_versions"]) or "kaldırıldı"} | {"AÇIK" if r["remaining"] else "DÜZELTİLDİ (lock)"} | {r["targets"]} | {r["severity_engineering"]} | {r["runtime_review"]} |\n'
    header+='\n## Diğer RustSec uyarıları — açık envanter\nBunlar vulnerability sayısına dahil değildir; kaldırılmış/unsound/yanked riskleri ayrı tutulur, otomatik kabul anlamına gelmez.\n\n| Tür | RUSTSEC | Paket/sürüm | Başlık |\n|---|---|---|---|\n'
    for kind,entries in now.get('warnings',{}).items():
        for v in entries:
            a=v.get('advisory') or {};p=v['package'];header+=f'| {kind} | {a.get("id","—")} | {p["name"]}@{p["version"]} | {a.get("title","Registry yanked version")} |\n'
    (R/f'reports/{repo}-vulnerabilities.md').write_text(header)
(R/'reports/security-triage.json').write_text(json.dumps(allrows,indent=2,ensure_ascii=False)+'\n')
inputs={repo:hashlib.sha256((R/repo/'Cargo.lock').read_bytes()).hexdigest() for repo in ('client','server')}
inputs.update(advisory_db_commit=subprocess.check_output(['git','-C',str(R/'build/advisory-db'),'rev-parse','HEAD'],text=True).strip(),cargo_audit='0.22.2')
(R/'reports/security-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
print('Reported',len(allrows),'baseline/current findings; no audit exceptions created.')
