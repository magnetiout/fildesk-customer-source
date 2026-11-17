import importlib.util,pathlib,os,stat,tempfile,unittest,types,hashlib
from unittest.mock import patch
P=pathlib.Path
spec=importlib.util.spec_from_file_location('repair',P(__file__).resolve().parents[1]/'deployment/singapore-runtime-fix/repair.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Repair(unittest.TestCase):
 def test_umask_root_cause_and_explicit_correction(self):
  with tempfile.TemporaryDirectory() as t:
   p=P(t)/'release';old=os.umask(0o077)
   try:p.mkdir(mode=0o755)
   finally:os.umask(old)
   self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o700)
   before=p.stat();entry={'dev':before.st_dev,'ino':before.st_ino}
   real=os.fstat
   def root_stat(fd):
    s=real(fd);return types.SimpleNamespace(st_dev=s.st_dev,st_ino=s.st_ino,st_uid=0)
   with patch.object(m.os,'fstat',side_effect=root_stat):m.repair_directory(p,entry)
   self.assertEqual(stat.S_IMODE(p.stat().st_mode),0o711);self.assertEqual(p.stat().st_ino,before.st_ino)
 def test_symlink_directory_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=P(t)/'link';p.symlink_to(t)
   with self.assertRaises(OSError):m.repair_directory(p,{'dev':0,'ino':0})
 def test_wrong_inode_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(RuntimeError):m.repair_directory(t,{'dev':0,'ino':0})
 def test_receipt_exact_paths(self):
  with self.assertRaises(RuntimeError):m.validate_ledger([],{'/expected'})
 def test_receipt_duplicate_rejected(self):
  with self.assertRaises(RuntimeError):m.validate_ledger([{'path':'/a'},{'path':'/a'}],{'/a'})
 def test_ledger_bytes_and_inode_preserved(self):
  with tempfile.TemporaryDirectory() as t:
   p=P(t)/'helper';p.write_bytes(b'code');s=p.stat();e={'path':str(p),'dev':s.st_dev,'ino':s.st_ino,'directory':False,'sha256':hashlib.sha256(b'code').hexdigest()}
   with patch.object(m,'trusted',return_value=s),patch.object(m,'read',return_value=b'code'):m.validate_ledger([e],{str(p)})
   with patch.object(m,'trusted',return_value=s),patch.object(m,'read',return_value=b'changed'),self.assertRaises(RuntimeError):m.validate_ledger([e],{str(p)})
 def test_mount_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   s=P(t).stat();e={'path':t,'dev':s.st_dev,'ino':s.st_ino,'directory':True}
   with patch.object(m,'trusted',return_value=s),patch.object(m.os.path,'ismount',return_value=True),self.assertRaises(RuntimeError):m.validate_ledger([e],{t})
 def test_no_mutation_without_explicit_apply(self):
  with patch.object(m.sys,'argv',['repair.py']),patch.object(m,'cmd') as cmd,self.assertRaises(RuntimeError):m.main()
  cmd.assert_not_called()
 def test_failed_snapshot_before_any_command(self):
  with patch.object(m.sys,'argv',['repair.py','--apply']),patch.object(m.os,'geteuid',return_value=0),patch.object(m.socket,'gethostname',return_value='ubuntu-s-1vcpu-1gb-sgp1'),patch.object(m,'trusted'),patch.object(m,'read',return_value=b'bad manifest'),patch.object(m,'cmd') as cmd,patch.object(m.os,'umask'),self.assertRaises(RuntimeError):m.main()
  cmd.assert_not_called()
if __name__=='__main__':unittest.main()
