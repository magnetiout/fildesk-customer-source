#!/usr/bin/env python3
"""Review scanner findings by exact source context; never print credential values."""
import json,pathlib,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'.tools/prepublish'
def git(path,*args):return subprocess.check_output(['git','-C',str(path),*args],text=True).strip()
out={'scanner':'Gitleaks 8.30.1, official asset checksum verified','scope':'all local refs plus tracked source snapshots and both pinned hbb_common modules','repositories':{},'limitations':['Pattern scans do not mathematically prove absence of every secret/customer datum.','Historical upstream public Firebase client identifiers retained; Cloud permission restrictions were not probed.','No ignored private runtime data, build/cache or local credentials staged.'],'firebase_reference':'https://firebase.google.com/docs/projects/api-keys'}
for name,path in [('root',ROOT),('client',ROOT/'client'),('server',ROOT/'server'),('client-common',ROOT/'client/libs/hbb_common'),('server-common',ROOT/'server/libs/hbb_common')]:
    findings=[]
    for mode in ('history','tree'):
        p=BASE/(name+'-'+mode+'.json');rows=json.loads(p.read_text()) if p.exists() else []
        for row in rows:
            file=row['File'];commit=row.get('Commit')
            if mode=='history':data=git(path,'show',commit+':'+file)
            else:
                file=str(pathlib.Path(file).relative_to(pathlib.Path('.tools/prepublish')/(name+'-tree')))
                data=(BASE/(name+'-tree')/file).read_text(errors='replace')
            line=data.splitlines()[row['StartLine']-1]
            if (file.startswith('src/lang/') or file=='src/tr.rs') and (re.search(r'\("(?:web_)?id_input_tip"',line) or ('?key=' in line and re.search(r'\("(?:web_)?id_input_tip"',data))):
                kind='translated public-key connection example'
            elif file in ('src/custom_server.rs','src/license.rs') and ('Zm9vYmFyLiwyCg==' in line or ('assert_eq!' in data and '#[cfg(test)]' in data)):
                kind='upstream example.net/foobar test fixture'
            elif file.startswith('README') and row['RuleID']=='generic-api-key':kind='upstream public-key connection documentation'
            elif file in ('flutter/web/index.html','web/index.html','flutter_hbb/android/app/google-services.json') and row['RuleID']=='gcp-api-key' and ('firebase' in data.lower() or 'mobilesdk_app_id' in data):kind='historical upstream public Firebase client configuration, absent from current Windows sources'
            elif file=='web/assets/vendor.b7bb6fa2.js' and row['RuleID']=='generic-api-key' and 'crypto_' in data:kind='historical libsodium JavaScript API symbol names'
            else:raise SystemExit('UNREVIEWED: '+name+' '+file+' '+row['RuleID'])
            findings.append({'scope':mode,'rule':row['RuleID'],'file':file,'commit':commit,'line':row['StartLine'],'classification':kind})
    out['repositories'][name]={'head':git(path,'rev-parse','HEAD'),'shallow':git(path,'rev-parse','--is-shallow-repository'),'reviewed':len(findings),'unreviewed':0,'findings':findings}
out['secondary_review']={'private_or_known_development_key_hits':0,'assigned_secret_false_positives':'program identifiers/constructor calls; see publish-history-scan.json','server_dotenv':'byte-identical upstream SQLite DATABASE_URL sample','root_dotenv':'Singapore .env.example template','upstream_history_assets':'official tiny LFS/symlink pointer blobs and historical nssm helper preserved; no local build/cache added'}
(ROOT/'reports/prepublish-secret-review.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({name:{'reviewed':r['reviewed'],'unreviewed':0} for name,r in out['repositories'].items()},indent=2))
