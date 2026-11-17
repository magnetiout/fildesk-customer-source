#!/usr/bin/env python3
"""Short synthetic TAO measurement, zero published ports; no VPS process starts."""
import datetime,json,pathlib,subprocess,time,uuid
root=pathlib.Path(__file__).resolve().parents[1];name='fildesk-budget-'+uuid.uuid4().hex[:10]
image='debian@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587'
def call(a):return subprocess.check_output(a,text=True).strip()
result={'scope':'TAO isolated idle/startup plus TCP connects; not VPS/relay load','samples':[]}
call(['docker','image','inspect',image,'--format','{{.Id}}'])
try:
 call(['docker','run','-d','--name',name,'--network','none','--cpus','0.25','--memory','192m','--memory-swap','192m','--pids-limit','64','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','65534:65534','--tmpfs','/data:uid=65534,gid=65534,mode=0700,size=16m','--tmpfs','/tmp:size=8m','-v',str(root/'artifacts/server-candidate')+':/opt/fildesk:ro','-w','/data','-e','RUST_LOG=warn',image,'sh','-c','umask 077; /opt/fildesk/hbbs -r 127.0.0.1:21117 -k - & /opt/fildesk/hbbr -k - & wait'])
 for i in range(5):
  time.sleep(2)
  result['samples'].append(call(['docker','exec',name,'sh','-c','cat /sys/fs/cgroup/memory.current; if test -r /sys/fs/cgroup/memory.peak; then cat /sys/fs/cgroup/memory.peak; else echo unavailable; fi; cat /sys/fs/cgroup/pids.current']))
 call(['docker','exec',name,'bash','-c','for port in 21115 21116 21117; do for i in {1..10}; do (exec 3<>/dev/tcp/127.0.0.1/$port) || exit 1; done; done'])
 info=json.loads(call(['docker','inspect',name]))[0];result['oom_killed']=info['State']['OOMKilled'];result['network']=info['HostConfig']['NetworkMode'];result['published_ports']=info['HostConfig']['PortBindings'];result['limit_bytes']=info['HostConfig']['Memory'];result['max_sampled_bytes']=max(int(v.splitlines()[0]) for v in result['samples']);result['kernel_peak_bytes']=result['samples'][-1].splitlines()[1];result['result']='PASS'
finally:
 # Remove only the randomly named test container created in this invocation.
 subprocess.run(['docker','rm','-f',name],check=True,stdout=subprocess.DEVNULL)
result['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(root/'reports/staging-resource-probe.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
