"""Synthetic evidence/PE fixture only. No real release approval is generated."""
import copy,datetime,hashlib,importlib.util,json,pathlib,struct,tempfile,unittest
R=pathlib.Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location('distribution_gate',R/'scripts/distribution_gate.py');gate=importlib.util.module_from_spec(s);s.loader.exec_module(gate)
def sha(b):return hashlib.sha256(b).hexdigest()
class Unsigned(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
  for n in ['config','reports','client','artifacts/customer','artifacts/source']:(self.root/n).mkdir(parents=True)
  body=bytearray(512);body[:2]=b'MZ';struct.pack_into('<I',body,60,128);body[128:132]=b'PE\0\0';struct.pack_into('<H',body,132,0x8664);struct.pack_into('<H',body,152,0x20b)
  (self.root/'artifacts/customer/FilDesk.exe').write_bytes(body);digest=sha(body);lock=b'synthetic lock';(self.root/'client/Cargo.lock').write_bytes(lock)
  self.put('config/release-policy.json',{'schema_version':1,'unsigned_customer_allowed':True,'decision_reference':'owner-unsigned-fildesk-20261025'})
  self.r={'schema_version':2,'kind':'fildesk-distribution','distribution_mode':'UNSIGNED','environment':'production','signature_status':'UNSIGNED','policy_approval':'owner-unsigned-fildesk-20261025','publisher_verified':False,'smartscreen_reputation':'NOT_CLAIMED','version':'1.5.0+74','profile':'customer','sha256':digest,'source':{'root':'1'*40,'client':'2'*40,'server':'3'*40},'lock_sha256':sha(lock),'artifact_path':'artifacts/customer/FilDesk.exe','public_name':'FilDesk-Destek-Windows.exe','url':'https://filteknoloji.com/downloads/fildesk/releases/1.5.0-74/FilDesk-Destek-Windows.exe','gates':{x:'PASS'for x in ['securityReview','licenseCompliance','nativeBuild','nativeConsent','operatorAuthorization','sessionTermination','qaReview','publicReleaseApproval']}}
  self.put('reports/windows-release-candidate.json',{'artifacts':{'customer':{**{k:self.r[k]for k in ['version','sha256','source','lock_sha256']},'profile':'customer','path':self.r['artifact_path']},'operator':{'sha256':'9'*64}}})
  self.put('reports/client-audit.json',{'vulnerabilities':{'count':0}});self.bind_audit()
  (self.root/'artifacts/source/source.tar.gz').write_bytes(b'synthetic source fixture')
  self.evidence('license_review',{'unresolved':[],'source_archive':'artifacts/source/source.tar.gz','source_sha256':sha(b'synthetic source fixture'),'source_url':self.r['url'].rsplit('/',1)[0]+'/source/FilDesk-Corresponding-Source.tar.gz'})
  self.evidence('payload_verification',{'role':'customer','operator_binaries':[],'runtime_complete':True})
  self.evidence('windows_verification',{'execution':'windows-device','signature_status':'NotSigned','protections_unchanged':True,'tester_id':'synthetic-device-tester','windows_build':'10.0.22631','tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
  self.evidence('review',{'decision':'approve','reviewer':'synthetic-independent-reviewer','verification_sha256':self.r['windows_verification']['sha256']});self.save()
 def bind_audit(self):
  self.put('reports/security-inputs.json',{'client':self.r['lock_sha256'],'source':self.r['source'],'artifact_sha256':self.r['sha256'],'target':'x86_64-pc-windows-msvc','client_audit_sha256':sha((self.root/'reports/client-audit.json').read_bytes())})
 def tearDown(self):self.tmp.cleanup()
 def put(self,n,v):
  raw=json.dumps(v).encode();(self.root/n).write_bytes(raw);return sha(raw)
 def evidence(self,key,v):
  self.r[key]={'path':'reports/'+key+'.json','sha256':self.put('reports/'+key+'.json',{'artifact_sha256':self.r['sha256'],'status':'PASS',**v})}
 def save(self):self.put('reports/trusted-distribution.json',self.r)
 def test_explicit_unsigned_fixture_passes_shape_and_bindings(self):self.assertEqual(gate.check(self.root),[])
 def test_owner_policy_required(self):
  self.put('config/release-policy.json',{'schema_version':1,'unsigned_customer_allowed':False});self.assertTrue(gate.check(self.root))
 def test_all_non_signing_gates_remain(self):
  old=copy.deepcopy(self.r)
  for k in old['gates']:
   self.r=copy.deepcopy(old);self.r['gates'][k]='BLOCKED';self.save();self.assertTrue(gate.check(self.root),k)
 def test_no_false_publisher_or_reputation(self):
  for field,value in [('publisher_verified',True),('smartscreen_reputation','VERIFIED'),('signature_status','Valid'),('distribution_mode','UNKNOWN')]:
   old=self.r[field];self.r[field]=value;self.save();self.assertTrue(gate.check(self.root));self.r[field]=old
 def test_changed_exe_rejected(self):
  (self.root/'artifacts/customer/FilDesk.exe').write_bytes(b'changed');self.assertTrue(gate.check(self.root))
 def test_security_and_license_not_waived(self):
  self.put('reports/client-audit.json',{'vulnerabilities':{'count':1}});self.assertTrue(gate.check(self.root));self.put('reports/client-audit.json',{'vulnerabilities':{'count':0}})
  self.evidence('license_review',{'unresolved':['missing grant']});self.save();self.assertTrue(gate.check(self.root))
 def test_operator_and_source_mismatch_rejected(self):
  self.evidence('payload_verification',{'role':'customer','operator_binaries':['Operator.exe'],'runtime_complete':True});self.save();self.assertTrue(gate.check(self.root))
 def test_protections_cannot_be_disabled(self):
  self.evidence('windows_verification',{'execution':'windows-device','signature_status':'NotSigned','protections_unchanged':False,'tester_id':'synthetic-tester','windows_build':'10.0.22631','tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat()});self.save();self.assertTrue(gate.check(self.root))

 def browser_fixture(self):
  spec=importlib.util.spec_from_file_location('browser_gate',R/'scripts/browser-release-gate.py');browser=importlib.util.module_from_spec(spec);spec.loader.exec_module(browser)
  proof=b'synthetic browser observation';(self.root/'reports/browser-proof.txt').write_bytes(proof)
  item={'status':'PASS','artifact_sha256':self.r['sha256'],'evidence':'reports/browser-proof.txt','evidence_sha256':sha(proof)}
  for n in ['opus-crt-validation.json','portable-trust-validation.json']:self.put('reports/'+n,item)
  checks=[('unsigned_status_disclosed' if k=='trusted_authenticode' else 'windows_security_observed' if k=='windows_security_accepts' else k) for k in browser.CHECKS]
  rows={n:{'version':'synthetic-version','channel':'stable','windows_build':'10.0.22631','tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protections_unchanged':True,**{k:item for k in checks}} for n in browser.BROWSERS}
  self.put('reports/browser-acceptance.json',rows)
  return browser,rows
 def test_unsigned_browser_uses_disclosure_and_keeps_all_other_evidence(self):
  browser,rows=self.browser_fixture();self.assertEqual(browser.check(self.root),[])
  del rows['chrome']['unsigned_status_disclosed'];self.put('reports/browser-acceptance.json',rows);self.assertTrue(browser.check(self.root))
 def test_unsigned_browser_rejects_disabled_protections_and_wrong_hash(self):
  browser,rows=self.browser_fixture();rows['edge']['protections_unchanged']=False;self.put('reports/browser-acceptance.json',rows);self.assertTrue(browser.check(self.root))
  browser,rows=self.browser_fixture();rows['firefox']['hash_match']={**rows['firefox']['hash_match'],'artifact_sha256':'8'*64};self.put('reports/browser-acceptance.json',rows);self.assertTrue(browser.check(self.root))

 def test_unsigned_does_not_waive_production_environment(self):
  self.r['environment']='staging';self.save();self.assertTrue(gate.check(self.root))

 def test_raw_advisory_requires_exact_applicability_proof(self):
  finding={'advisory':{'id':'RUSTSEC-2099-9999'},'package':{'name':'fixture-only','version':'1.0'}}
  audit={'vulnerabilities':{'count':1,'list':[finding]}}
  audit_sha=self.put('reports/client-audit.json',audit);self.bind_audit()
  self.assertTrue(gate.check(self.root))
  proof=b'synthetic target/API review evidence, not a real advisory disposition'
  (self.root/'reports/security-proof.txt').write_bytes(proof)
  row={'advisory':'RUSTSEC-2099-9999','package':'fixture-only','version':'1.0','disposition':'NOT_AFFECTED_TARGET','package_fixed':False,'reason':'Synthetic fixture exercises exact source, target and evidence bindings only.','evidence':[{'path':'reports/security-proof.txt','sha256':sha(proof)}]}
  review={'schema_version':1,'status':'PASS','target':'x86_64-pc-windows-msvc','source':self.r['source'],'lock_sha256':self.r['lock_sha256'],'artifact_sha256':self.r['sha256'],'audit_sha256':audit_sha,'reviewer':'fixture-security-reviewer','findings':[row]}
  def save_review():
   self.r['security_applicability']={'path':'reports/security-applicability.json','sha256':self.put('reports/security-applicability.json',review)};self.save()
  save_review();self.assertEqual(gate.check(self.root),[])
  for field,value in [('disposition','LOW_RISK'),('disposition','UNKNOWN'),('package_fixed',True),('version','2.0')]:
   previous=row[field];row[field]=value;save_review();self.assertTrue(gate.check(self.root));row[field]=previous
  review['findings']=[row,row];save_review();self.assertTrue(gate.check(self.root))
  review['findings']=[row];review['target']='x86_64-unknown-linux-gnu';save_review();self.assertTrue(gate.check(self.root))
  review['target']='x86_64-pc-windows-msvc';save_review()
  (self.root/'reports/security-proof.txt').write_bytes(b'changed');self.assertTrue(gate.check(self.root))

 def test_malformed_or_missing_raw_audit_rejected(self):
  for audit in [{},{'vulnerabilities':{'count':False}},{'vulnerabilities':{'count':0,'list':[{}]}}]:
   self.put('reports/client-audit.json',audit);self.assertTrue(gate.check(self.root))

 def test_zero_count_audit_still_bound_to_source_target_and_bytes(self):
  for field,value in [('source',{'root':'f'*40}),('target','wasm32-unknown-unknown'),('client_audit_sha256','0'*64),('artifact_sha256','0'*64)]:
   self.bind_audit();v=json.loads((self.root/'reports/security-inputs.json').read_text());v[field]=value;self.put('reports/security-inputs.json',v);self.assertTrue(gate.check(self.root))
  self.bind_audit();self.put('reports/client-audit.json',{'vulnerabilities':{'count':0},'changed':'other report'});self.assertTrue(gate.check(self.root))

 def test_x86_pe_and_unknown_machine_are_rejected_even_with_matching_hash(self):
  p=self.root/'artifacts/customer/FilDesk.exe';original=p.read_bytes()
  for machine,magic in [(0x14c,0x10b),(0,0x20b)]:
   body=bytearray(original);struct.pack_into('<H',body,132,machine);struct.pack_into('<H',body,152,magic);p.write_bytes(body)
   self.r['sha256']=sha(body);self.save()
   candidate=json.loads((self.root/'reports/windows-release-candidate.json').read_text());candidate['artifacts']['customer']['sha256']=sha(body);self.put('reports/windows-release-candidate.json',candidate)
   errors=gate.check(self.root);self.assertTrue(any('AMD64' in e for e in errors),errors)
