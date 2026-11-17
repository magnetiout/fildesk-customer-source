import contextlib,io,json,pathlib,tempfile,types,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).parents[1]
source=(ROOT/'deployment/maintenance-unbacked-v2/fildesk-vps-remove-approved.sh').read_text().split("<<'FILDESK_PY'\n",1)[1].rsplit('\nFILDESK_PY',1)[0]
m=types.ModuleType('removal_test');exec(compile(source,'approved-removal','exec'),m.__dict__)
def app(n,c,s):return {'name':n,'pid':123,'pm2_env':{'name':n,'pm_cwd':c,'pm_exec_path':s,'status':'online'}}
def fixture():
 x={o:[app(n,*pair) for n,pair in targets.items()] for o,targets in m.APPS.items()}
 x['kado'][0]['pm2_env']['args']=['/var/www/teldex/oksid/server.py']
 for n,c in m.KEEP.items():x['root'].append(app(n,c,'/usr/bin/node'))
 return x
class Safety(unittest.TestCase):
 def test_valid_identity(self):m.validate_targets(fixture())
 def test_wrong_cwd_aborts(self):
  x=fixture();x['root'][0]['pm2_env']['pm_cwd']='/var/www/feekiller'
  with self.assertRaises(RuntimeError):m.validate_targets(x)
 def test_wrong_owner_aborts(self):
  x=fixture();x['root'].append(x['kado'].pop())
  with self.assertRaises(RuntimeError):m.validate_targets(x)
 def test_oksid_arg_aborts(self):
  x=fixture();x['kado'][0]['pm2_env']['args']=['/home/kado/server.py']
  with self.assertRaises(RuntimeError):m.validate_targets(x)
 def test_preserved_name_on_other_owner(self):
  x=fixture();x['root'].append(app('oksid','/srv/unknown','/usr/bin/python'))
  self.assertIn('oksid',[p['name'] for p in m.keep_map(x)['root']])
 def test_protected_pid_change_stops(self):
  x=fixture();baseline=m.keep_map(x);x['root'][-1]['pid']=999
  with patch.object(m,'lists',return_value=x):
   with self.assertRaisesRegex(RuntimeError,'PID'):m.guard(baseline,'','')
 def test_http_and_tls_failures(self):
  for value in ['500 0','200 60','302 0']:
   with patch.object(m,'call',return_value=value):
    with self.assertRaises(RuntimeError):m.health()
 def test_nonallowlist_rejected(self):
  for target in ['/home/kado/.oksid','/var/www/feekiller','/var/lib/postgresql','/usr/bin/python3.12','/']:
   with self.assertRaises(RuntimeError):m.check_tree(target)
 def test_link_root_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t);(p/'real').mkdir();(p/'link').symlink_to(p/'real',target_is_directory=True)
   with patch.object(m,'TREES',(str(p/'link'),)):
    with self.assertRaises(RuntimeError):m.check_tree(str(p/'link'))
 def test_fd_delete_preserves_external_symlink_target(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t);outside=p/'preserve';outside.mkdir();(outside/'data').write_text('keep')
   target=p/'approved';target.mkdir();(target/'a').write_text('delete');(target/'child').mkdir();(target/'child'/'b').write_text('delete')
   (target/'python').symlink_to(outside,target_is_directory=True)
   with patch.object(m,'TREES',(str(target),)):
    identity=m.check_tree(str(target));m.delete_tree(str(target),identity)
   self.assertFalse(target.exists());self.assertEqual((outside/'data').read_text(),'keep')
 def test_mount_aborts(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)/'approved';p.mkdir()
   with patch.object(m,'TREES',(str(p),)),patch.object(m,'mounts',return_value=[str(p/'mounted')]):
    with self.assertRaisesRegex(RuntimeError,'Mount'):m.check_tree(str(p))
 def test_inode_mismatch_aborts_before_delete(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)/'approved';p.mkdir();(p/'data').write_text('keep')
   with patch.object(m,'TREES',(str(p),)):
    with self.assertRaisesRegex(RuntimeError,'inode'):m.delete_tree(str(p),(-1,-1))
   self.assertTrue((p/'data').exists())
 def test_vhost_mapping_valid(self):
  m.validate_vhost_content(m.ENABLED[0],b'server_name taner.filteknoloji.com;\nproxy_pass http://127.0.0.1:3001;\nroot /var/www/taner/client/dist;')
  m.validate_vhost_content(m.ENABLED[1],b'server_name teldex.feekiller.com;\nproxy_pass http://127.0.0.1:5055/;\nproxy_pass http://localhost:3005;')
 def test_vhost_shared_domain_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'domains'):m.validate_vhost_content(m.ENABLED[0],b'server_name taner.filteknoloji.com filteknoloji.com;')
 def test_vhost_protected_upstream_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'upstream'):m.validate_vhost_content(m.ENABLED[0],b'server_name taner.filteknoloji.com;\nproxy_pass http://127.0.0.1:3003;')
 def test_nginx_failure_restores_only_target_config(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t);real=p/'available';link=p/'enabled';other=p/'other';real.write_text('taner');other.write_text('teldex');link.symlink_to(real)
   paths=(str(link),str(other),str(real));snap={}
   for q in [link,other,real]:
    s=q.lstat();snap[str(q)]={'bytes':None if q.is_symlink() else q.read_bytes(),'link':str(real) if q.is_symlink() else None,'inode':(s.st_dev,s.st_ino),'mode':s.st_mode&0o777,'uid':s.st_uid,'gid':s.st_gid}
   calls=[]
   def call(args):
    calls.append(args)
    if len(calls)==1:raise RuntimeError('test rejects changed configuration')
    return ''
   with patch.object(m,'VHOSTS',paths),patch.object(m,'call',side_effect=call),patch.object(m,'event'):
    with self.assertRaises(RuntimeError):m.disable_vhosts(snap)
   self.assertTrue(link.is_symlink());self.assertEqual(real.read_text(),'taner');self.assertEqual(other.read_text(),'teldex')
   self.assertEqual(sum(a==['/usr/bin/systemctl','reload','nginx'] for a in calls),1) # restored config only
 def test_check_mode_no_mutation(self):
  with patch.object(m,'lists',return_value=fixture()),patch.object(m,'startup_unit',return_value='unit'),patch.object(m,'nginx_fingerprint',return_value={}),patch.object(m,'vhost_snapshot',return_value={}),patch.object(m,'check_tree',return_value=(1,1)),patch.object(m,'metrics',return_value={}),patch.object(m,'event'),patch.object(m,'pm') as pm,patch.object(m,'delete_tree') as delete:
   m.execute(False);pm.assert_not_called();delete.assert_not_called()
 def test_first_health_error_stops_before_delete(self):
  with patch.object(m,'lists',return_value=fixture()),patch.object(m,'startup_unit',return_value='unit'),patch.object(m,'nginx_fingerprint',return_value={}),patch.object(m,'vhost_snapshot',return_value={}),patch.object(m,'check_tree',return_value=(1,1)),patch.object(m,'metrics',return_value={}),patch.object(m,'event'),patch.object(m,'guard',side_effect=RuntimeError('health')),patch.object(m,'delete_tree') as delete,patch.object(m,'pm') as pm:
   pm.side_effect=[json.dumps(fixture()['root']),'']
   with self.assertRaisesRegex(RuntimeError,'health'):m.execute(True)
   self.assertEqual(pm.call_args_list[-1].args,('root','stop','mexc-dashboard'));delete.assert_not_called()
 def test_startup_spec_preserves_environment(self):
  x=fixture()['root'][-1]['pm2_env'];x['env']={'SYNTHETIC':'fixture'}
  self.assertEqual(m.startup_spec(x)['env'],{'SYNTHETIC':'fixture'})
 def test_empty_kado_save_is_owner_scoped_and_rotated(self):
  with tempfile.TemporaryDirectory() as t:
   calls=[];p=pathlib.Path(t)
   def pm(owner,*args):
    calls.append((owner,args))
    if args==('jlist',):return '[]'
    if args==('save','--force'):
     (p/'dump.pm2').write_text('[]');(p/'dump.pm2.bak').write_text('[]');return ''
    self.fail('Unexpected PM2 mutation')
   with patch.object(m,'pm',side_effect=pm),patch.object(m,'home',return_value=t),patch.object(m,'event'):
    m.save_startup('kado',{})
   self.assertEqual(calls,[('kado',('jlist',)),('kado',('save','--force')),('kado',('save','--force'))])
 def test_env_change_aborts_guard(self):
  x=fixture();baseline=m.keep_map(x);specs=m.startup_hashes(x)
  x['root'][-1]['pm2_env']['env']={'CHANGED':'yes'}
  with patch.object(m,'lists',return_value=x):
   with self.assertRaisesRegex(RuntimeError,'configuration'):m.guard(baseline,'unit',{},specs)
 def test_script_has_no_backup_or_db_delete_gate(self):
  self.assertNotIn('review_required',source);self.assertNotIn('offhost-restore-receipt',source)
  self.assertNotIn('DROP DATABASE',source);self.assertNotIn('DROP ROLE',source)
  self.assertNotIn("'delete','all'",source);self.assertNotIn('reboot',source.replace("'startup_reboot_test'",''))
