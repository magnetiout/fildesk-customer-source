import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch, MagicMock
import json, types

spec=importlib.util.spec_from_file_location('maintenance',Path(__file__).parents[1]/'deployment/maintenance/fildesk-vps-maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def app(name,cwd,script):
 return {'name':name,'pid':123,'pm2_env':{'pm_cwd':cwd,'pm_exec_path':script,'status':'online'}}

def fixture():
 x={'root':[],'kado':[]}
 for n,(o,c,s) in m.APPS.items():x[o].append(app(n,c,s))
 for n in m.KEEP:x['root'].append(app(n,'/var/www/'+n,'/usr/bin/node'))
 return x

class Guards(unittest.TestCase):
 def test_exact_app_mapping(self):m.validate_apps(fixture())
 def test_mismatched_script_fails(self):
  x=fixture();x['root'][0]['pm2_env']['pm_exec_path']='/var/www/feekiller/index.js'
  with self.assertRaises(RuntimeError):m.validate_apps(x)
 def test_duplicate_app_fails(self):
  x=fixture();x['root'].append(x['root'][0])
  with self.assertRaises(RuntimeError):m.validate_apps(x)
 def test_protected_offline_fails(self):
  x=fixture();x['root'][-1]['pm2_env']['status']='stopped'
  with self.assertRaises(RuntimeError):m.validate_apps(x)
 def test_unknown_apps_are_protected(self):
  x=fixture();x['root'].append(app('unidentified','/srv/unknown','/usr/bin/node'))
  self.assertIn('unidentified',[p['name'] for p in m.protected(x)['root']])
 def test_private_backup_excludes_protected_apps(self):
  x=m.selected(fixture())
  self.assertEqual({p['name'] for p in x['root']},{'mexc-dashboard','teldex-admin','teldex'})
  self.assertEqual([p['name'] for p in x['kado']],['oksid'])
 def test_same_name_wrong_owner_stays_protected(self):
  x=fixture();x['root'].append(app('oksid','/srv/unidentified','/usr/bin/python'))
  self.assertIn('oksid',[p['name'] for p in m.protected(x)['root']])
  self.assertNotIn('oksid',[p['name'] for p in m.selected(x)['root']])
 def test_http_failure_aborts(self):
  with patch.object(m,'call',return_value='503 0'):
   with self.assertRaises(RuntimeError):m.health()
 def test_tls_failure_aborts(self):
  with patch.object(m,'call',return_value='200 60'):
   with self.assertRaises(RuntimeError):m.health()
 def test_subprocess_error_is_redacted(self):
  result=subprocess.CompletedProcess(['tool'],1,b'secret-output',b'password=secret')
  with patch.object(m.subprocess,'run',return_value=result):
   with self.assertRaises(RuntimeError) as e:m.call(['/bin/tool'])
  self.assertNotIn('secret',str(e.exception))
 def test_wrong_host_never_initializes_state(self):
  with patch.object(m.sys,'argv',['tool','verify']),patch.object(m.os,'geteuid',return_value=0),patch.object(m.socket,'gethostname',return_value='other'),patch.object(m,'state_init') as init:
   with self.assertRaises(RuntimeError):m.main()
   init.assert_not_called()
 def test_nonroot_never_initializes_state(self):
  with patch.object(m.sys,'argv',['tool','backup']),patch.object(m.os,'geteuid',return_value=998),patch.object(m,'state_init') as init:
   with self.assertRaises(RuntimeError):m.main()
   init.assert_not_called()
 def test_wrapper_rejects_developer_directory(self):
  base=Path(__file__).parents[1]/'deployment/maintenance'
  for name in ['backup','remove','verify']:
   p=subprocess.run(['bash',str(base/f'fildesk-vps-{name}.sh')],capture_output=True,text=True)
   self.assertNotEqual(p.returncode,0);self.assertIn('install reviewed files',p.stderr)
 def test_removal_draft_has_no_mutators(self):
  import inspect
  text=inspect.getsource(m.remove)
  for token in ["'stop'","'delete'","'restart'",'rmtree','unlink','reload','DROP']:
   self.assertNotIn(token,text)

class ReviewGuards(unittest.TestCase):
 def invoke(self, review, inventory_hash):
  state=MagicMock();entry=state.__truediv__.return_value
  entry.read_text.return_value=json.dumps(review)
  entry.is_symlink.return_value=False
  entry.stat.return_value=types.SimpleNamespace(st_uid=0,st_mode=0o100600)
  with patch.object(m,'STATE',state),patch.object(m,'digest',return_value=inventory_hash):
   return m.review_required()
 def test_inventory_hash_is_pinned(self):
  with self.assertRaisesRegex(RuntimeError,'inventory hash'):self.invoke({},'0'*64)
 def test_preliminary_scope_required(self):
  with self.assertRaisesRegex(RuntimeError,'review scope'):self.invoke({},m.EXPECTED_INVENTORY_SHA)
 def test_oksid_extra_required(self):
  with self.assertRaisesRegex(RuntimeError,'Oksid'):self.invoke({'backup_scope':'online-preliminary-no-removal'},m.EXPECTED_INVENTORY_SHA)
 def test_oksid_is_backup_only(self):
  self.assertIn('/home/kado/.oksid',m.BACKUP_TREES)
  self.assertNotIn('/home/kado/.oksid',m.TREES)
 def test_no_removal_review_bypass(self):
  import inspect
  self.assertIn('Final removal NOT RELEASED',inspect.getsource(m.remove))

if __name__=='__main__':unittest.main()
