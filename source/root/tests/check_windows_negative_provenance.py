#!/usr/bin/env python3
"""Reject modified manifests against an actual downloaded EXE; no Windows execution."""
import argparse,copy,hashlib,importlib.util,json,os,pathlib,subprocess,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('directory',type=pathlib.Path);p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--commit',required=True);a=p.parse_args()
src=a.directory.resolve();manifest=json.loads((src/'manifest.json').read_text(encoding='utf-8-sig'));profile=manifest['profile'];product='FilDesk' if manifest['product']=='FilDesk' else 'FilRemote';rows=[]
cases=[('client_lock_sha256','0'*64,'Lock differs beyond known line-ending conversion'),('public_config_sha256','0'*64,'Embedded public configuration source mismatch'),('project_commit','0'*40,'Source commit/profile/environment mismatch'),('sha256','0'*64,'Artifact SHA256 or byte size mismatch')]
for field,value,reason in cases:
    with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='artifact-negative-') as d:
        dest=pathlib.Path(d)/profile;dest.mkdir();m=copy.deepcopy(manifest);m[field]=value
        (dest/'manifest.json').write_text(json.dumps(m));os.link(src/(product+'.exe'),dest/(product+'.exe'))
        result=subprocess.run([sys.executable,str(ROOT/'scripts/verify-downloaded-windows.py'),str(dest),'--commit',a.commit,'--config',str(a.config.resolve()),'--profile',profile],capture_output=True,text=True)
        assert result.returncode!=0 and reason in result.stderr,(field,result.stderr)
        rows.append({'mutation':field,'expected_rejection':reason,'status':'PASS: rejected','scope':'Local provenance verifier using a modified manifest and the actual downloaded '+profile+' EXE; not Windows runtime'})
# A forged operator manifest must not make a copied customer DLL a second profile.
with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='artifact-profile-swap-') as d:
    spec=importlib.util.spec_from_file_location('fil_config',ROOT/'scripts/configure-client.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    historical=subprocess.check_output(['git','-C',str(ROOT),'show',a.commit+':scripts/configure-client.py'])
    exec(compile(historical,'historical-configure-client.py','exec'),module.__dict__)
    cfg=json.loads(a.config.read_text())
    for name in ['customer','operator']:
        dest=pathlib.Path(d)/name;dest.mkdir();m=copy.deepcopy(manifest);m['profile']=name
        rendered=module.render(dict(cfg,profile=name)).encode().replace(b'\n',b'\r\n')
        m['public_config_sha256']=hashlib.sha256(rendered).hexdigest()
        (dest/'manifest.json').write_text(json.dumps(m))
        for file in [product+'.exe',product+'-bundle.zip']:os.link(src/file,dest/file)
    result=subprocess.run([sys.executable,str(ROOT/'scripts/verify-downloaded-windows.py'),d,'--commit',a.commit,'--config',str(a.config.resolve())],capture_output=True,text=True)
    reason='Customer and operator reused an identical runtime DLL'
    assert result.returncode!=0 and reason in result.stderr,result.stderr
    rows.append({'mutation':'forged second profile reusing the same actual runtime DLL','expected_rejection':reason,'status':'PASS: rejected','scope':'Static package isolation check; not Windows runtime'})
(ROOT/'reports/windows-negative-verification.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
