#!/usr/bin/env python3
import hashlib,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
compose=['docker','compose','-f',str(ROOT/'deployment/development/compose.yml')]
def inspect(name):return json.loads(subprocess.check_output(['docker','inspect',name]))[0]
key=ROOT/'deployment/development/data/id_ed25519'
before=hashlib.sha256(key.read_bytes()).hexdigest()
for name in ('fil-remote-dev-hbbs-1','fil-remote-dev-hbbr-1'):
    d=inspect(name);h=d['HostConfig']
    assert h['Memory']==268435456 and h['MemorySwap']==268435456
    assert h['NanoCpus']==500000000 and h['PidsLimit']==64
    assert h['ReadonlyRootfs'] and h['CapDrop']==['ALL']
    assert d['State']['Health']['Status']=='healthy'
    for ports in d['NetworkSettings']['Ports'].values():
        if ports:
            for port in ports:assert port['HostIp']=='127.0.0.1' and port['HostPort'] in ['21115','21116','21117']
assert key.stat().st_mode&0o077==0
print('PASS runtime limits, loopback publication, health, private key mode')
subprocess.run(compose+['restart'],check=True)
subprocess.run(compose+['up','-d','--wait','--wait-timeout','90'],check=True)
assert before==hashlib.sha256(key.read_bytes()).hexdigest()
subprocess.run(['python3',str(ROOT/'tests/server_protocol.py')],check=True)
print('PASS restart preserves private key and same peer profiles; no secrets printed')
