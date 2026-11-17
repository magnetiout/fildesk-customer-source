#!/usr/bin/env python3
"""Read all reachable Git history objects before publication; findings contain no secret values."""
import hashlib,json,pathlib,re,subprocess,time
R=pathlib.Path(__file__).resolve().parents[1]
known=[]
for p in [R/'deployment/development/data/id_ed25519',R/'build/security/candidate-data/id_ed25519']:
 if p.exists():known.append(p.read_bytes().strip())
patterns={
 'private-key-pem':rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----[\r\n]+[A-Za-z0-9+/=\r\n]{32,}',
 'github-token':rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b',
 'aws-access-key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
 'credential-url':rb'https?://[^\s/@:"\']{3,}:[^\s/@"\']{8,}@',
 'assigned-secret':rb'(?im)^\s*(?:export\s+)?(?:[A-Z_]*(?:TOKEN|PASSWORD|PRIVATE_KEY|CLIENT_SECRET|API_KEY))\s*[=:]\s*["\']?([A-Za-z0-9_+/.=-]{24,})',
}
compiled={k:re.compile(v) for k,v in patterns.items()}
report={'scope':'all refs reachable Git objects, working tree tracked paths and ignored-path inventory; pattern scan is not a mathematical absence proof','repositories':{}}
for repo in ['.','client','server']:
 base=R/repo
 lines=subprocess.check_output(['git','-C',str(base),'rev-list','--objects','--all'],text=True).splitlines()
 names={line.split(' ',1)[0]:line.split(' ',1)[1] if ' ' in line else '<commit/tag>' for line in lines}
 meta=subprocess.check_output(['git','-C',str(base),'cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'],input=('\n'.join(names)+'\n').encode()).decode().splitlines()
 entries=[line.split() for line in meta if line.split()[1] in ('blob','commit','tag')]
 proc=subprocess.Popen(['git','-C',str(base),'cat-file','--batch'],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
 hits=[];large=[];total=0
 for oid,kind,size in entries:
  proc.stdin.write((oid+'\n').encode());proc.stdin.flush();header=proc.stdout.readline().split();size=int(header[2]);content=proc.stdout.read(size);assert proc.stdout.read(1)==b'\n';total+=size
  reasons=[name for name,pat in compiled.items() if pat.search(content)]
  if any(secret in content for secret in known):reasons.append('KNOWN-DEVELOPMENT-PRIVATE-KEY')
  if reasons:hits.append({'object':oid,'path':names[oid],'rules':reasons})
  if kind=='blob' and (size>10*1024*1024 or re.search(r'\.(exe|dll|pdb|so|a|zip|7z)$',names[oid],re.I)):large.append({'object':oid,'path':names[oid],'bytes':size})
 proc.stdin.close();proc.wait()
 tracked=subprocess.check_output(['git','-C',str(base),'ls-files','-z']).decode().split('\0')
 sensitive=[p for p in tracked if re.search(r'(^|/)(\.env(?:\.|$)|id_ed25519(?:$|\.)|.*\.pem$|.*\.key$|data/|target/|node_modules/)',p)]
 working=[]
 for name in tracked:
  path=base/name
  if not name or not path.is_file():continue
  content=path.read_bytes();reasons=[rule for rule,pat in compiled.items() if pat.search(content)]
  if any(secret in content for secret in known):reasons.append('KNOWN-DEVELOPMENT-PRIVATE-KEY')
  if reasons:working.append({'path':name,'rules':reasons})
 report['repositories'][repo]={'head':subprocess.check_output(['git','-C',str(base),'rev-parse','HEAD'],text=True).strip(),'commits':int(subprocess.check_output(['git','-C',str(base),'rev-list','--all','--count'])),'objects_scanned':len(entries),'bytes_scanned':total,'findings':hits,'working_tree_findings':working,'sensitive_tracked_paths':sensitive,'binary_history_inventory':large}
 print(repo,len(entries),'objects',len(hits),'findings',flush=True)
(R/'reports/publish-history-scan.json').write_text(json.dumps(report,indent=2)+'\n')
