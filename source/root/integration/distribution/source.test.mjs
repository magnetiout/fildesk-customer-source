import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {sourceDownload} from './source.mjs';
const bytes=Buffer.from('synthetic source fixture; not a release');
const hash=createHash('sha256').update(bytes).digest('hex');
const base='https://filteknoloji.com/downloads/fildesk/releases/1.5.0-77';
const release={schema_version:2,kind:'fildesk-public-download',approved:true,environment:'production',profile:'customer',version:'1.5.0+77',filename:'FilDesk-Destek-Windows.exe',downloadUrl:base+'/FilDesk-Destek-Windows.exe',sourceUrl:base+'/source/FilDesk-Corresponding-Source.tar.gz',sha256:'a'.repeat(64),sourceSHA256:hash,releaseEvidenceSHA256:'b'.repeat(64),bytes:1024,supportedSystems:['Windows 11 x64'],signing:'unsigned',signatureStatus:'NotSigned',publisher_verified:false,policyApproval:'owner-unsigned-fildesk-20261025',smartscreenReputation:'NOT_CLAIMED'};
test('source GET/HEAD streams exact bytes; tampering, wrong path and unpublished release stay closed',async()=>{
 const directory=await mkdtemp(path.join(os.tmpdir(),'fildesk-source-'));
 try{
  await mkdir(path.join(directory,hash));const file=path.join(directory,hash,'FilDesk-Corresponding-Source.tar.gz');await writeFile(file,bytes);
  let response=await sourceDownload(new Request(release.sourceUrl),{release,directory});
  assert.equal(response.status,200);assert.deepEqual(Buffer.from(await response.arrayBuffer()),bytes);
  response=await sourceDownload(new Request(release.sourceUrl,{method:'HEAD'}),{release,directory});
  assert.equal(response.status,200);assert.equal((await response.arrayBuffer()).byteLength,0);
  assert.equal((await sourceDownload(new Request(release.sourceUrl+'bad'),{release,directory})).status,404);
  assert.equal((await sourceDownload(new Request(release.sourceUrl),{release:{...release,approved:false},directory})).status,503);
  await writeFile(file,'tampered');assert.equal((await sourceDownload(new Request(release.sourceUrl),{release,directory})).status,503);
 }finally{await rm(directory,{recursive:true,force:true});}
});
