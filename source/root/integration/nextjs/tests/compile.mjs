import { spawnSync } from 'node:child_process';
import { mkdirSync, copyFileSync } from 'node:fs';
import path from 'node:path';
const args=['node_modules/typescript/bin/tsc','--noEmit','false','--module','NodeNext','--moduleResolution','NodeNext','--rootDir','..','--outDir','../.test-dist'];
const result=spawnSync(process.execPath,args,{stdio:'inherit'});
if(result.status!==0) process.exit(result.status ?? 1);
mkdirSync('../.test-dist/distribution',{recursive:true});
copyFileSync('../distribution/release-contract.mjs','../.test-dist/distribution/release-contract.mjs');
const tests=spawnSync(process.execPath,['--test','tests/download.test.mjs'],{
  stdio:'inherit',env:{...process.env,NODE_PATH:path.resolve('node_modules')}
});
process.exit(tests.status ?? 1);
