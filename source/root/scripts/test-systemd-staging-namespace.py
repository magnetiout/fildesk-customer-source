#!/usr/bin/env python3
"""Real TAO user-systemd namespace pilot; NOT VPS DynamicUser/system-manager acceptance."""
import datetime,json,os,pathlib,subprocess,uuid,time
R=pathlib.Path(__file__).resolve().parents[1];name='fildesk-ns-'+uuid.uuid4().hex[:8];work=R/'build'/name;work.mkdir(mode=0o700);(work/'data').mkdir(mode=0o700)
proof=work/'host-network.json';proof.write_text(json.dumps({'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'netns':os.readlink('/proc/self/ns/net')}))
guard=str(R/'deployment/singapore-systemd-v2/namespace_guard.py');marker=str(work/'data/network-identity.json')
slice=name+'.slice';units=[];result={'scope':'TAO user systemd; PrivateUsers added, DynamicUser not supported here; VPS NOT RUN','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'FAIL'}
def call(args):return subprocess.check_output(args,stderr=subprocess.STDOUT,text=True).strip()
def start(role,props,args,wait=False):
 unit=name+'-'+role+'.service';units.append(unit)
 command=['systemd-run','--user','--quiet','--collect','--unit='+unit,'--slice='+slice,'--service-type=exec']
 if wait:command+=['--wait','--pipe']
 for p in props:command+=['-p',p]
 return call(command+args)
try:
 start('budget',[],['/bin/sleep','120'])
 call(['systemctl','--user','set-property','--runtime',slice,'CPUQuota=25%','MemoryHigh=128M','MemoryMax=192M','MemorySwapMax=0','TasksMax=64'])
 common=['PrivateUsers=yes','PrivateNetwork=yes','NoNewPrivileges=yes','UMask=0077','Environment=RUST_LOG=error','WorkingDirectory='+str(work/'data')]
 start('hbbs',common+['ExecStartPre=/usr/bin/python3 -I '+guard+' hbbs '+str(proof)+' '+marker],[str(R/'artifacts/server-candidate/hbbs'),'-r','127.0.0.1:21117','-k','-'])
 for _ in range(30):
  if (work/'data/id_ed25519.pub').exists():break
  time.sleep(.1)
 start('hbbr',common+['ExecStartPre=/usr/bin/python3 -I '+guard+' hbbr '+str(proof)+' '+marker,'JoinsNamespaceOf='+name+'-hbbs.service','After='+name+'-hbbs.service'],[str(R/'artifacts/server-candidate/hbbr'),'-k','-'])
 time.sleep(1)
 probe=work/'probe.py'
 probe.write_text("import importlib.util,pathlib,json,os\ns=importlib.util.spec_from_file_location('probe',"+repr(str(R/'tests/server_protocol.py'))+");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nm.run(21115,pathlib.Path("+repr(str(work/'data'))+"),pathlib.Path("+repr(str(work/'synthetic-profiles.json'))+"))\nprint('namespace='+os.readlink('/proc/self/ns/net'))\n")
 result['units']={};ns=[]
 for role in ('hbbs','hbbr'):
  unit=name+'-'+role+'.service';props=call(['systemctl','--user','show',unit,'-p','MainPID,ControlGroup,Slice,ActiveState']);result['units'][role]=props
  pid=dict(l.split('=',1) for l in props.splitlines())['MainPID'];ns.append(os.readlink('/proc/'+pid+'/ns/net'))
 result['namespaces']=ns;result['host_namespace']=os.readlink('/proc/self/ns/net');assert ns[0]==ns[1] and ns[0]!=result['host_namespace']
 result['probe']=start('probe',common+['JoinsNamespaceOf='+name+'-hbbs.service','After='+name+'-hbbs.service'],['/usr/bin/python3',str(probe)],True)
 result['slice']=call(['systemctl','--user','show',slice,'-p','CPUQuotaPerSecUSec,MemoryHigh,MemoryMax,MemorySwapMax,TasksMax,MemoryCurrent,TasksCurrent,ControlGroup'])
 result['status']='PASS'
except subprocess.CalledProcessError as e:result['error']=e.output[-2000:]
except Exception as e:result['error']=type(e).__name__+': '+str(e)
finally:
 for unit in reversed(units):subprocess.run(['systemctl','--user','stop',unit],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['systemctl','--user','stop',slice],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 # Remove only runtime property drop-ins created for this uniquely named pilot slice.
 subprocess.run(['systemctl','--user','revert',slice],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 (R/'reports/systemd-namespace-pilot.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2));raise SystemExit(0 if result['status']=='PASS' else 1)