class EntryAndCluster(unittest.TestCase):
 def test_original_root_check_reproduces_socket_nameerror(self):
  old=(ROOT/'deployment/maintenance-unbacked/fildesk-vps-remove-approved.sh').read_text().split("<<'FILDESK_PY'\n",1)[1].rsplit('\nFILDESK_PY',1)[0]
  original=types.ModuleType('original');exec(compile(old,'original-embedded-python','exec'),original.__dict__)
  with patch.object(original.os,'geteuid',return_value=0),patch.object(original.sys,'argv',['removal','--check']):
   with self.assertRaisesRegex(NameError,"socket"):original.main()
 def test_cluster_instance_replaced_aborts_before_stop(self):
  import copy
  x=fixture();x['root'][0]['pm2_env']['exec_mode']='cluster_mode';changed=copy.deepcopy(x['root']);changed[0]['pid']=456
  with contextlib.ExitStack() as stack:
   stack.enter_context(patch.object(m,'lists',return_value=x))
   for name,value in [('startup_unit','unit'),('nginx_fingerprint',{}),('vhost_snapshot',{}),('check_tree',(1,1)),('metrics',{})]:stack.enter_context(patch.object(m,name,return_value=value))
   stack.enter_context(patch.object(m,'event'));pm=stack.enter_context(patch.object(m,'pm',return_value=json.dumps(changed)))
   with self.assertRaisesRegex(RuntimeError,'instance changed'):m.execute(True)
   self.assertEqual(pm.call_args_list[0].args,('root','jlist'));self.assertEqual(pm.call_count,1)
 def test_no_undefined_global_names(self):
  import symtable,builtins
  table=symtable.symtable(source,'removal','exec')
  defined={v.get_name() for v in table.get_symbols() if v.is_assigned() or v.is_imported() or v.is_namespace()}|set(dir(builtins))|{'__name__'}
  def walk(t):
   for symbol in t.get_symbols():
    if symbol.is_referenced() and symbol.is_global():self.assertIn(symbol.get_name(),defined)
   for child in t.get_children():walk(child)
  walk(table)
 def test_main_check_readonly_entrypoint(self):
  with contextlib.ExitStack() as stack:
   for target,kwargs in [('lists',{'return_value':fixture()}),('startup_unit',{'return_value':'unit'}),('nginx_fingerprint',{'return_value':{}}),('vhost_snapshot',{'return_value':{}}),('check_tree',{'return_value':(1,1)}),('metrics',{'return_value':{}})]:stack.enter_context(patch.object(m,target,**kwargs))
   stack.enter_context(patch.object(m.os,'geteuid',return_value=0));stack.enter_context(patch.object(m.socket,'gethostname',return_value=m.HOST))
   stack.enter_context(patch.object(m.sys,'argv',['removal','--check']))
   stack.enter_context(patch.object(m.os,'umask'));stack.enter_context(patch.object(m.os,'nice'))
   stack.enter_context(patch.object(m,'LOG',None))
   for name in ('pm','delete_tree','disable_vhosts','save_startup'):
    stack.enter_context(patch.object(m,name,side_effect=AssertionError('mutation '+name)))
   stack.enter_context(patch('builtins.open',side_effect=AssertionError('file write/open')))
   stack.enter_context(patch.object(pathlib.Path,'mkdir',side_effect=AssertionError('mkdir')))
   with contextlib.redirect_stdout(io.StringIO()):m.main()
   self.assertEqual(m.RESULT['status'],'CHECK PASS — no applications changed')
 def test_single_cluster_instance_accepted(self):
  x=fixture();x['root'][0]['pm2_env']['exec_mode']='cluster_mode';m.validate_targets(x)
 def test_ambiguous_cluster_instances_rejected(self):
  import copy
  x=fixture();x['root'][0]['pm2_env']['exec_mode']='cluster_mode';x['root'].append(copy.deepcopy(x['root'][0]))
  with self.assertRaisesRegex(RuntimeError,'Duplicate'):m.validate_targets(x)
 def test_apply_only_exact_owner_and_targets(self):
  import copy
  state=fixture();state['root'][0]['pm2_env']['exec_mode']='cluster_mode';calls=[]
  def pm(owner,*args):
   calls.append((owner,args))
   if args==('jlist',):return json.dumps(state[owner])
   name=args[1];self.assertIn(name,m.APPS[owner])
   if args[0]=='stop':
    for row in state[owner]:
     if row['name']==name:row['pm2_env']['status']='stopped';row['pid']=0
   elif args[0]=='delete':state[owner]=[p for p in state[owner] if p['name']!=name]
   else:self.fail('Unexpected mutation')
   return ''
  with contextlib.ExitStack() as stack:
   stack.enter_context(patch.object(m,'lists',side_effect=lambda:copy.deepcopy(state)))
   for name,value in [('startup_unit','unit'),('nginx_fingerprint',{}),('vhost_snapshot',{}),('check_tree',(1,1)),('metrics',{'disk_available_bytes':1,'available_ram_bytes':1,'swap_used_bytes':1})]:stack.enter_context(patch.object(m,name,return_value=value))
   for name in ('event','guard','save_startup','no_users_of_targets','disable_vhosts'):stack.enter_context(patch.object(m,name))
   delete=stack.enter_context(patch.object(m,'delete_tree'));stack.enter_context(patch.object(m,'pm',side_effect=pm))
   m.execute(True)
   self.assertEqual([c.args[0] for c in delete.call_args_list],list(m.TREES))
  actual=[(o,*args) for o,args in calls if args[0]!='jlist']
  self.assertEqual(actual,[(o,action,n) for o,n in [('root','mexc-dashboard'),('root','teldex-admin'),('kado','oksid'),('root','teldex')] for action in ('stop','delete')])
  self.assertEqual({p['name'] for p in state['root']},set(m.KEEP));self.assertEqual(state['kado'],[])
if __name__=='__main__':unittest.main()
