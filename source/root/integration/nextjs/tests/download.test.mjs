import { test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const Download = require('../../.test-dist/nextjs/components/FilDeskDownload.js').default;
const render = props => renderToStaticMarkup(React.createElement(Download, {supportUrl: 'https://filteknoloji.com', ...props}));
test('draft has no download link', () => { const html = render({}); assert.match(html, /henüz yayımlanmadı/); assert.doesNotMatch(html, /download=""/); });
test('invalid published release is rejected', () => assert.throws(() => render({release: {version:'0.1.0',sha256:'fake',bytes:3}})));
test('unsigned public download is rejected', () => assert.throws(() => render({privacyUrl:'/privacy',release:{version:'0.1.0-dev',sha256:'a'.repeat(64),bytes:1024,downloadUrl:'/files/FilDesk.exe',sourceUrl:'/files/source.tar.gz',signing:'unsigned-test'}})));
test('unsafe support URL rejected', () => assert.throws(() => render({supportUrl:'javascript:alert(1)'})));

const base='https://filteknoloji.com/downloads/fildesk/releases/1.5.0-77';
const unsigned={schema_version:2,kind:'fildesk-public-download',approved:true,environment:'production',profile:'customer',version:'1.5.0+77',filename:'FilDesk-Destek-Windows.exe',downloadUrl:base+'/FilDesk-Destek-Windows.exe',sourceUrl:base+'/source/FilDesk-Corresponding-Source.tar.gz',sha256:'a'.repeat(64),bytes:1024,sourceSHA256:'b'.repeat(64),releaseEvidenceSHA256:'c'.repeat(64),supportedSystems:['Windows 11 x64'],signing:'unsigned',signatureStatus:'NotSigned',publisher_verified:false,policyApproval:'owner-unsigned-fildesk-20261025',smartscreenReputation:'NOT_CLAIMED'};
test('approved unsigned release discloses status without verified publisher or untested OS claim',()=>{
 const html=render({privacyUrl:'/privacy',release:unsigned});
 assert.match(html,/Windows için indir/);assert.match(html,/dosya imzasızdır/);
 assert.doesNotMatch(html,/Doğrulanan yayıncı/);assert.doesNotMatch(html,/Windows 10/);
 assert.match(html,/FilDesk-Destek-Windows.exe/);assert.match(html,/1.5.0\+77/);
});
test('signed publisher shown only with Valid status',()=>{
 const html=render({privacyUrl:'/privacy',release:{...unsigned,signing:'authenticode',signatureStatus:'Valid',publisher_verified:true,publisher:'TEST FIXTURE'}});
 assert.match(html,/Doğrulanan yayıncı/);
 assert.throws(()=>render({privacyUrl:'/privacy',release:{...unsigned,publisher_verified:true}}));
});
test('published download requires privacy notice',()=>assert.throws(()=>render({release:unsigned})));
