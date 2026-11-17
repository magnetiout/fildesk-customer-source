import subprocess,json,datetime,os,pathlib,socket
if socket.gethostname() != "ubuntu-s-1vcpu-1gb-sgp1" or os.getuid() == 0:
    raise SystemExit("Refuse unexpected host or user context")
os.nice(15)
out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mutations':False}
def run(a):
 r=subprocess.run(a,capture_output=True,text=True,timeout=30);return r
out['pm2']={}
for who,args in [('root',['sudo','-n','/usr/bin/pm2','jlist']),('kado',['/usr/bin/pm2','jlist'])]:
 live=run(['ps','-eo','user=,comm=']).stdout
 if not any(line.split()[0] == who and 'PM2' in line for line in live.splitlines() if line.split()):
  out['pm2'][who]={'status':'BLOCKED: no existing daemon; CLI not invoked'}
  continue
 r=run(args)
 try:
  data=json.loads(r.stdout)
  out['pm2'][who]={'exit':r.returncode,'apps':[{'name':p.get('name'),'pid':p.get('pid'),'pm_id':p.get('pm_id'),'status':p.get('pm2_env',{}).get('status'),'cwd':p.get('pm2_env',{}).get('pm_cwd'),'script':p.get('pm2_env',{}).get('pm_exec_path'),'memory':p.get('monit',{}).get('memory'),'cpu':p.get('monit',{}).get('cpu'),'out_log':p.get('pm2_env',{}).get('pm_out_log_path'),'error_log':p.get('pm2_env',{}).get('pm_err_log_path')} for p in data]}
 except Exception:out['pm2'][who]={'exit':r.returncode,'parse':'FAILED; unfiltered output suppressed'}
out['health']=[]
for host in ['filteknoloji.com','feekiller.com','kanaryaelektronik.com']:
 r=run(['curl','--silent','--show-error','--connect-timeout','8','--max-time','20','--resolve',host+':443:127.0.0.1','-o','/dev/null','-w','%{http_code} %{ssl_verify_result}', 'https://'+host+'/'])
 out['health'].append({'domain':host,'method':'GET / HTTPS local nginx with TLS verification','exit':r.returncode,'http_tls':r.stdout.strip()})
for name,args in [('memory',['free','-b']),('disk',['df','-B1','/']),('load',['cat','/proc/loadavg']),('services',['systemctl','show','nginx','pm2-root','postgresql@16-main','--property=Id,ActiveState,ActiveEnterTimestamp'])]:
 r=run(args);out[name]={'exit':r.returncode,'output':r.stdout}
out['readability']=[]
for s in ['/var/www/taner/server/data','/root/.pm2/dump.pm2','/etc/nginx/sites-available/mexc-dashboard','/var/www/teldex','/home/kado/teldex-admin']:
 p=pathlib.Path(s);out['readability'].append({'path':s,'readable':os.access(p,os.R_OK),'searchable':os.access(p,os.X_OK)})
r=run(['sudo','-n','-u','postgres','/usr/bin/psql','-X','-w','-d','postgres','-Atc',"SELECT state, count(*) FROM pg_stat_activity GROUP BY state;"])
out['postgres_connection_counts']={'exit':r.returncode,'counts':r.stdout.strip() if r.returncode==0 else None,'status':'PASS' if r.returncode==0 else 'BLOCKED: authorized OS/database access unavailable; stderr suppressed'}
print(json.dumps(out,indent=2))
