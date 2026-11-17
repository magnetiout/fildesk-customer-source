"""Reproduce Windows core.autocrlf=true without requiring a Windows host."""
import json, os, pathlib, subprocess, sys, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class SourceCheckoutTests(unittest.TestCase):
    def test_binary_patch_bytes_survive_windows_style_checkout(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='checkout-test-') as temp:
            base = pathlib.Path(temp)
            origin, clone = base/'origin', base/'clone'
            origin.mkdir()
            def git(*args):
                return subprocess.run(['git', *map(str,args)], check=True, capture_output=True)
            git('init', origin)
            (origin/'branding/patches').mkdir(parents=True)
            (origin/'.gitattributes').write_bytes((ROOT/'.gitattributes').read_bytes())
            patch = (ROOT/'branding/patches/client.patch').read_bytes()
            (origin/'branding/patches/client.patch').write_bytes(patch)
            git('-C', origin, 'add', '.')
            git('-C', origin, '-c', 'user.name=Checkout test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
            git('-c', 'core.autocrlf=true', 'clone', origin, clone)
            self.assertEqual((clone/'branding/patches/client.patch').read_bytes(), patch)
            self.assertIn(b'GIT binary patch\n', patch)

    def test_actual_bootstrap_pins_lf_despite_windows_native_eol(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='bootstrap-eol-test-') as temp:
            base = pathlib.Path(temp)
            upstream, fixture = base/'upstream', base/'fixture'
            upstream.mkdir(); (fixture/'scripts').mkdir(parents=True); (fixture/'config').mkdir()
            def git(*args):
                return subprocess.check_output(['git', *map(str,args)], stderr=subprocess.PIPE).decode().strip()
            git('init', upstream)
            (upstream/'.gitattributes').write_bytes(b'* text=auto\n')
            content = b'version = 4\n\n[[package]]\nname = "fixture"\nversion = "1.0.0"\n'
            (upstream/'Cargo.lock').write_bytes(content)
            git('-C', upstream, 'add', '.')
            git('-C', upstream, '-c', 'user.name=Checkout test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
            git('-C', upstream, 'tag', 'fixture')
            pin = {'url': upstream.as_uri(), 'tag':'fixture', 'commit':git('-C',upstream,'rev-parse','HEAD'), 'submodules':''}
            (fixture/'config/upstream.lock.json').write_text(json.dumps({'client':pin,'server':pin}))
            (fixture/'scripts/bootstrap-sources.py').write_bytes((ROOT/'scripts/bootstrap-sources.py').read_bytes())
            env = dict(os.environ, GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='core.eol', GIT_CONFIG_VALUE_0='crlf')
            subprocess.run([sys.executable, str(fixture/'scripts/bootstrap-sources.py')], env=env, check=True, capture_output=True)
            for name in ['client','server']:
                self.assertEqual((fixture/name/'Cargo.lock').read_bytes(), content)

if __name__ == '__main__': unittest.main()
