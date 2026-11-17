#!/usr/bin/env python3
"""Fail closed; capacity proposal is not a measured VPS production guarantee."""
import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('audit',type=pathlib.Path);p.add_argument('probe',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
x=json.loads(a.audit.read_text());probe=json.loads(a.probe.read_text());reasons=[]
minram=min(s['memory']['MemAvailable'] for s in x['samples']);limit=192*1024**2;reserve=128*1024**2
root_line=next((l for l in x['df'].splitlines() if l.split()[-1]=='/'),None)
if root_line is None or int(root_line.split()[4])<512*1024**2:reasons.append('root free disk below provisional512MiB stage/data/log reserve')
if max(s['load'][0] for s in x['samples'])+0.25>x['cpus']:reasons.append('sampled load plus 0.25CPU budget exceeds vCPU count')
lines=x['vmstat'].splitlines();rows=[l.split() for l in lines[2:] if len(l.split())>=17]
if any(int(r[6]) or int(r[7]) for r in rows[1:]):reasons.append('swap IO observed in brief vmstat samples; investigate before start')
apps=x['pm2'].get('root',{}).get('apps',[])
if {p['name'] for p in apps}!={'filteknoloji','feekiller','kanaryaelektronik'} or any(p['status']!='online' for p in apps):reasons.append('protected PM2 state unavailable or unhealthy')
if minram<limit+reserve:reasons.append('available RAM below 192MiB hard cap + provisional128MiB live-app reserve')
if probe.get('result')!='PASS' or probe.get('max_sampled_bytes',limit)>=limit:reasons.append('local budget probe failed')
if any(v['exit'] or v['http_tls']!='200 0' for v in x['health'].values()):reasons.append('protected HTTPS health failure')
if any(':'+str(n)+' ' in x['listeners'] for n in range(21115,21120)):reasons.append('requested port conflict')
if x['sudo_noninteractive']!=0 and not x['runtime']['docker'] and not x['runtime']['podman'] and x['user_namespace_probe_exit']!=0:reasons.append('no authorized isolated runtime: sudo requires operator; unprivileged network namespace denied')
# Native wildcard listeners are never an acceptable fallback.
reasons.append('new private-network systemd runtime requires reviewed root installation and VPS sandbox validation')
r={'decision':'NO-GO' if reasons else 'GO','reasons':reasons,'capacity_only':'eligible for a root-controlled short pilot, NOT production capacity proof' if minram>=limit+reserve else 'insufficient proposed reserve','min_available_bytes':minram,'combined_server_hard_cap_bytes':limit,'provisional_live_app_reserve_bytes':reserve,'sampled_local_bytes':probe.get('max_sampled_bytes'),'production_gate':'CLOSED'}
a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2));raise SystemExit(2 if reasons else 0)
