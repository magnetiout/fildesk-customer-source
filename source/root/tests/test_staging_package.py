"""Fail-closed package validation; generated fixtures only, no deployment/network."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / 'deployment/singapore-staging/verify.py'

class StagingPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='staging-verifier-', dir=ROOT/'build')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        data = b'fixture binary bytes'
        (self.root/'hbbs').write_bytes(data)
        self.manifest = {'environment':'staging-loopback-only',
            'server_commit':'62207aa701e7fd4ecb5ee7bf5d86da1498c0cceb',
            'files':{'hbbs':{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}}}
        (self.root/'verify.py').write_bytes(VERIFIER.read_bytes())
        data = (self.root/'verify.py').read_bytes()
        self.manifest['files']['verify.py']={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        self.save()

    def save(self):
        (self.root/'package-manifest.json').write_text(json.dumps(self.manifest))

    def verify(self):
        return subprocess.run(['python3',str(self.root/'verify.py')],capture_output=True).returncode

    def test_optimized_python_refused(self):
        result = subprocess.run(["python3", "-O", str(self.root/"verify.py")],capture_output=True)
        self.assertNotEqual(result.returncode,0)

    def test_valid(self):
        self.assertEqual(self.verify(),0)

    def test_tampered_binary(self):
        (self.root/'hbbs').write_bytes(b'fixture binary BYTEs')
        self.assertNotEqual(self.verify(),0)

    def test_extra_private_key(self):
        (self.root/'id_ed25519').write_text('synthetic marker, not a key')
        self.assertNotEqual(self.verify(),0)

    def test_data_directory(self):
        (self.root/'data').mkdir()
        self.assertNotEqual(self.verify(),0)

    def test_symlink(self):
        (self.root/'unexpected-link').symlink_to('hbbs')
        self.assertNotEqual(self.verify(),0)

    def test_traversal_manifest(self):
        self.manifest['files']['../outside'] = self.manifest['files']['hbbs']
        self.save()
        self.assertNotEqual(self.verify(),0)

if __name__ == '__main__': unittest.main()
