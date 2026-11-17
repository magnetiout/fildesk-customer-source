import { validateRelease } from './fildesk-release-contract.mjs';

// Shape validation only. This file is populated by the gated release exporter,
// never by a web request, administrator form or environment approval flag.
export function approvedPublicFilDeskDownload(value: unknown) {
    try {
        const release = validateRelease(value);
        return {
            version: release.version, sha256: release.sha256, bytes: release.bytes,
            downloadUrl: release.downloadUrl, sourceUrl: release.sourceUrl,
            supportedSystems: release.supportedSystems, signing: release.signing,
            compatibilityNote: release.compatibilityNote,
            publisher: release.signing === 'authenticode'
                ? release.publisher : 'Windows tarafından doğrulanmadı',
        };
    } catch {
        return null;
    }
}
