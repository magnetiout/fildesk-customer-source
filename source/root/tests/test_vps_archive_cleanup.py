import importlib.util, pathlib, tempfile, os, unittest, hashlib
p=pathlib.Path(__file__).resolve().parents[1]/'deployment/maintenance-backups/cleanup_template.py'
s=importlib.util.spec_from_file_location('cleanup',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ArchiveGuards(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=pathlib.Path(self.tmp.name)/'archive.tar.gz';self.p.write_bytes(b'synthetic archive');x=self.p.stat()
  self.e={'path':str(self.p),'dev':x.st_dev,'ino':x.st_ino,'size':x.st_size,'mtime_ns':x.st_mtime_ns,'sha256':hashlib.sha256(self.p.read_bytes()).hexdigest()}
 def tearDown(self):self.tmp.cleanup()
 def validate(self):
  d,f=m.validated(self.e);os.close(f);os.close(d)
 def test_valid_readonly(self):self.validate();self.assertTrue(self.p.exists())
 def test_hash_mismatch(self):
  self.e['sha256']='0'*64
  with self.assertRaises(RuntimeError):self.validate()
 def test_modified(self):
  self.p.write_bytes(b'changed')
  with self.assertRaises(RuntimeError):self.validate()
 def test_symlink(self):
  target=self.p.with_name('target');self.p.rename(target);self.p.symlink_to(target)
  with self.assertRaises(OSError):self.validate()
 def test_parent_symlink(self):
  link=self.p.parent/'link';link.symlink_to(self.p.parent,target_is_directory=True);self.e['path']=str(link/self.p.name)
  with self.assertRaises(OSError):self.validate()
 def test_hardlink(self):
  os.link(self.p,self.p.with_name('alias'))
  with self.assertRaises(RuntimeError):self.validate()
 def test_inode_changed(self):
  self.e['ino']+=1
  with self.assertRaises(RuntimeError):self.validate()
 def test_no_traversal(self):
  with self.assertRaises(RuntimeError):m.parent_fd('/tmp/../etc/passwd')
 def test_fifo_nonblocking(self):
  self.p.unlink();os.mkfifo(self.p)
  with self.assertRaises(RuntimeError):self.validate()
 def test_open_elsewhere(self):
  m.MANIFEST=[self.e];proc=self.p.parent/'proc'/'123456789';proc.mkdir(parents=True)
  (proc/'cmdline').write_bytes(b'test\0');(proc/'fd').mkdir();(proc/'fd'/'3').symlink_to(self.p)
  try:
   with self.assertRaisesRegex(RuntimeError,'open in another process'):m.idle(proc.parent)
  finally:m.MANIFEST=[]
if __name__=='__main__':unittest.main()
