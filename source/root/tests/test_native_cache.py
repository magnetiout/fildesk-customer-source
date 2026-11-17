import importlib.util
import json
import pathlib
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('cache', pathlib.Path(__file__).resolve().parents[1]/'scripts/verify-native-cache.py')
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class NativeCache(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.manifest = self.root/'vcpkg.json'
        self.manifest.write_text(json.dumps({'vcpkg-configuration': {'default-registry': {'baseline': '1'*40}}}))
        info = self.root/'installed/vcpkg/info'
        info.mkdir(parents=True)
        self.status = self.root/'installed/vcpkg/status'
        self.status.write_text('\n\n'.join(f'Package: {name}\nVersion: 1.0\nArchitecture: {cache.TRIPLET}\nStatus: install ok installed' for name in cache.REQUIRED))
        for name in cache.REQUIRED:
            relative = f'{cache.TRIPLET}/lib/{name}.lib'
            path = self.root/'installed'/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'test fixture, not a library')
            (info/f'{name}_1.0_{cache.TRIPLET}.list').write_text(relative+'\n')

    def check(self):
        return cache.validate(self.root, self.manifest, '1'*40)

    def test_complete_cache_admitted(self):
        self.assertEqual(self.check()['status'], 'PASS')

    def test_wrong_baseline_rejected(self):
        with self.assertRaisesRegex(ValueError, 'baseline'):
            cache.validate(self.root, self.manifest, '2'*40)

    def test_missing_record_rejected(self):
        self.status.write_text(self.status.read_text().replace('Package: opus', 'Package: other'))
        with self.assertRaisesRegex(ValueError, 'missing installed packages'):
            self.check()

    def test_missing_file_rejected(self):
        (self.root/f'installed/{cache.TRIPLET}/lib/opus.lib').unlink()
        with self.assertRaisesRegex(ValueError, 'missing installed file'):
            self.check()

    def test_unsafe_list_rejected(self):
        (self.root/f'installed/vcpkg/info/opus_1.0_{cache.TRIPLET}.list').write_text('../private\n')
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            self.check()
