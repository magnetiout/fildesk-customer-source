// Public metadata is exported only after the repository's release gates pass.
// Validation here checks consistency, not the truth of human acceptance records.
export const unsignedDecision = 'owner-unsigned-fildesk-20261025';
export function validateRelease(r) {
  const sha = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
  if (!r || r.schema_version !== 2 || r.kind !== 'fildesk-public-download' ||
      r.approved !== true || r.environment !== 'production' || r.profile !== 'customer' ||
      typeof r.version !== 'string' || !/^\d+\.\d+\.\d+(?:\+\d+)?$/.test(r.version) ||
      !sha(r.sha256) || !sha(r.releaseEvidenceSHA256) || !sha(r.sourceSHA256) ||
      !Number.isSafeInteger(r.bytes) || r.bytes <= 0 || r.bytes > 1073741824 ||
      !Array.isArray(r.supportedSystems) || r.supportedSystems.length === 0 ||
      r.supportedSystems.some(s => !['Windows 10 x64', 'Windows 11 x64'].includes(s))) {
    throw new Error('Unapproved production Customer metadata');
  }
  const version = r.version.replace('+', '-');
  if (r.compatibilityApproval !== undefined && (
      r.compatibilityApproval !== 'owner-windows10-deferred-20261116' ||
      !Array.isArray(r.testedSystems) || r.testedSystems.length !== 1 || r.testedSystems[0] !== 'Windows 11 x64' ||
      r.compatibilityNote !== 'Bu paket Windows 11 üzerinde test edilmiştir. Windows 10 fiziksel kabulü henüz yapılmamıştır.')) {
    throw new Error('Explicit untested Windows 10 disclosure required');
  }
  const base = `https://filteknoloji.com/downloads/fildesk/releases/${version}`;
  if (r.filename !== 'FilDesk-Destek-Windows.exe' ||
      r.downloadUrl !== `${base}/${r.filename}` ||
      r.sourceUrl !== `${base}/source/FilDesk-Corresponding-Source.tar.gz`) {
    throw new Error('Customer URL/source contract mismatch');
  }
  if (r.signing === 'unsigned') {
    if (r.signatureStatus !== 'NotSigned' || r.publisher_verified !== false ||
        r.policyApproval !== unsignedDecision || r.smartscreenReputation !== 'NOT_CLAIMED') {
      throw new Error('Explicit unsigned policy and disclosure required');
    }
  } else if (r.signing === 'authenticode') {
    if (r.signatureStatus !== 'Valid' || r.publisher_verified !== true ||
        typeof r.publisher !== 'string' || !r.publisher.trim()) throw new Error('Verified publisher required');
  } else throw new Error('Unknown signing mode');
  return r;
}
