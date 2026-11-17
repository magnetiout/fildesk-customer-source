export type WindowsRelease = {
  schema_version: 2;
  kind: 'fildesk-public-download';
  approved: true;
  environment: 'production';
  profile: 'customer';
  version: string;
  filename: 'FilDesk-Destek-Windows.exe';
  downloadUrl: string;
  sourceUrl: string;
  sha256: string;
  bytes: number;
  releaseEvidenceSHA256: string;
  sourceSHA256: string;
  supportedSystems: ('Windows 10 x64' | 'Windows 11 x64')[];
  testedSystems?: ('Windows 10 x64' | 'Windows 11 x64')[];
  compatibilityApproval?: 'owner-windows10-deferred-20261116';
  compatibilityNote?: string;
} & ({signing: 'unsigned'; signatureStatus: 'NotSigned'; publisher_verified: false;
  policyApproval: 'owner-unsigned-fildesk-20261025'; smartscreenReputation: 'NOT_CLAIMED'} |
  {signing: 'authenticode'; signatureStatus: 'Valid'; publisher_verified: true; publisher: string});
export const unsignedDecision: string;
export function validateRelease(value: unknown): WindowsRelease;
