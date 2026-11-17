#!/usr/bin/env python3
"""TAO-only PostgreSQL restore rehearsal; no network, ports, host mounts or shared DB.
Synthetic PASS never represents a real VPS backup restoration.
"""
import argparse,datetime,hashlib,json,os,pathlib,subprocess,tempfile,time,uuid
P=pathlib.Path
ROOT=P('/home/kadir/rust');PRIVATE=ROOT/'build/vps-maintenance-private'
IMAGE='postgres@sha256:ec9f656f17c8b4dfebf49e58cf5c46d493d4846d4ea6d8b85d0637f68ee33bfc'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def run(a,**kw):
 r=subprocess.run(a,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=600,**kw)
 if r.returncode:raise RuntimeError('Isolated command failed; secret-bearing output suppressed')
 return r.stdout

def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--synthetic',action='store_true');g.add_argument('--dump',type=P)
 ap.add_argument('--sha256');ap.add_argument('--report',type=P,required=True);a=ap.parse_args()
 if not P.cwd().resolve().is_relative_to(ROOT) or a.report.exists():raise RuntimeError('Unexpected working directory or existing report')
 os.umask(0o077);PRIVATE.mkdir(mode=0o700,exist_ok=True)
 if not a.synthetic:
  if not a.dump.resolve().is_relative_to(PRIVATE) or a.dump.is_symlink() or not a.sha256 or sha(a.dump)!=a.sha256:raise RuntimeError('Unverified private dump')
 run(['docker','image','inspect',IMAGE])
 name='fildesk-pg-restore-'+uuid.uuid4().hex[:12];started=False
 report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image':IMAGE,'mode':'synthetic' if a.synthetic else 'actual-dump','actual_vps_backup_restore':'NOT RUN','network':'none','ports':[],'host_mounts':[],'cpu':0.5,'memory_mib':768,'pids':64,'postgres_data_tmpfs_mib':256,'ownership_acl_restore':'NOT TESTED; --no-owner --no-privileges','full_application_restore':'NOT RUN'}
 try:
  run(['docker','run','-d','--name',name,'--label','fildesk.restore=temporary','--network','none','--read-only','--user','999:999','--cap-drop','ALL','--security-opt','no-new-privileges','--cpus','0.5','--memory','768m','--memory-swap','768m','--pids-limit','64','--log-driver','none','--tmpfs','/var/lib/postgresql/data:rw,uid=999,gid=999,mode=0700,size=256m','--tmpfs','/var/run/postgresql:rw,uid=999,gid=999,mode=0700,size=8m','--tmpfs','/tmp:rw,noexec,nosuid,size=16m','-e','POSTGRES_HOST_AUTH_METHOD=trust',IMAGE,'postgres','-c','listen_addresses=','-c','shared_buffers=32MB','-c','max_connections=10'])
  started=True
  for _ in range(60):
   r=subprocess.run(['docker','exec',name,'pg_isready','-U','postgres'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
   if r.returncode==0:break
   time.sleep(0.5)
  else:raise RuntimeError('Isolated PostgreSQL startup timeout')
  report['postgres_version']=run(['docker','exec',name,'postgres','--version']).decode().strip()
  def sql(db,text):return run(['docker','exec',name,'psql','-X','-U','postgres','-d',db,'-v','ON_ERROR_STOP=1','-Atc',text])
  if a.synthetic:
   sql('postgres','CREATE DATABASE fildesk_synthetic;')
   sql('fildesk_synthetic','CREATE TABLE fixture(id integer PRIMARY KEY, label text NOT NULL); INSERT INTO fixture VALUES(1,\'synthetic\');')
   folder=P(tempfile.mkdtemp(prefix='synthetic-',dir=PRIVATE));dump=folder/'synthetic.dump'
   # Synthetic data only. Real data streams directly from private local file below.
   dump.write_bytes(run(['docker','exec',name,'pg_dump','-U','postgres','-Fc','fildesk_synthetic']))
  else:dump=a.dump
  report['dump_sha256']=sha(dump)
  sql('postgres','CREATE DATABASE fildesk_restore;')
  with open(dump,'rb') as f:
   run(['docker','exec','-i',name,'pg_restore','-U','postgres','--dbname=fildesk_restore','--exit-on-error','--single-transaction','--no-owner','--no-privileges'],stdin=f)
  if a.synthetic and sql('fildesk_restore','SELECT count(*) FROM fixture WHERE id=1 AND label=\'synthetic\';').strip()!=b'1':raise RuntimeError('Synthetic data mismatch')
  report['restore']='PASS'
  report['user_table_count']=int(sql('fildesk_restore',"SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema');").strip())
  if not a.synthetic:report['actual_vps_backup_restore']='PASS: database data/schema only; archive and app acceptance separate'
 except Exception as e:
  report['restore']='FAIL';report['error']=str(e) if isinstance(e,RuntimeError) else type(e).__name__
 finally:
  if started:
   # Only this randomly named, newly created container, after ownership label check.
   tag=run(['docker','inspect','--format','{{index .Config.Labels "fildesk.restore"}}',name]).strip()
   if tag!=b'temporary':raise RuntimeError('Container cleanup identity mismatch')
   run(['docker','stop','--time','5',name]);run(['docker','rm',name]);report['temporary_container_removed']=True
  a.report.write_text(json.dumps(report,indent=2)+'\n')
 if report.get('restore')!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
