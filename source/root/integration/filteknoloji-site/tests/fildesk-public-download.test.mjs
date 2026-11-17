// Synthetic metadata exercises the site adapter, never physical release evidence.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {createRequire} from 'node:module';
import ts from 'typescript';
const box={};
const localRequire=createRequire(new URL('../lib/fildesk-public-download.ts',import.meta.url));
vm.runInNewContext(ts.transpileModule(fs.readFileSync('lib/fildesk-public-download.ts','utf8'),{
    compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}
}).outputText,{exports:box,require:localRequire});
const adapt=box.approvedPublicFilDeskDownload;
const base='https://filteknoloji.com/downloads/fildesk/releases/1.5.0-77';
function fixture(){return{schema_version:2,kind:'fildesk-public-download',approved:true,
    environment:'production',profile:'customer',version:'1.5.0+77',filename:'FilDesk-Destek-Windows.exe',
    downloadUrl:base+'/FilDesk-Destek-Windows.exe',sourceUrl:base+'/source/FilDesk-Corresponding-Source.tar.gz',
    sha256:'a'.repeat(64),sourceSHA256:'b'.repeat(64),releaseEvidenceSHA256:'c'.repeat(64),bytes:1024,
    supportedSystems:['Windows 11 x64'],signing:'unsigned',signatureStatus:'NotSigned',
    publisher_verified:false,policyApproval:'owner-unsigned-fildesk-20261025',smartscreenReputation:'NOT_CLAIMED'};}
test('checked-in new manifest remains withheld',()=>assert.equal(adapt(JSON.parse(fs.readFileSync('config/fildesk-public-download.json'))),null));
test('unsigned adapter discloses unknown publisher and retains exact source URL',()=>{
    const value=adapt(fixture());assert.equal(value.publisher,'Windows tarafından doğrulanmadı');
    assert.equal(value.sourceUrl,fixture().sourceUrl);assert.equal(value.version,'1.5.0+77');
});
test('owner Windows 10 deferral keeps the untested compatibility disclosure',()=>{
    const note='Bu paket Windows 11 üzerinde test edilmiştir. Windows 10 fiziksel kabulü henüz yapılmamıştır.';
    const value={...fixture(),supportedSystems:['Windows 10 x64','Windows 11 x64'],
        testedSystems:['Windows 11 x64'],compatibilityApproval:'owner-windows10-deferred-20261116',compatibilityNote:note};
    assert.equal(adapt(value).compatibilityNote,note);
    assert.equal(adapt({...value,compatibilityNote:'Windows 10 test edildi'}),null);
});
test('operator, development, unsigned-test and incomplete evidence remain blocked',()=>{
    for(const change of[{profile:'operator'},{environment:'development'},{signing:'unsigned-test'},
        {approved:false},{sourceSHA256:''},{releaseEvidenceSHA256:''},{publisher_verified:true}])
        assert.equal(adapt({...fixture(),...change}),null);
});
test('signed adapter retains a publisher only with Valid signature metadata',()=>{
    const value=adapt({...fixture(),signing:'authenticode',signatureStatus:'Valid',publisher_verified:true,publisher:'SYNTHETIC PUBLISHER'});
    assert.equal(value.publisher,'SYNTHETIC PUBLISHER');
});
test('Customer route does not expose an Operator path or a different origin',()=>{
    for(const change of[{filename:'FilDesk-Operator.exe'},{downloadUrl:'https://evil.invalid/app.exe'},
        {sourceUrl:'https://evil.invalid/source'},{version:'../latest'}]) assert.equal(adapt({...fixture(),...change}),null);
});
