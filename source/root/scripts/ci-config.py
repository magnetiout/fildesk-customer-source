#!/usr/bin/env python3
import json,os,pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[1]
c=json.loads(os.environ['FIL_CONFIG_JSON'])
c['profile']=os.environ.get('FIL_PROFILE','customer')
(root/'build').mkdir(exist_ok=True)
p=root/'build/client.local.json';p.write_text(json.dumps(c))
subprocess.run([sys.executable,str(root/'scripts/configure-client.py'),str(p)],check=True)

if os.environ.get('GITHUB_ENV'):
    with open(os.environ['GITHUB_ENV'],'a') as envfile:
        envfile.write('FIL_ENVIRONMENT='+c['environment']+'\n')
