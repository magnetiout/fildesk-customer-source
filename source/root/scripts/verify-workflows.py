#!/usr/bin/env python3
import pathlib,re,subprocess,yaml
root=pathlib.Path(__file__).resolve().parents[1]
for p in sorted((root/'.github/workflows').glob('fil-*.yml')):
    d=yaml.safe_load(p.read_text());triggers=d.get('on',d.get(True))
    assert set(triggers)=={'workflow_dispatch'},p
    assert d['permissions']=={'contents':'read'},p
    assert 'secrets.' not in p.read_text(),p
    for job in d['jobs'].values():
        assert 'timeout-minutes' in job
        for step in job['steps']:
            if 'uses' in step:assert re.fullmatch(r'[\w/-]+@[0-9a-f]{40}',step['uses']),step['uses']
subprocess.run(['docker','compose','-f',str(root/'deployment/development/compose.yml'),'config','--quiet'],check=True)
prod=subprocess.run(['docker','compose','--env-file',str(root/'deployment/singapore/.env.example'),'-f',str(root/'deployment/singapore/compose.yml'),'config','--quiet'],capture_output=True,text=True)
assert prod.returncode!=0,'Production blank config must fail'
print('PASS workflow YAML structure, SHA action pins, minimal permissions, no secret usage')
print('PASS development Compose parse; blank production Compose refused')
print('NOT RUN GitHub runner/native Windows execution; YAML parse is not build proof')
