import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {brotliCompressSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const digest=(b,kind='sha256')=>createHash(kind).update(b).digest('hex');
const u32=n=>{const b=Buffer.alloc(4);b.writeUInt32BE(n);return b;};
test('payload verifier accepts Windows path prefixes and rejects outer/inner tampering',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'fil-payload-'));
 try {
  const content=Buffer.from('synthetic, not a real executable'),compressed=brotliCompressSync(content),name=Buffer.from('.\\FilDesk.exe');
  const binary=Buffer.concat([Buffer.from('fixture rustdesk'),u32(name.length),name,u32(compressed.length),compressed,Buffer.from(digest(content,'md5')),Buffer.from('rustdesk.\\FilDesk.exe')]);
  const exe=path.join(root,'FilDesk.exe'),manifest=path.join(root,'manifest.json');fs.writeFileSync(exe,binary);
  const record={product:'FilDesk',profile:'TEST FIXTURE',files:[{path:'application/FilDesk.exe',sha256:digest(content),bytes:content.length},{path:'portable/FilDesk.exe',sha256:digest(binary),bytes:binary.length}]};
  const run=()=>execFileSync(process.execPath,[fileURLToPath(new URL('../../scripts/verify-portable-payload.mjs',import.meta.url)),exe,manifest],{stdio:'pipe'});
  fs.writeFileSync(manifest,JSON.stringify(record));assert.equal(JSON.parse(run()).files,1);
  fs.writeFileSync(exe,Buffer.concat([binary,Buffer.from('tamper')]));assert.throws(run);
  fs.writeFileSync(exe,binary);record.files[0].sha256='0'.repeat(64);fs.writeFileSync(manifest,JSON.stringify(record));assert.throws(run);
 }finally{fs.rmSync(root,{recursive:true,force:true});}
});
