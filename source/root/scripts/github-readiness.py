#!/usr/bin/env python3
"""Read-only GitHub identity/explicit target permission check. Never pushes or dispatches."""
import argparse,datetime,json,os,pathlib,shutil,subprocess,urllib.request,urllib.error
p=argparse.ArgumentParser();p.add_argument('--repo',help='Owner explicitly authorized owner/repository');a=p.parse_args()
r=pathlib.Path(__file__).resolve().parents[1]
token=os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN');gh=shutil.which('gh')
report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'gh_cli_available':bool(gh),'token_env_present':bool(token),'gh_hosts_file_present':(pathlib.Path.home()/'.config/gh/hosts.yml').exists(),'explicit_repository':a.repo,'check_scope':'Read-only identity/permission check; publication and workflow runs reported separately','blockers':[]}
gh_authenticated=False
if not token and gh:
    # gh 2.4 lacks `gh auth token`; use its authenticated API transport directly.
    result=subprocess.run([gh,'auth','status','--hostname','github.com'],capture_output=True,text=True)
    gh_authenticated=result.returncode==0
report['gh_authenticated']=gh_authenticated
def api(path):
    if gh_authenticated:
        return json.loads(subprocess.check_output([gh,'api',path],text=True,stderr=subprocess.PIPE))
    request=urllib.request.Request('https://api.github.com/'+path,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(request,timeout=20) as response:return json.load(response)
if not (token or gh_authenticated):report['blockers'].append('Usable GitHub credential unavailable')
else:
    try:
        report['identity']=api('user')['login']
        if a.repo:
            import re
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',a.repo):raise ValueError('Invalid repository identifier')
            repo=api('repos/'+a.repo);report['repository_permissions']=repo.get('permissions',{})
            if not report['repository_permissions'].get('push'):report['blockers'].append('Repository push permission unavailable')
            # Read-only Actions availability; no run, upload, repo creation or cost incurred.
            report['actions_access']=bool(api('repos/'+a.repo+'/actions/workflows').get('workflows') is not None)
    except (urllib.error.URLError,KeyError,ValueError,subprocess.CalledProcessError) as e:
        report['blockers'].append('GitHub identity/permission check failed: '+type(e).__name__)
if not a.repo:report['blockers'].append('Owner-authorized GitHub target not specified')
report['status']='BLOCKED' if report['blockers'] else 'READY FOR AUTHORIZED PUBLISH'
(r/'reports/github-readiness.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(2 if report['blockers'] else 0)
