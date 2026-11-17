#!/usr/bin/env python3
"""Read-only post-cleanup evidence; no raw environment, PM2 or journal output."""
import datetime,json,os,pathlib,shutil,subprocess,time
P=pathlib.Path
os.nice(15)
def run(a,t=25):
 p=subprocess.run(a,capture_output=True,text=True,timeout=t);return p.returncode,p.stdout
r={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':run(['hostname'])[1].strip(),'os':P('/etc/os-release').read_text(),'kernel':run(['uname','-rm'])[1].strip(),'cpus':os.cpu_count(),'cpu_model':next((l.split(':',1)[1].strip() for l in P('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')),''),'samples':[]}
for i in range(3):
 mem={l.split(':')[0]:int(l.split(':')[1].split()[0])*1024 for l in P('/proc/meminfo').read_text().splitlines() if l.split(':')[0] in ('MemTotal','MemAvailable','SwapTotal','SwapFree')}
 r['samples'].append({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'memory':mem,'load':os.getloadavg()})
 if i<2:time.sleep(10)
r['df']=run(['df','-B1','-PT'])[1];r['inodes']=run(['df','-Pi'])[1];r['vmstat']=run(['vmstat','1','5'])[1]
r['listeners']=run(['ss','-H','-lntu'])[1];r['processes']=run(['ps','-eo','pid,user,comm,rss,pcpu','--sort=-rss'])[1].splitlines()[:26]
r['services']=run(['systemctl','list-units','--type=service','--state=running','--no-pager','--plain'])[1]
r['unit_states']={}
for u in ('ssh','nginx','pm2-root','postgresql@16-main'):
 r['unit_states'][u]=run(['systemctl','show',u,'--property=ActiveState,SubState,UnitFileState,NRestarts,ActiveEnterTimestamp'])[1]
r['runtime']={n:shutil.which(n) for n in ('docker','podman','bwrap','unshare','systemd-run','ip')}
r['user_manager']=run(['systemctl','--user','is-system-running'])[0]
r['user_linger']=run(['loginctl','show-user',str(os.getuid()),'--property=Linger'])[1].strip()
r['user_namespace_probe_exit']=run(['unshare','--user','--map-root-user','--net','true'])[0]
r['sudo_noninteractive']=run(['sudo','-n','true'])[0]
r['health']={}
for d in ('filteknoloji.com','feekiller.com','kanaryaelektronik.com'):
 code,out=run(['curl','--silent','--connect-timeout','8','--max-time','20','--resolve',d+':443:127.0.0.1','-o','/dev/null','-w','%{http_code} %{ssl_verify_result}','https://'+d+'/'])
 r['health'][d]={'exit':code,'http_tls':out}
r['pm2']={}
# Only query a daemon already running; never bootstrap one.
for owner,home in [('root','/root/.pm2'),('kado','/home/kado/.pm2')]:
 if owner=='root' and run(['systemctl','is-active','--quiet','pm2-root'])[0]!=0:r['pm2'][owner]={'status':'ROOT_DAEMON_NOT_ACTIVE_NO_CLI'};continue
 if owner=='kado':
  try:
   pid=int(P(home+'/pm2.pid').read_text().strip());proc=P('/proc')/str(pid)
   if proc.stat().st_uid!=os.getuid() or 'PM2' not in (proc/'comm').read_text():raise ValueError('wrong daemon')
  except (OSError,ValueError):r['pm2'][owner]={'status':'NO_VERIFIED_DAEMON_NO_CLI'};continue
 code,out=run((['sudo','-n','/usr/bin/pm2','jlist'] if owner=='root' else ['/usr/bin/pm2','jlist']))
 try:
  rows=json.loads(out) if code==0 else [];r['pm2'][owner]={'exit':code,'apps':[{'name':p['name'],'pid':p['pid'],'cwd':p['pm2_env'].get('pm_cwd'),'script':p['pm2_env'].get('pm_exec_path'),'status':p['pm2_env'].get('status'),'restarts':p['pm2_env'].get('restart_time'),'mode':p['pm2_env'].get('exec_mode')} for p in rows]}
 except ValueError:r['pm2'][owner]={'exit':code,'parse':'UNAVAILABLE'}
r['trees']={p:os.path.lexists(p) for p in ('/var/www/taner','/var/www/teldex','/home/kado/teldex-admin','/home/kado/teldex-admin.git','/opt/fildesk-server','/home/kado/fildesk-staging')}
code,out=run(['journalctl','--since','-30min','-p','err','-o','json','--no-pager']);counts={}
for line in out.splitlines():
 try:unit=json.loads(line).get('_SYSTEMD_UNIT','unknown');counts[unit]=counts.get(unit,0)+1
 except ValueError:pass
r['journal_error_counts']={'exit':code,'visible_to':'kado (may be incomplete)','units':counts}
r['reboot_required']=P('/var/run/reboot-required').exists()
print(json.dumps(r,indent=2))
