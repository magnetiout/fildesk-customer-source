import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('identity', ROOT/'scripts/verify-release-version.py')
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


class ReleaseIdentity(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.client = pathlib.Path(tmp.name)
        for file in ('Cargo.toml', 'flutter/pubspec.yaml', 'src/fil_connection_status.rs',
                     'src/flutter_ffi.rs', 'flutter/lib/desktop/pages/desktop_setting_page.dart',
                     'flutter/windows/runner/Runner.rc', 'libs/portable/build.rs'):
            target = self.client/file
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/'client'/file).read_bytes())

    def test_actual_metadata_matches_and_protocol_is_preserved(self):
        result = identity.validate(self.client, '1.5.0+77')
        self.assertEqual(result['wireProtocolVersion'], '1.5.0')
        self.assertEqual(result['windowsFixedVersion'], '1.5.0.77')

    def test_stale_native_build_rejected(self):
        p = self.client/'src/fil_connection_status.rs'
        p.write_text(p.read_text().replace('1.5.0+77', '1.5.0+73'))
        with self.assertRaisesRegex(ValueError, 'native display'):
            identity.validate(self.client)

    def test_stale_outer_fixed_resource_rejected(self):
        p = self.client/'libs/portable/build.rs'
        p.write_text(p.read_text().replace('0x0001_0005_0000_004d', '0x0000_0001_0000_0000'))
        with self.assertRaisesRegex(ValueError, 'fixed version'):
            identity.validate(self.client)

    def test_wire_version_cannot_be_changed_by_display_bump(self):
        p = self.client/'Cargo.toml'
        p.write_text(p.read_text().replace('version = "1.5.0"', 'version = "1.5.0+77"', 1))
        with self.assertRaisesRegex(ValueError, 'wire protocol'):
            identity.validate(self.client)
