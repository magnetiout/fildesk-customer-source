#!/usr/bin/env python3
"""Actual systemd private network + shared slice + wire test, one unit/two children.
Does NOT validate VPS DynamicUser or cross-unit JoinsNamespaceOf.
"""
import datetime,json,os,pathlib,subprocess,uuid
R=pathlib.Path(__file__).resolve().parents[1];name='fildesk-private-'+uuid.uuid4().hex[:8];work=R/'build'/name;work.mkdir(mode=0o700);(work/'data').mkdir(mode=0o700);slice=name+'.slice';unit=name+'.service';anchor=name+'-budget.service'
code='''import json,pathlib,os,subprocess,time,importlib.util
R=pathlib.Path(ROOT);W=pathlib.Path(WORK)
assert os.readlink('/proc/self/ns/net')!=HOST
subprocess.run(['/usr/sbin/ip','link','set','lo','up'],check=True)
subprocess.run(['/usr/sbin/ip','address','add','192.0.2.1/32','dev','lo'],check=True)
import socket
assert sorted(n for _,n in socket.if_nameindex())==['lo']
env=dict(os.environ,RUST_LOG='error');os.umask(0o077);children=[]
try:
 for n,args in [('hbbs',['-r','192.0.2.1:21117','-k','-']),('hbbr',['-k','-'])]:
  children.append(subprocess.Popen([str(R/'artifacts/server-candidate'/n),*args],cwd=W/'data',env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL));time.sleep(.5)
 s=importlib.util.spec_from_file_location('probe',R/'deployment/singapore-systemd-v2/server_protocol.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.run(21115,W/'data',W/'synthetic.json',host='192.0.2.1')
 ns=[os.readlink('/proc/'+str(p.pid)+'/ns/net') for p in children];assert ns[0]==ns[1] and ns[0]!=HOST
 cg=pathlib.Path('/sys/fs/cgroup'+pathlib.Path('/proc/self/cgroup').read_text().split('0::')[1].strip()).parent
 vals={n:(cg/n).read_text().strip() for n in ('memory.current','memory.max','memory.high','memory.swap.max','pids.max','cpu.max')}
 assert vals['memory.max']=='201326592' and vals['memory.high']=='134217728' and vals['memory.swap.max']=='0' and vals['pids.max']=='64'
 quota,period=map(int,vals['cpu.max'].split());assert quota/period==.25
 print(json.dumps({'namespaces':ns,'host_namespace':HOST,'effective_shared_slice':vals,'result':'PASS','scope':'one user-systemd unit; unshare creates private netns; NOT systemd PrivateNetwork/JoinsNamespaceOf or VPS DynamicUser'}))
finally:
 for p in children:p.terminate()
 for p in children:p.wait(timeout=10)
'''.replace('ROOT',repr(str(R))).replace('WORK',repr(str(work))).replace('HOST',repr(os.readlink('/proc/self/ns/net')))
p=work/'run.py';p.write_text(code)
def run(a):return subprocess.check_output(a,stderr=subprocess.STDOUT,text=True)
try:
 run(['systemd-run','--user','--quiet','--collect','--unit='+anchor,'--slice='+slice,'/bin/sleep','90'])
 run(['systemctl','--user','set-property','--runtime',slice,'CPUQuota=25%','MemoryHigh=128M','MemoryMax=192M','MemorySwapMax=0','TasksMax=64'])
 out=run(['systemd-run','--user','--quiet','--collect','--wait','--pipe','--unit='+unit,'--slice='+slice,'-p','NoNewPrivileges=yes','/usr/bin/unshare','--user','--map-root-user','--net','/usr/bin/python3',str(p)])
 (R/'reports/systemd-private-pair-test.log').write_text(out);print(out)
except subprocess.CalledProcessError as e:
 (R/'reports/systemd-private-pair-test.log').write_text('FAIL\n'+e.output);print(e.output);raise
finally:
 for n in (unit,anchor,slice):subprocess.run(['systemctl','--user','stop',n],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['systemctl','--user','revert',slice],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
