import importlib.util,pathlib,os,tempfile,unittest,hashlib,json
from unittest.mock import patch
R=pathlib.Path(__file__).resolve().parents[1]
def load(n):
 s=importlib.util.spec_from_file_location(n,R/'deployment/singapore-systemd-v2'/f'{n}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('install');g=load('namespace_guard')
class Guards(unittest.TestCase):
 def test_host_namespace_rejected(self):
  with self.assertRaises(RuntimeError):g.validate('hbbs',{'boot_id':'b','netns':'host'},{'boot_id':'b','netns':'host'},['lo'])
 def test_boot_change_rejected(self):
  with self.assertRaises(RuntimeError):g.validate('hbbs',{'boot_id':'old','netns':'host'},{'boot_id':'new','netns':'private'},['lo'])
 def test_external_interface_rejected(self):
  with self.assertRaises(RuntimeError):g.validate('hbbs',{'boot_id':'b','netns':'host'},{'boot_id':'b','netns':'private'},['eth0','lo'])
 def test_peer_mismatch_rejected(self):
  with self.assertRaises(RuntimeError):g.validate('hbbr',{'boot_id':'b','netns':'host'},{'boot_id':'b','netns':'private'},['lo'],{'boot_id':'b','netns':'other'})
 def test_shared_private_accepted(self):
  cur={'boot_id':'b','netns':'private'};g.validate('hbbr',{'boot_id':'b','netns':'host'},cur,['lo'],cur)
 def test_untrusted_parent_rejected(self):
  with self.assertRaises(RuntimeError):m.trusted_dir('/tmp')
 def test_symlink_parent_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)/'link';p.symlink_to('/root')
   with self.assertRaises((OSError,RuntimeError)):m.trusted_dir(str(p))
class Rollback(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=pathlib.Path(self.tmp.name);self.dest=self.p/'new';self.file=self.dest/'bin';self.keep=self.p/'existing';self.keep.write_text('keep')
  # Test only transaction IO in a disposable unprivileged directory; production remains root-only.
  self.patches=[patch.object(m,'OWNER',os.getuid()),patch.object(m,'ALLOWED',{str(self.dest),str(self.file)}),patch.object(m,'trusted_dir',side_effect=lambda p:os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW))]
  for p in self.patches:p.start()
  self.tx=m.Transaction(self.p/'receipt.json')
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def create(self):self.tx.create(str(self.dest));self.tx.create(str(self.file),b'verified')
 def test_directory_final_mode_survives_restrictive_umask(self):
  old=os.umask(0o077)
  try:self.create()
  finally:os.umask(old)
  self.assertEqual(self.dest.stat().st_mode&0o777,0o755)
  self.tx.rollback()
 def test_failure_rolls_back_only_created(self):
  try:
   self.create();raise RuntimeError('injected validation failure')
  except RuntimeError:self.tx.rollback()
  self.assertFalse(self.dest.exists());self.assertEqual(self.keep.read_text(),'keep');self.assertEqual(json.loads((self.p/'receipt.json').read_text())['phase'],'ROLLED_BACK')
 def test_existing_never_overwritten(self):
  self.dest.mkdir()
  with self.assertRaises(FileExistsError):self.tx.create(str(self.dest))
  self.assertEqual(self.tx.entries,[])
 def test_changed_content_preserved(self):
  self.create();self.file.write_bytes(b'changed')
  with self.assertRaises(RuntimeError):self.tx.rollback()
  self.assertEqual(self.file.read_bytes(),b'changed')
 def test_replacement_symlink_preserved(self):
  self.create();self.file.unlink();self.file.symlink_to(self.keep)
  with self.assertRaises(RuntimeError):self.tx.rollback()
  self.assertEqual(self.keep.read_text(),'keep')
 def test_mount_rejected(self):
  self.create()
  with patch.object(m,'mountpoints',return_value=[str(self.file)]):
   with self.assertRaises(RuntimeError):self.tx.rollback()
  self.assertTrue(self.file.exists())
 def test_foreign_new_file_not_recursively_removed(self):
  self.create();(self.dest/'foreign').write_text('keep')
  with self.assertRaises(OSError):self.tx.rollback()
  self.assertEqual((self.dest/'foreign').read_text(),'keep')
 def test_nonallowlist_rejected(self):
  with self.assertRaises(RuntimeError):self.tx.create(str(self.keep),b'bad')

