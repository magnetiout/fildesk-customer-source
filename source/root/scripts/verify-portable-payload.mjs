// Static verification of the actual upstream Brotli payload; no Windows execution.
import fs from 'node:fs';
import {brotliDecompressSync} from 'node:zlib';
import {createHash} from 'node:crypto';
const [exePath,manifestPath]=process.argv.slice(2);
const blob=fs.readFileSync(exePath), manifest=JSON.parse(fs.readFileSync(manifestPath));
const expected=new Map(manifest.files.filter(f=>f.path.startsWith('application/')).map(f=>[f.path.slice(12),f]));
const entrypoint=manifest.product==='FilDesk'?'FilDesk.exe':'FilRemote.exe';
const outer=manifest.files.find(f=>f.path==='portable/'+entrypoint);
if(!outer || outer.bytes!==blob.length || outer.sha256!==createHash('sha256').update(blob).digest('hex'))throw Error('Outer EXE hash mismatch');
const marker=Buffer.from('rustdesk');let verified;
for(let start=blob.indexOf(marker);start>=0;start=blob.indexOf(marker,start+1)) {
 try {
  let at=start+8;const entries=new Map();let total=0;
  while(!blob.subarray(at,at+8).equals(marker)) {
   const n=blob.readUInt32BE(at);at+=4;if(!n||n>4096)throw Error('path length');
   const name=blob.subarray(at,at+n).toString('utf8').replaceAll('\\','/').replace(/^\.\//,'');at+=n;
   if(!expected.has(name)||entries.has(name))throw Error('unknown/duplicate path');
   const length=blob.readUInt32BE(at);at+=4;if(!length||length>blob.length-at-32)throw Error('length');
   const bytes=brotliDecompressSync(blob.subarray(at,at+length),{maxOutputLength:268435456});at+=length;
   const md5=blob.subarray(at,at+32).toString();at+=32;
   if(createHash('md5').update(bytes).digest('hex')!==md5)throw Error('upstream cache hash mismatch');
   const sha=createHash('sha256').update(bytes).digest('hex'),f=expected.get(name);
   if(sha!==f.sha256||bytes.length!==f.bytes)throw Error('payload SHA256/size mismatch');
   total+=bytes.length;entries.set(name,sha);
  }
  at+=8;
  if(![entrypoint,'.\\'+entrypoint,'./'+entrypoint].some(name=>blob.subarray(at,at+Buffer.byteLength(name)).equals(Buffer.from(name)))||entries.size!==expected.size)throw Error('entrypoint/incomplete payload');
  verified={status:'PASS',scope:'Static Brotli extraction byte equality to previously verified bundle manifest; no signature/runtime acceptance',files:entries.size,expanded_bytes:total,exe_bytes:blob.length,exe_sha256:createHash('sha256').update(blob).digest('hex'),profile:manifest.profile,signature:manifest.signing ?? 'unsigned-test',windows_runtime:'NOT RUN'};break;
 }catch { /* Other occurrences of the marker are ordinary binary strings. */ }
}
if(!verified)throw Error('No complete matching portable payload found');
console.log(JSON.stringify(verified,null,2));
