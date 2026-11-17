"""Synthetic local files only. Passing fixtures never claim real Windows execution."""
import copy,datetime,hashlib,importlib.util,json,pathlib,tempfile,unittest
R=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('windows_gate',R/'scripts/windows-release-gate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class WindowsGate(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);(self.root/'reports').mkdir();self.now=datetime.datetime.now(datetime.timezone.utc);self.date=self.now.isoformat();self.arts={}
  (self.root/'client').mkdir();(self.root/'client/Cargo.lock').write_bytes(b'SYNTHETIC UNIT LOCK');self.lock=hashlib.sha256(b'SYNTHETIC UNIT LOCK').hexdigest()
  for p in ['customer','operator']:
   path='artifacts/'+p+'/FilDesk.exe';f=self.root/path;f.parent.mkdir(parents=True);f.write_bytes(('MZ SYNTHETIC UNIT ARTIFACT '+p).encode());self.arts[p]={'profile':p,'version':'1.5.0-dev','sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'path':path,'source':{'root':'a'*40,'client':'b'*40,'server':'c'*40},'lock_sha256':self.lock,'built_at':(self.now-datetime.timedelta(hours=1)).isoformat()}
  self.candidate={'schema_version':1,'kind':'fildesk-windows-candidate','artifacts':self.arts};self.write('windows-release-candidate.json',self.candidate)
  self.bound={p:{k:a[k] for k in ['sha256','version','profile','source','lock_sha256']} for p,a in self.arts.items()}
  self.data={'schema_version':1,'kind':'fildesk-windows-acceptance','tester_id':'qa-alice','devices':[{'id':'WIN10-LAB-A','windows_release':'10','windows_build':'10.0.19045'},{'id':'WIN11-LAB-B','windows_release':'11','windows_build':'10.0.26100'}],'cases':{}}
  for case in m.REQUIRED:
   record={'schema_version':1,'kind':'fildesk-windows-case','execution':'windows-device','case_id':case,'status':'PASS','artifacts':self.bound,'tested_at':self.date,'tester_id':'qa-alice','device_ids':['WIN10-LAB-A','WIN11-LAB-B'],'steps':'Synthetic unit fixture steps for '+case,'observed':'Synthetic unit fixture observations for '+case}
   self.write(case+'.json',record);b=(self.root/'reports'/ (case+'.json')).read_bytes();self.data['cases'][case]={'status':'PASS','artifacts':copy.deepcopy(self.bound),'tested_at':self.date,'device_ids':['WIN10-LAB-A','WIN11-LAB-B'],'evidence':'reports/'+case+'.json','evidence_sha256':hashlib.sha256(b).hexdigest()}
  self.save()
 def tearDown(self):self.tmp.cleanup()
 def write(self,name,value):(self.root/'reports'/name).write_text(json.dumps(value))
 def save(self):self.write('windows-acceptance.json',self.data)
 def rejected(self):self.assertTrue(m.check(self.root))
 def mutate_proof(self,fn):
  item=self.data['cases']['consent'];p=self.root/item['evidence'];d=json.loads(p.read_text());fn(d);p.write_text(json.dumps(d));item['evidence_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();self.save()
 def test_complete_synthetic_fixture_schema_only(self):self.assertEqual(m.check(self.root),[])
 def test_missing_candidate_and_actual_evidence_blocked(self):
  with tempfile.TemporaryDirectory() as t:self.assertTrue(m.check(pathlib.Path(t)))
 def test_old_flat_pass_strings_rejected(self):self.write('windows-acceptance.json',{k:{'status':'PASS','evidence':'some report'} for k in m.REQUIRED});self.rejected()
 def test_all_original_required_cases_preserved(self):
  self.assertEqual(len(m.REQUIRED),14)
  for case in m.REQUIRED:
   item=self.data['cases'].pop(case);self.save();self.rejected();self.data['cases'][case]=item
 def test_missing_version_or_bad_schema_rejected(self):
  self.data['schema_version']=2;self.save();self.rejected()
 def test_current_lock_mismatch_rejected(self):
  (self.root/'client/Cargo.lock').write_bytes(b'changed');self.rejected()
 def test_candidate_actual_bytes_hash_mismatch(self):
  (self.root/self.arts['operator']['path']).write_bytes(b'changed');self.rejected()
 def test_case_artifact_source_lock_profile_version_mismatch(self):
  for key,value in [('sha256','e'*64),('source',{'root':'e'*40}),('lock_sha256','f'*64),('profile','operator'),('version','other')]:
   old=copy.deepcopy(self.data['cases']['consent']['artifacts']['customer'][key]);self.data['cases']['consent']['artifacts']['customer'][key]=value;self.save();self.rejected();self.data['cases']['consent']['artifacts']['customer'][key]=old
 def test_wrong_case_tester_device_timestamp_or_execution_record(self):
  for key,value in [('case_id','auth_success'),('tester_id','another-tester'),('device_ids',['WIN11-LAB-B']),('tested_at','2000-01-01T00:00:00Z'),('execution','synthetic'),('status','FAIL')]:
   original=(self.root/'reports/consent.json').read_text();self.mutate_proof(lambda d:d.update({key:value}));self.rejected();(self.root/'reports/consent.json').write_text(original);self.data['cases']['consent']['evidence_sha256']=hashlib.sha256(original.encode()).hexdigest();self.save()
 def test_blank_or_placeholder_observation_rejected(self):
  self.mutate_proof(lambda d:d.update(observed=''));self.rejected()
 def test_missing_or_tampered_evidence_file(self):
  p=self.root/'reports/consent.json';p.write_bytes(b'tampered');self.rejected();p.unlink();self.rejected()
 def test_plain_or_empty_hashed_evidence_is_not_execution(self):
  item=self.data['cases']['consent'];p=self.root/item['evidence'];p.write_text('PASS');item['evidence_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();self.save();self.rejected()
 def test_copied_case_evidence_rejected(self):
  self.data['cases']['consent']['evidence']=self.data['cases']['auth_success']['evidence'];self.data['cases']['consent']['evidence_sha256']=self.data['cases']['auth_success']['evidence_sha256'];self.save();self.rejected()
 def test_traversal_absolute_and_backslash_paths_rejected(self):
  for path in ['reports/../outside','/etc/passwd','reports\\outside']:
   self.data['cases']['consent']['evidence']=path;self.save();self.rejected()
 def test_evidence_and_parent_symlink_rejected(self):
  p=self.root/'reports/consent.json';content=p.read_bytes();p.unlink();out=self.root/'elsewhere';out.write_bytes(content);p.symlink_to(out);self.rejected()
  p.unlink();sub=self.root/'real';sub.mkdir();(sub/'proof').write_bytes(content);(self.root/'reports/link').symlink_to(sub,target_is_directory=True);self.data['cases']['consent']['evidence']='reports/link/proof';self.save();self.rejected()
 def test_candidate_artifact_symlink_rejected(self):
  p=self.root/self.arts['customer']['path'];b=p.read_bytes();p.unlink();out=self.root/'another.exe';out.write_bytes(b);p.symlink_to(out);self.rejected()
 def test_identity_os_and_date_fail_closed(self):
  for fn in [lambda d:d.update(tester_id='TODO'),lambda d:d['devices'][1].update(windows_release='10'),lambda d:d['devices'][1].update(id='WIN10-LAB-A'),lambda d:d['cases']['consent'].update(tested_at='2000-01-01T00:00:00Z'),lambda d:d['cases']['consent'].update(tested_at='2099-01-01T00:00:00Z'),lambda d:d['cases']['consent'].update(tested_at='2026-01-01T00:00:00')]:
   old=copy.deepcopy(self.data);fn(self.data);self.save();self.rejected();self.data=old
 def test_malformed_json_and_wrong_top_types(self):
  for raw in ['null','[]','true','{']:(self.root/'reports/windows-acceptance.json').write_text(raw);self.rejected()
if __name__=='__main__':unittest.main()
