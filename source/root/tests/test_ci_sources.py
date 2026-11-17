import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

CI = load(ROOT / 'scripts/bootstrap-ci-sources.py', 'ci_sources_test')
ENTRY = load(ROOT / 'scripts/bootstrap-sources.py', 'bootstrap_entry_test')


def git(root, *args):
    return subprocess.check_output(['git', '-c', 'user.name=CI Source Test',
        '-c', 'user.email=ci-source@localhost.invalid', '-C', str(root), *args],
        text=True, stderr=subprocess.DEVNULL).strip()


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name) / 'root'
        self.root.mkdir()
        git(self.root, 'init', '--quiet')
        (self.root / 'config').mkdir()
        (self.root / 'ci/source').mkdir(parents=True)
        (self.root / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/bootstrap-ci-sources.py', self.root / 'scripts/bootstrap-ci-sources.py')
        self.manifest = {'schema_version': 1, 'kind': 'fildesk-ci-local-bundles-v1', 'sources': {}}
        self.sources = {}
        for name in ['client', 'server']:
            source = pathlib.Path(self.temp.name) / name
            source.mkdir()
            git(source, 'init', '--quiet')
            git(source, 'switch', '--quiet', '-c', 'pala/fixture')
            (source / 'libs/hbb_common/src').mkdir(parents=True)
            (source / 'libs/hbb_common/Cargo.toml').write_text('[package]\nname="fixture-common"\n')
            (source / 'libs/hbb_common/src/lib.rs').write_text('// scoped synthetic source\n')
            (source / 'Cargo.lock').write_text('# synthetic lock\n')
            git(source, 'add', '.')
            git(source, 'commit', '--quiet', '-m', 'Synthetic source fixture')
            self.sources[name] = source
            self.rebundle(name)
        self.save()

    def rebundle(self, name):
        source = self.sources[name]
        bundle = self.root / f'ci/source/{name}.bundle'
        if bundle.exists():
            bundle.unlink()
        git(source, 'bundle', 'create', str(bundle), 'refs/heads/pala/fixture')
        self.manifest['sources'][name] = {'bundle': f'ci/source/{name}.bundle',
            'sha256': hashlib.sha256(bundle.read_bytes()).hexdigest(),
            'commit': git(source, 'rev-parse', 'HEAD'), 'tree': git(source, 'rev-parse', 'HEAD^{tree}'),
            'ref': 'refs/heads/pala/fixture',
            'lock_sha256': hashlib.sha256((source / 'Cargo.lock').read_bytes()).hexdigest(),
            'vendored_common_sha256': CI.common_digest(source / 'libs/hbb_common')}

    def save(self):
        (self.root / 'config/ci-source-inputs.json').write_text(json.dumps(self.manifest))

    def test_actual_bundle_restore_has_exact_head_tree_lock_common_and_no_network_commands(self):
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            return subprocess.run(args, **kwargs)
        ENTRY.restore(self.root, run=runner)
        for name, pin in self.manifest['sources'].items():
            dst = self.root / name
            self.assertEqual(git(dst, 'rev-parse', 'HEAD'), pin['commit'])
            self.assertEqual(CI.common_digest(dst / 'libs/hbb_common'), pin['vendored_common_sha256'])
        self.assertFalse(any('submodule' in c or 'apply' in c for c in calls))
        self.assertFalse(any(any(str(a).startswith(('https://', 'ssh://')) for a in c) for c in calls))

    def test_tampered_second_bundle_rejected_before_any_clone(self):
        (self.root / 'ci/source/server.bundle').write_bytes(b'corrupt')
        with mock.patch.object(CI.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                CI.restore(self.root)
            run.assert_not_called()
        self.assertFalse((self.root / 'client').exists())

    def test_preexisting_second_destination_including_broken_symlink_refused(self):
        (self.root / 'server').symlink_to(self.root / 'missing')
        with self.assertRaises(ValueError):
            CI.restore(self.root)
        self.assertFalse((self.root / 'client').exists())

    def test_wrong_commit_refused_before_clone(self):
        self.manifest['sources']['client']['commit'] = 'a' * 40
        self.save()
        with self.assertRaises(ValueError):
            CI.restore(self.root)
        self.assertFalse((self.root / 'client').exists())

    def test_extra_bundle_head_refused(self):
        source = self.sources['client']
        git(source, 'branch', 'pala/extra')
        bundle = self.root / 'ci/source/client.bundle'
        bundle.unlink()
        git(source, 'bundle', 'create', str(bundle), '--branches')
        self.manifest['sources']['client']['sha256'] = hashlib.sha256(bundle.read_bytes()).hexdigest()
        self.save()
        with self.assertRaises(ValueError):
            CI.restore(self.root)
        self.assertFalse((self.root / 'client').exists())

    def test_missing_vendored_common_refused(self):
        source = self.sources['client']
        git(source, 'rm', '-r', 'libs/hbb_common')
        git(source, 'commit', '--quiet', '-m', 'Missing common negative fixture')
        old = self.manifest['sources']['client']['vendored_common_sha256']
        # Bundle source is valid Git, but the required vendored directory is absent.
        bundle = self.root / 'ci/source/client.bundle'
        bundle.unlink()
        git(source, 'bundle', 'create', str(bundle), 'refs/heads/pala/fixture')
        pin = self.manifest['sources']['client']
        pin.update(sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(), commit=git(source, 'rev-parse', 'HEAD'), tree=git(source, 'rev-parse', 'HEAD^{tree}'), vendored_common_sha256=old)
        self.save()
        with self.assertRaises(ValueError):
            CI.restore(self.root)

    def test_gitlink_refused(self):
        source = self.sources['client']
        commit = git(source, 'rev-parse', 'HEAD')
        git(source, 'update-index', '--add', '--cacheinfo', f'160000,{commit},unexpected-submodule')
        git(source, 'commit', '--quiet', '-m', 'Gitlink negative fixture')
        self.rebundle('client')
        self.save()
        with self.assertRaises(ValueError):
            CI.restore(self.root)

    def test_symlink_or_traversal_bundle_refused(self):
        for name in ['../client.bundle', 'ci/source/../client.bundle']:
            self.manifest['sources']['client']['bundle'] = name
            self.save()
            with self.assertRaises(ValueError):
                CI.restore(self.root)
        self.manifest['sources']['client']['bundle'] = 'ci/source/client.bundle'
        self.save()
        bundle = self.root / 'ci/source/client.bundle'
        moved = self.root / 'moved.bundle'
        bundle.rename(moved)
        bundle.symlink_to(moved)
        with self.assertRaises(ValueError):
            CI.restore(self.root)

    def test_malformed_manifest_never_falls_back_to_remote_legacy(self):
        (self.root / 'config/ci-source-inputs.json').write_text('{bad json')
        with self.assertRaises(ValueError):
            ENTRY.restore(self.root)

    def test_unknown_or_malformed_manifest_schema_refused_before_clone(self):
        for field, value in [('schema_version', True), ('kind', 'unknown-v2'), ('sources', [])]:
            original = self.manifest[field]
            self.manifest[field] = value
            self.save()
            with self.assertRaises(ValueError):
                CI.restore(self.root)
            self.assertFalse((self.root / 'client').exists())
            self.manifest[field] = original

    def test_wrong_tree_or_lock_is_rejected(self):
        for field in ['tree', 'lock_sha256']:
            original = self.manifest['sources']['client'][field]
            self.manifest['sources']['client'][field] = 'a' * len(original)
            self.save()
            with self.assertRaises(ValueError):
                CI.restore(self.root)
            for name in ['client', 'server']:
                shutil.rmtree(self.root / name, ignore_errors=True)
            self.manifest['sources']['client'][field] = original

    def test_legacy_entry_without_manifest_preserves_existing_commands(self):
        (self.root / 'config/ci-source-inputs.json').unlink()
        pins = {name: {'url': f'https://github.com/example/{name}.git', 'tag': 'v1', 'commit': 'a' * 40, 'submodules': ''} for name in ['client', 'server']}
        (self.root / 'config/upstream.lock.json').write_text(json.dumps(pins))
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, stdout='a' * 40 if args[-2:] == ['rev-parse', 'HEAD'] else '')
        ENTRY.restore(self.root, run=runner)
        self.assertEqual(sum('clone' in c for c in calls), 2)
        self.assertEqual(sum('rename' in c for c in calls), 2)
        self.assertEqual(sum('submodule' in c and 'update' in c for c in calls), 2)




class PlatformOrderTests(unittest.TestCase):
    def test_real_bundles_common_digest_is_platform_independent(self):
        import builtins
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            git(root, 'init', '-q')
            for relative in ['config/ci-source-inputs.json', 'ci/source/client.bundle', 'ci/source/server.bundle']:
                dest = root / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, dest)
            CI.restore(root)
            pins = json.loads((ROOT / 'config/ci-source-inputs.json').read_text())
            def windows_sorted(items, *, key=None, reverse=False):
                return builtins.sorted(items, key=key or (lambda p: pathlib.PureWindowsPath(p.as_posix())), reverse=reverse)
            for name in ['client', 'server']:
                common = root / name / 'libs/hbb_common'
                paths = [p for p in common.rglob('*') if p.is_file()]
                def old_digest(items):
                    return hashlib.sha256(''.join(p.relative_to(common).as_posix() + '\0' + hashlib.sha256(p.read_bytes()).hexdigest() + '\n' for p in items).encode()).hexdigest()
                expected = pins['sources'][name]['vendored_common_sha256']
                self.assertNotEqual(old_digest(windows_sorted(paths)), expected)
                with mock.patch.object(CI, 'sorted', windows_sorted, create=True):
                    self.assertEqual(CI.common_digest(common), expected)

    def test_diagnostics_only_disclose_allowlisted_static_messages(self):
        self.assertEqual(ENTRY.safe_failure_reason(ValueError('Vendored common digest mismatch')), 'Vendored common digest mismatch')
        for error in [ValueError('PRIVATE_SENTINEL'), subprocess.CalledProcessError(1, ['PRIVATE_SENTINEL'], stderr='PRIVATE_SENTINEL'), subprocess.TimeoutExpired(['PRIVATE_SENTINEL'], 1)]:
            self.assertNotIn('PRIVATE_SENTINEL', ENTRY.safe_failure_reason(error))


if __name__ == '__main__':
    unittest.main()
