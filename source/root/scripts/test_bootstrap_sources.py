import importlib.util,json,pathlib,subprocess,tempfile,unittest
S=pathlib.Path(__file__).with_name('bootstrap-sources.py');spec=importlib.util.spec_from_file_location('bootstrap',S);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class BootstrapTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name);(self.root/'config').mkdir();self.calls=[]
  self.pins={n:{'url':'https://github.com/magnetiout/fil-remote-'+n+'.git','tag':'pala/security-source-20261015','commit':'a'*40,'submodules':'','source_format':M.SANITIZED}for n in ['client','server']}
 def write(self): (self.root/'config/upstream.lock.json').write_text(json.dumps(self.pins))
 def runner(self,args,**kw):
  self.calls.append(args)
  if 'clone'in args:
   d=pathlib.Path(args[-1]);(d/'libs/hbb_common/src').mkdir(parents=True);(d/'libs/hbb_common/Cargo.toml').write_text('[package]\n');(d/'libs/hbb_common/src/lib.rs').write_text('')
  out='a'*40 if 'rev-parse'in args else ''
  return subprocess.CompletedProcess(args,0,out,'')
 def test_sanitized_skips_legacy(self):
  self.write();M.restore(self.root,self.runner);flat=' '.join(' '.join(c)for c in self.calls);self.assertNotIn('submodule',flat);self.assertNotIn('apply',flat);self.assertNotIn('rename',flat);self.assertNotIn('switch',flat)
 def test_unknown_format_preflight(self):
  self.pins['server']['source_format']='wrong';self.write()
  with self.assertRaises(ValueError):M.restore(self.root,self.runner)
  self.assertEqual(self.calls,[])
 def test_existing_destination_preflight(self):
  (self.root/'server').symlink_to(self.root/'missing');self.write()
  with self.assertRaises(ValueError):M.restore(self.root,self.runner)
  self.assertEqual(self.calls,[])
 def test_wrong_sha(self):
  self.pins['client']['commit']='b'*40;self.write()
  with self.assertRaises(ValueError):M.restore(self.root,self.runner)
 def test_missing_common(self):
  self.write()
  def run(a,**k):
   r=self.runner(a,**k)
   if 'clone'in a:(pathlib.Path(a[-1])/'libs/hbb_common/src/lib.rs').unlink()
   return r
  with self.assertRaises(ValueError):M.restore(self.root,run)
 def test_gitlink_refusal(self):
  self.write()
  def run(a,**k):
   r=self.runner(a,**k)
   if 'ls-tree'in a:r.stdout='160000 commit '+ 'b'*40+'\tlibs/hbb_common'
   return r
  with self.assertRaises(ValueError):M.restore(self.root,run)
 def test_legacy_kept(self):
  for p in self.pins.values():p.pop('source_format')
  self.write();M.restore(self.root,self.runner);flat=' '.join(' '.join(c)for c in self.calls);self.assertIn('submodule update --init --recursive',flat);self.assertIn('remote rename origin upstream',flat)
 def test_credential_url_refusal(self):
  self.pins['client']['url']='https://token@github.com/magnetiout/client.git';self.write()
  with self.assertRaises(ValueError):M.restore(self.root,self.runner)
  self.assertEqual(self.calls,[])
 def test_actual_two_local_clones(self):
  pub=pathlib.Path(__file__).resolve().parents[2]
  for n in self.pins:
   src=pub/n;self.pins[n]['commit']=subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()
  self.write();calls=[]
  def run(a,**k):
   calls.append(a)
   if 'clone'in a:a=a.copy();a[-2]=str(pub/pathlib.Path(a[-1]).name)
   return subprocess.run(a,**k)
  M.restore(self.root,run)
  for n in self.pins:self.assertTrue((self.root/n/'libs/hbb_common/src/lib.rs').is_file())
  self.assertFalse(any('apply'in a or'submodule'in a for a in calls))
if __name__=='__main__':unittest.main()
