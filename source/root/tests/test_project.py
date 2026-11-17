import base64,importlib.util,json,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('configure',ROOT/'scripts/configure-client.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ReleaseSafety(unittest.TestCase):
    def config(self):return {'environment':'development','profile':'customer','id_server':'127.0.0.1:21116','relay_server':'127.0.0.1:21117','public_key':base64.b64encode(bytes(range(32))).decode()}
    def test_staging_profile_isolation(self):
        c=self.config();c['environment']='staging'
        self.assertIn('"FilDesk-Staging"',module.render(c))
        c['profile']='operator';self.assertIn('"FilDesk-Staging-Operator"',module.render(c))
        self.assertNotIn('"FilDesk-Dev"',module.render(c))
    def test_staging_requires_real_public_key(self):
        c=self.config();c.update(environment='staging',public_key='')
        with self.assertRaises(ValueError):module.validate(c)
    def test_customer_and_operator(self):
        c=self.config();self.assertIn('FilDesk-Dev',module.render(c));c['profile']='operator';self.assertIn('FilDesk-Dev-Operator',module.render(c))
    def test_windows_install_identity(self):
        import re
        for env in ["development", "production"]:
            for profile in ["customer", "operator"]:
                c=self.config();c["profile"]=profile
                if env=="production":
                    c.update(environment=env,id_server="support.example.net:21116",relay_server="support.example.net:21117")
                name=re.search(r'APP_NAME: &str = "([^"]+)"',module.render(c)).group(1)
                self.assertRegex(name,r"^[a-zA-Z0-9-]+$")
    def test_production_placeholders_refused(self):
        c=json.loads((ROOT/'config/production.example.json').read_text())
        with self.assertRaises(ValueError):module.validate(c)
    def test_private_key_refused(self):
        c=self.config();c['public_key']=base64.b64encode(bytes(range(64))).decode()
        with self.assertRaises(ValueError):module.validate(c)
    def test_known_dev_key_refused_in_production(self):
        c=self.config();c.update(environment='production',id_server='remote.filteknoloji.com:21116',relay_server='remote.filteknoloji.com:21117')
        # Test fixture hostname is never a production configuration.
        c['public_key']=json.loads((ROOT/'config/development-public-keys.json').read_text())[0]
        with self.assertRaises(ValueError):module.validate(c)
    def test_no_config_code_injection(self):
        for host in ['x\"; panic!(); //:21116','$(echo hacked):21116','http://host:21116','127.0.0.1:65536']:
            c=self.config();c['id_server']=host
            with self.assertRaises(ValueError):module.validate(c)
    def test_no_unknown_secret_fields(self):
        c=self.config();c['private_key']='DO-NOT-ACCEPT'
        with self.assertRaises(ValueError):module.validate(c)
    def test_source_pins(self):
        for name,pin in json.loads((ROOT/'config/upstream.lock.json').read_text()).items():
            # HEAD may advance to local Fil commit; pinned base must remain an ancestor.
            subprocess.run(['git','-C',str(ROOT/name),'merge-base','--is-ancestor',pin['commit'],'HEAD'],check=True)
            self.assertEqual(subprocess.check_output(['git','-C',str(ROOT/name),'rev-parse','HEAD:libs/hbb_common'],text=True).strip(),pin['submodules'].split()[0])
            self.assertIn('GNU AFFERO GENERAL PUBLIC LICENSE',(ROOT/name/('LICENCE' if name=='client' else 'LICENSE')).read_text())
if __name__=='__main__':unittest.main(verbosity=2)
