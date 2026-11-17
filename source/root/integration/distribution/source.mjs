// Stream the matching source archive without buffering a GiB into the web process.
import {open, constants} from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {Readable} from 'node:stream';
import {validateRelease} from './release-contract.mjs';

export async function sourceDownload(request,{release,directory}) {
  if(!['GET','HEAD'].includes(request.method)) return new Response(null,{status:405,headers:{Allow:'GET, HEAD'}});
  if(new URL(request.url).protocol!=='https:') return new Response('HTTPS required',{status:400});
  try{validateRelease(release);}catch{return new Response('Release unavailable',{status:503});}
  if(new URL(request.url).pathname!==new URL(release.sourceUrl).pathname) return new Response(null,{status:404});
  let file,streaming=false;
  try {
    file=await open(path.join(directory,release.sourceSHA256,'FilDesk-Corresponding-Source.tar.gz'),constants.O_RDONLY|constants.O_NOFOLLOW);
    const before=await file.stat();
    if(!before.isFile()||before.size<=0) throw new Error('Invalid archive');
    const hash=createHash('sha256');
    for await(const chunk of file.createReadStream({start:0,autoClose:false})) hash.update(chunk);
    const after=await file.stat();
    if(hash.digest('hex')!==release.sourceSHA256||before.size!==after.size||before.mtimeMs!==after.mtimeMs||before.ctimeMs!==after.ctimeMs) throw new Error('Source integrity mismatch');
    const headers={'Content-Type':'application/gzip','Content-Disposition':'attachment; filename="FilDesk-Corresponding-Source.tar.gz"',
      'Content-Length':String(after.size),'X-Content-Type-Options':'nosniff','Cache-Control':'public, max-age=31536000, immutable','ETag':`"sha256-${release.sourceSHA256}"`};
    if(request.method==='HEAD') return new Response(null,{headers});
    const body=Readable.toWeb(file.createReadStream({start:0}));
    streaming=true;
    return new Response(body,{headers});
  }catch{return new Response('Source unavailable',{status:503,headers:{'Cache-Control':'no-store'}});}
  finally{if(file&&!streaming) await file.close();}
}
