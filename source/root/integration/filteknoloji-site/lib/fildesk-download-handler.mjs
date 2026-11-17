// Server-only reference handler. No hosting changes or executable publication.
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { validateRelease } from './fildesk-release-contract.mjs';
export { validateRelease } from './fildesk-release-contract.mjs';
export async function download(request, { release, directory }) {
  if (!['GET','HEAD'].includes(request.method)) return new Response(null,{status:405,headers:{Allow:'GET, HEAD'}});
  if (new URL(request.url).protocol !== 'https:') return new Response('HTTPS required',{status:400});
  try { validateRelease(release); } catch { return new Response('Release unavailable',{status:503,headers:{'Cache-Control':'no-store'}}); }
  // Fixed filename and hash-only folder: no request path enters the filesystem.
  let body;
  try { body=await readFile(path.join(directory,release.sha256,'FilDesk.exe')); }
  catch { return new Response('Release unavailable',{status:503}); }
  if(body.length!==release.bytes || createHash('sha256').update(body).digest('hex')!==release.sha256) return new Response('Release integrity failure',{status:503,headers:{'Cache-Control':'no-store'}});
  // Hash URL must match the manifest. Stable aliases must redirect without caching instead.
  if(new URL(request.url).pathname!==new URL(release.downloadUrl).pathname) return new Response(null,{status:404});
  return new Response(request.method==='HEAD'?null:body,{headers:{
    'Content-Type':'application/octet-stream',
    'Content-Disposition':`attachment; filename="${release.filename}"`,
    'Content-Length':String(body.length),
    'X-Content-Type-Options':'nosniff',
    'Cache-Control':'public, max-age=31536000, immutable',
    'ETag':`"sha256-${release.sha256}"`
  }});
}
