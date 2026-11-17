import type { CSSProperties } from 'react';
import { validateRelease, type WindowsRelease } from '../../distribution/release-contract.mjs';
export type { WindowsRelease } from '../../distribution/release-contract.mjs';
export type FilDeskProps = {
  release?: WindowsRelease;
  privacyUrl?: string;
  supportUrl: string;
};
function safeUrl(value: string): string {
  if (/[\\\u0000-\u0020]/.test(value)) throw new Error('Invalid URL characters');
  if (value.startsWith('/') && !value.startsWith('//')) return value;
  const url = new URL(value);
  if (url.protocol !== 'https:') throw new Error('HTTPS or a local absolute path required');
  return url.toString();
}
const card: CSSProperties = { padding: '1.5rem', border: '1px solid #dce5e8', borderRadius: 18, background: '#fff' };

export default function FilDeskDownload({ release, privacyUrl, supportUrl }: FilDeskProps) {
  if (release) {
    validateRelease(release);
    if (!privacyUrl) throw new Error('Reviewed privacy notice required');
  }
  return (
    <main lang="tr" style={{ background: '#f4f7f8', color: '#173741', padding: 'clamp(20px, 5vw, 64px)', fontFamily: 'system-ui, sans-serif', lineHeight: 1.65 }}>
      <div style={{ maxWidth: 920, margin: 'auto' }}>
        <img src="/fildesk/fil-teknoloji.svg" alt="Fil Teknoloji logosu" width={80} height={80} />
        <p style={{ letterSpacing: 2, fontWeight: 700 }}>FİL TEKNOLOJİ</p>
        <h1 style={{ fontSize: 'clamp(36px, 7vw, 64px)', lineHeight: 1.1, marginBottom: 20 }}>Destek, bir bağlantı uzağınızda.</h1>
        <p style={{ fontSize: 20, maxWidth: 640 }}>FilDesk ile bilgisayarınızdaki sorunu birlikte çözelim. Hesap açmadan, ID ve geçici parolanızla yetkili destek personeline erişim sağlayın.</p>
        <section aria-labelledby="download-title" style={card}>
          <h2 id="download-title">Windows için FilDesk</h2>
          <p>{release ? release.supportedSystems.join(' / ') : 'Windows • 64 bit'} • İnternet bağlantısı gerekir</p>
          {release?.compatibilityNote && <p>{release.compatibilityNote}</p>}
          {release ? <>
            <a href={safeUrl(release.downloadUrl)} download={release.filename} style={{ display: 'inline-block', padding: '14px 26px', borderRadius: 10, background: '#205c74', color: '#fff', fontWeight: 700 }}>Windows için indir</a>
            {release.signing === 'authenticode' && <p>Doğrulanan yayıncı: {release.publisher}</p>}
            <p>Sürüm: {release.version} · {(release.bytes / 1048576).toFixed(1)} MB</p>
            <p>{release.signing === 'unsigned'
              ? 'Bu dosya imzasızdır; Windows yayıncıyı doğrulayamaz ve güvenlik uyarısı gösterebilir. Emin değilseniz destek ekibine danışın.'
              : 'Authenticode imzası bulunan sürüm. Windows dosya özelliklerinden yayıncıyı doğrulayın. İmza, SmartScreen uyarısı çıkmayacağını garanti etmez.'}</p>
            <details><summary>SHA256 dosya doğrulama</summary><code style={{ overflowWrap: 'anywhere' }}>{release.sha256}</code><p>PowerShell: <code>{`Get-FileHash .\\${release.filename} -Algorithm SHA256`}</code></p></details>
            <p><a href={safeUrl(release.sourceUrl)}>Bu sürümün kaynak kodu ve lisansları</a></p>
          </> : <p role="status"><strong>Test hazırlığı sürüyor.</strong> Doğrulanmış Windows dosyası henüz yayımlanmadı.</p>}
        </section>
        <section aria-labelledby="steps-title" style={{ margin: '36px 0' }}>
          <h2 id="steps-title">Dört adımda uzaktan destek</h2>
          <ol>
            <li>{release?.filename ?? 'FilDesk'} dosyasını indirin ve açın. Destek için kurulum gerekmez.</li>
            <li>Ekrandaki bilgisayar ID’si ve geçici parolayı kullanın veya gelen destek isteğini kendiniz kabul edin.</li>
            <li>Bilgileri yalnız görüştüğünüz yetkili Fil Teknoloji destek personeline iletin.</li>
            <li>Oturumu görünür bağlantı penceresinden sonlandırın; işiniz bittiğinde uygulamayı kapatın.</li>
          </ol>
        </section>
        <aside style={card}><strong>Kontrol sizde.</strong> Beklemediğiniz bir arama veya mesaj üzerine ID/parolanızı paylaşmayın. Destek sırasında hassas belgelerinizi kapatın. Dosya aktarımı, pano ve ses izinlerini oturumdan yönetin.</aside>
        <footer style={{ marginTop: 30 }}>
          <a href={safeUrl(supportUrl)}>Fil Teknoloji destek iletişimi</a> · {privacyUrl ? <a href={safeUrl(privacyUrl)}>KVKK ve gizlilik bilgilendirmesi</a> : <span>Gizlilik metni yayın öncesi hukuk değerlendirmesindedir.</span>}
          <p>FilDesk, RustDesk OSS tabanlıdır. AGPL-3.0 ve üçüncü taraf lisansları geçerlidir.</p>
        </footer>
      </div>
    </main>
  );
}
