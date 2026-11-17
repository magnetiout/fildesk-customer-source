import copy,json,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Gate(unittest.TestCase):
 def check(self,change=None):
  x=json.loads((ROOT/'reports/vps-post-cleanup-evidence.json').read_text())
  if change:change(x)
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'audit.json').write_text(json.dumps(x))
   r=subprocess.run(['python3',str(ROOT/'scripts/staging-go-gate.py'),str(p/'audit.json'),str(ROOT/'reports/staging-resource-probe.json'),'--output',str(p/'result.json')],capture_output=True)
   self.assertEqual(r.returncode,2);return json.loads((p/'result.json').read_text())
 def test_actual_blocks_missing_isolation(self):self.assertTrue(any('isolated runtime' in r for r in self.check()['reasons']))
 def test_low_ram_blocks(self):self.assertTrue(any('RAM' in r for r in self.check(lambda x:x['samples'][0]['memory'].update(MemAvailable=1))['reasons']))
 def test_health_blocks(self):self.assertTrue(any('HTTPS' in r for r in self.check(lambda x:x['health']['feekiller.com'].update(http_tls='500 0'))['reasons']))
 def test_ports_block(self):self.assertTrue(any('port conflict' in r for r in self.check(lambda x:x.update(listeners='tcp LISTEN 0 10 0.0.0.0:21116 0.0.0.0:*'))['reasons']))
if __name__=='__main__':unittest.main()
