#!/usr/bin/env python3
import pathlib,re,json,hashlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
keypath=ROOT/'deployment/development/data/id_ed25519'
secret=keypath.read_bytes().strip() if keypath.exists() else b''
patterns=[re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}')]
found=[];checked=0
for directory in ('scripts','config','branding','deployment','integration','docs','tests','.github'):
    for p in (ROOT/directory).rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ('node_modules','.test-dist','data','__pycache__')) or p.name=='.env' or '.local.' in p.name:continue
        b=p.read_bytes();checked+=1
        if (secret and secret in b) or any(pattern.search(b) for pattern in patterns):found.append(str(p.relative_to(ROOT)))
if found:raise SystemExit('FAIL suspected secret files: '+', '.join(found))
print(f'PASS bounded first-party secret scan: {checked} files, no development private key or known token pattern')
print('LIMIT: not a complete external secret-scanner audit of every upstream fixture/dependency')
for repo in ('client','server'):
    text=(ROOT/repo/'Cargo.lock').read_text();packages=[]
    for section in text.split('[[package]]')[1:]:
        item={k:v for k,v in re.findall(r'^(name|version|source|checksum) = "([^"\n]*)"$',section,re.M)}
        if item:packages.append(item)
    (ROOT/'reports'/f'{repo}-dependencies.json').write_text(json.dumps({'format':'Cargo lock inventory (not complete SPDX SBOM)','packages':packages},indent=2)+'\n')
    print(repo,len(packages),'Cargo packages inventoried')
