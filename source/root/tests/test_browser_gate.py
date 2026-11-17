import importlib.util,json,pathlib,tempfile,unittest,hashlib
R=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('browser_gate',R/'scripts/browser-release-gate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BrowserGate(unittest.TestCase):
 def test_missing_evidence_blocked(self):
  with tempfile.TemporaryDirectory(dir=R/'build') as d:self.assertTrue(m.check(pathlib.Path(d)))
 def test_fixture_hash_binding_and_no_unsigned_waiver(self):
  # Synthetic evidence in temporary fixtures only; never writes real acceptance reports.
  with tempfile.TemporaryDirectory(dir=R/'build') as d:
   root=pathlib.Path(d);reports=root/'reports';reports.mkdir();proof=b'synthetic unit fixture';(reports/'proof.txt').write_bytes(proof)
   item={'status':'PASS','artifact_sha256':'a'*64,'evidence':'reports/proof.txt','evidence_sha256':hashlib.sha256(proof).hexdigest()}
   release={'sha256':'a'*64,'environment':'production','profile':'customer','filename':'FilDesk.exe','signature_status':'Valid','publisher':'TEST FIXTURE','trusted_public_ca':True,'verification':item}
   def write(n,o):(reports/n).write_text(json.dumps(o))
   write('signed-distribution.json',release)
   for name in ('opus-crt-validation.json','portable-trust-validation.json'):write(name,item)
   rows={b:dict(version='test-fixture',channel='stable',windows_build='fixture',tested_at='fixture',protections_unchanged=True,**{key:item for key in m.CHECKS}) for b in m.BROWSERS};write('browser-acceptance.json',rows)
   self.assertEqual(m.check(root),[])
   release['signature_status']='NotSigned';write('signed-distribution.json',release);self.assertTrue(m.check(root))
   release['signature_status']='Valid';write('signed-distribution.json',release)
   rows['chrome']['hash_match']={**item,'artifact_sha256':'b'*64};write('browser-acceptance.json',rows);self.assertTrue(m.check(root))
   rows['chrome']['hash_match']=item;write('browser-acceptance.json',rows);(reports/'proof.txt').write_bytes(b'tampered');self.assertTrue(m.check(root))
