#!/usr/bin/env python3
"""Local isolated candidate regression. Creates only its own project; no VPS access.
Leaves test data under ignored build/, removes only newly created containers/network.
"""
if not __debug__:
    raise SystemExit("Refusing optimized Python: validation assertions must remain enabled")

import datetime, hashlib, importlib.util, json, os, pathlib, socket, subprocess, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.umask(0o077)
version = subprocess.check_output(['docker','version','--format','{{.Server.Version}}'],text=True).strip()
assert int(version.split('.')[0]) >= 28, 'Docker localhost publishing requires >=28'
for port, kind in ((33115,socket.SOCK_STREAM),(33116,socket.SOCK_STREAM),(33116,socket.SOCK_DGRAM),(33117,socket.SOCK_STREAM)):
    with socket.socket(socket.AF_INET,kind) as sock:
        if kind == socket.SOCK_STREAM: sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        sock.bind(('127.0.0.1',port))
manifest=json.loads((ROOT/'artifacts/server-candidate/manifest.json').read_text())
assert manifest['fil_commit']=='62207aa701e7fd4ecb5ee7bf5d86da1498c0cceb'
for name in ('hbbs','hbbr'):
    assert hashlib.sha256((ROOT/'artifacts/server-candidate'/name).read_bytes()).hexdigest()==manifest['files'][name]['sha256']
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
project='fildesk-staging-test-'+stamp.lower()
assert not subprocess.check_output(['docker','ps','-aq','--filter','label=com.docker.compose.project='+project]).strip()
work=ROOT/'build'/project;work.mkdir(mode=0o700);(work/'data').mkdir(mode=0o700)
env=dict(os.environ,FIL_UID=str(os.getuid()),FIL_GID=str(os.getgid()))
config=json.loads(subprocess.check_output(['docker','compose','-f','deployment/singapore-staging/compose.yml','config','--format','json'],env=env))
config['name']=project;config['networks']['default']['name']=project+'_default'
for name,service in config['services'].items():
    service['restart']='no'
    for v in service['volumes']:
        assert v['target'] in ('/opt/fildesk','/data')
        v['source']=str(ROOT/'artifacts/server-candidate') if v['target']=='/opt/fildesk' else str(work/'data')
    for port in service['ports']:
        assert port['host_ip']=='127.0.0.1'
        port['published']=str(int(port['published'])+12000)
    if name=='hbbs':service['command'][2]='127.0.0.1:33117'
compose=work/'compose.json';compose.write_text(json.dumps(config,indent=2))
cmd=['docker','compose','-f',str(compose)]
def dev_state():
    return subprocess.check_output(['docker','inspect','fil-remote-dev-hbbs-1','fil-remote-dev-hbbr-1','--format','{{.Name}} {{.State.StartedAt}} {{json .HostConfig.PortBindings}}'],text=True)
before=dev_state()
started=False
try:
    started=True
    subprocess.run(cmd+['up','-d'],check=True)
    ids=[project+'-hbbs-1',project+'-hbbr-1']
    for _ in range(30):
        state=json.loads(subprocess.check_output(['docker','inspect',*ids]))
        if all(s['State'].get('Health',{}).get('Status')=='healthy' for s in state):break
        time.sleep(1)
    assert all(s['State'].get('Health',{}).get('Status')=='healthy' for s in state)
    for s in state:
        assert s['HostConfig']['Memory']==256*1024*1024 and s['HostConfig']['PidsLimit']==64
        for ports in s['HostConfig']['PortBindings'].values():assert all(p['HostIp']=='127.0.0.1' for p in ports)
    public=(work/'data/id_ed25519.pub').read_bytes()
    assert public!=(ROOT/'deployment/development/data/id_ed25519.pub').read_bytes()
    assert (work/'data/id_ed25519').stat().st_mode & 0o777==0o600
    spec=importlib.util.spec_from_file_location('probe',ROOT/'tests/server_protocol.py');probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    probe.run(33115,work/'data',work/'probe-profiles.json')
    subprocess.run(cmd+['restart','hbbs','hbbr'],check=True)
    time.sleep(2)
    assert public==(work/'data/id_ed25519.pub').read_bytes()
    probe.run(33115,work/'data',work/'probe-profiles.json')
    report={'scope':'local TAO only; NOT VPS/Windows E2E','result':'PASS','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'project':project,'server_commit':manifest['fil_commit'],'public_key_file_sha256':hashlib.sha256(public).hexdigest(),'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'checks':['health','loopback only','resource limits','new key0600 and independent from dev','synthetic UDP registration','NAT TCP','infrastructure key rejection','bidirectional relay','restart identity and ID persistence']}
    (work/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS local candidate; evidence:',work/'result.json')
finally:
    if started:subprocess.run(cmd+['down'],check=True)
    assert before==dev_state(), 'Existing development service state changed'
    print('Existing development timestamps/bindings unchanged; new test data retained:',work)