class UnitCollisions(unittest.TestCase):
 def fixture(self,**changes):
  props=dict(LoadState='loaded',ActiveState='inactive',FragmentPath='',SourcePath='',Transient='no',ControlGroup='',UnitFileState='',DropInPaths='')
  props.update(changes)
  return ''.join(k+'='+v+'\n' for k,v in props.items()).encode()
 def test_implicit_exact_slice_accepted(self):
  m.validate_unit_state('fildesk-staging.slice',self.fixture())
 def test_absent_services_accepted(self):
  for name in m.UNITS:m.validate_unit_state(name,self.fixture(LoadState='not-found'))
 def test_loaded_services_and_other_slice_rejected(self):
  for name in (*m.UNITS[1:],'other.slice'):
   with self.subTest(name=name),self.assertRaises(RuntimeError):m.validate_unit_state(name,self.fixture())
 def test_unsafe_slice_properties_rejected(self):
  for key,value in [('ActiveState','active'),('ActiveState','failed'),('Transient','yes'),('FragmentPath','/etc/custom'),('SourcePath','/run/custom'),('ControlGroup','/fildesk.slice'),('UnitFileState','static'),('DropInPaths','/etc/custom.conf'),('LoadState','error')]:
   with self.subTest(key=key,value=value),self.assertRaises(RuntimeError):m.validate_unit_state(m.UNITS[0],self.fixture(**{key:value}))
 def test_missing_duplicate_unknown_properties_rejected(self):
  raw=self.fixture()
  for data in [raw.replace(b'Transient=no\n',b''),raw+b'LoadState=loaded\n',raw+b'Unknown=\n',b'']:
   with self.subTest(data=data),self.assertRaises(RuntimeError):m.validate_unit_state(m.UNITS[0],data)
 def run_check(self,root,existing=None):
  def call(args):
   self.assertEqual(args[:2],['systemctl','show'])
   return self.fixture(**({} if args[2]==m.UNITS[0] else {'LoadState':'not-found'}))
  with patch.object(m,'unit_search_paths',return_value={root}),patch.object(m.os.path,'lexists',side_effect=lambda p:p==existing),patch.object(m,'call',side_effect=call),patch.object(m,'trusted_dir',side_effect=lambda _:os.open(root,os.O_RDONLY|os.O_DIRECTORY)):
   m.no_existing()
 def test_preflight_empty_implicit_is_read_only(self):
  with tempfile.TemporaryDirectory() as d:
   self.run_check(d);self.assertEqual(list(pathlib.Path(d).iterdir()),[])
 def test_unit_files_symlinks_and_dropins_rejected(self):
  for name in m.UNITS:
   for kind in ('file','dangling-symlink','dropin'):
    with self.subTest(name=name,kind=kind),tempfile.TemporaryDirectory() as d:
     p=pathlib.Path(d)/(name+('.d' if kind=='dropin' else ''))
     if kind=='file':p.write_text('preserve')
     elif kind=='dropin':p.mkdir()
     else:p.symlink_to('/missing-fildesk-target')
     with self.assertRaises(RuntimeError):self.run_check(d)
     self.assertTrue(os.path.lexists(p))
 def test_state_install_and_runtime_rejected(self):
  for target in (*m.ALLOWED,'/var/lib/fildesk-staging','/var/lib/private/fildesk-staging','/run/fildesk-staging-hbbs','/run/fildesk-staging-hbbr'):
   with self.subTest(target=target),tempfile.TemporaryDirectory() as d,self.assertRaises(RuntimeError):self.run_check(d,target)
 def test_effective_paths_and_standard_paths_checked(self):
  with patch.object(m,'call',return_value=b'/custom/system/units\n'):
   paths=m.unit_search_paths()
  self.assertIn('/custom/system/units',paths)
  self.assertIn('/run/systemd/transient',paths)
  self.assertIn('/etc/systemd/system',paths)
 def test_empty_or_relative_lookup_rejected(self):
  for raw in (b'',b'relative\n',b'/etc/../tmp\n'):
   with patch.object(m,'call',return_value=raw),self.assertRaises(RuntimeError):m.unit_search_paths()
 def test_transaction_create_call_arity(self):
  import ast
  tree=ast.parse((R/'deployment/singapore-systemd-v2/install.py').read_text())
  for node in ast.walk(tree):
   if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='create':
    self.assertIn(len(node.args),(1,2))
  # Both helper files must be installed using the exact approved names.
  self.assertIn("for n in ('namespace_guard.py','namespace_setup.py'):tx.create(DEST+'/'+n,data[n])",(R/'deployment/singapore-systemd-v2/install.py').read_text())
if __name__=='__main__':unittest.main()
