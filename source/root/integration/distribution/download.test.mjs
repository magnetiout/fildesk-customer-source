import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {download,validateRelease} from './download.mjs';
// Synthetic bytes/approval metadata test HTTP behavior, never real signing acceptance.
const bytes=Buffer.from('synthetic HTTP test fixture');
const hash=createHash('sha256').update(bytes).digest('hex');
const url='https://filteknoloji.com/downloads/fildesk/releases/1.5.0-77/FilDesk-Destek-Windows.exe';
const release={schema_version:2,kind:'fildesk-public-download',approved:true,environment:'production',profile:'customer',filename:'FilDesk-Destek-Windows.exe',signing:'unsigned',signatureStatus:'NotSigned',publisher_verified:false,policyApproval:'owner-unsigned-fildesk-20261025',smartscreenReputation:'NOT_CLAIMED',sha256:hash,bytes:bytes.length,version:'1.5.0+77',downloadUrl:url,sourceUrl:url.replace('FilDesk-Destek-Windows.exe','source/FilDesk-Corresponding-Source.tar.gz'),sourceSHA256:'a'.repeat(64),releaseEvidenceSHA256:'b'.repeat(64),supportedSystems:['Windows 11 x64']};
test('approved unsigned build-version accepted; incomplete or misleading metadata fails closed',()=>{
 assert.equal(validateRelease(release).version,'1.5.0+77');
 for(const change of [{approved:false},{signing:'unsigned-test'},{environment:'development'},{profile:'operator'},{sha256:'../escape'},{filename:'installer.zip'},{publisher_verified:true},{policyApproval:''},{releaseEvidenceSHA256:''},{sourceSHA256:''},{supportedSystems:[]},{version:'../77'},{downloadUrl:'https://evil.test/file.exe'},{sourceUrl:'https://evil.test/source'}]) assert.throws(()=>validateRelease({...release,...change}));
 assert.equal(validateRelease({...release,signing:'authenticode',signatureStatus:'Valid',publisher_verified:true,publisher:'TEST FIXTURE'}).signing,'authenticode');
 assert.throws(()=>validateRelease({...release,signing:'authenticode',signatureStatus:'Valid',publisher_verified:true}));
 const deferred={...release,supportedSystems:['Windows 10 x64','Windows 11 x64'],testedSystems:['Windows 11 x64'],compatibilityApproval:'owner-windows10-deferred-20261116',compatibilityNote:'Bu paket Windows 11 üzerinde test edilmiştir. Windows 10 fiziksel kabulü henüz yapılmamıştır.'};
 assert.equal(validateRelease(deferred).testedSystems[0],'Windows 11 x64');
 assert.throws(()=>validateRelease({...deferred,compatibilityNote:'Windows 10 passed'}));
});
test('HTTPS GET/HEAD exact bytes and headers; missing/tampered/wrong-path fail',async()=>{
 const directory=await mkdtemp(path.join(os.tmpdir(),'fil-download-'));
 try {
  await mkdir(path.join(directory,hash));const file=path.join(directory,hash,'FilDesk.exe');await writeFile(file,bytes);
  let response=await download(new Request(url),{release,directory});assert.equal(response.status,200);assert.deepEqual(Buffer.from(await response.arrayBuffer()),bytes);
  assert.equal(response.headers.get('Content-Disposition'),'attachment; filename="FilDesk-Destek-Windows.exe"');assert.equal(response.headers.get('Content-Type'),'application/octet-stream');assert.match(response.headers.get('Cache-Control'),/immutable/);assert.equal(response.headers.get('X-Content-Type-Options'),'nosniff');
  response=await download(new Request(url,{method:'HEAD'}),{release,directory});assert.equal((await response.arrayBuffer()).byteLength,0);assert.equal(response.headers.get('Content-Length'),String(bytes.length));
  assert.equal((await download(new Request(url.replace('https:','http:')),{release,directory})).status,400);
  assert.equal((await download(new Request(url.replace('1.5.0-77','1.5.0-76')),{release,directory})).status,404);
  assert.equal((await download(new Request(url,{method:'POST'}),{release,directory})).status,405);
  assert.equal((await download(new Request(url),{release:{...release,approved:false},directory})).status,503);
  await writeFile(file,'tampered');assert.equal((await download(new Request(url),{release,directory})).status,503);
 } finally {await rm(directory,{recursive:true,force:true});}
});
