#!/usr/bin/env python3
"""Restore pinned source trees; sanitized exports are already branded."""
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import urllib.parse

SANITIZED = 'fil-sanitized-source-v1'


def restore(root, run=subprocess.run):
    root = pathlib.Path(root)
    if os.path.lexists(root / 'config/ci-source-inputs.json'):
        spec = importlib.util.spec_from_file_location('ci_sources', root / 'scripts/bootstrap-ci-sources.py')
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        return helper.restore(root, run=run)
    lock = json.loads((root / 'config/upstream.lock.json').read_text())
    if not isinstance(lock, dict) or set(lock) != {'client', 'server'}:
        raise ValueError('Expected exactly client and server pins')
    # Validate the entire plan and both destinations before the first clone.
    for name, pin in lock.items():
        if not isinstance(pin, dict):
            raise ValueError('Invalid source pin')
        fmt = pin.get('source_format')
        if fmt is not None and fmt != SANITIZED:
            raise ValueError('Unknown source format')
        url = pin.get('url')
        if not isinstance(url, str):
            raise ValueError('Invalid HTTPS source URL')
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname != 'github.com'
                or parsed.netloc != 'github.com' or parsed.query or parsed.fragment
                or not re.fullmatch(r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?', parsed.path)):
            raise ValueError('Invalid HTTPS source URL')
        if not isinstance(pin.get('commit'), str) or not re.fullmatch(r'[0-9a-f]{40}', pin['commit']):
            raise ValueError('Invalid commit pin')
        if not isinstance(pin.get('tag'), str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', pin['tag']) or '..' in pin['tag']:
            raise ValueError('Invalid source ref')
        if not isinstance(pin.get('submodules', ''), str):
            raise ValueError('Invalid submodule pins')
        if os.path.lexists(root / name):
            raise ValueError('Destination exists; use a fresh checkout')

    for name, pin in lock.items():
        dst = root / name
        def command(args):
            return run(args, check=True, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE).stdout.strip()
        def git(*args):
            return command(['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', '-C', str(dst), *args])
        command(['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', 'clone', '--depth', '1', '--branch', pin['tag'], '--', pin['url'], str(dst)])
        if git('rev-parse', 'HEAD') != pin['commit']:
            raise ValueError('Source commit pin mismatch')
        if pin.get('source_format') == SANITIZED:
            if any(line.startswith('160000 ') for line in git('ls-tree', '-r', 'HEAD').splitlines()):
                raise ValueError('Sanitized source contains gitlinks')
            common = dst / 'libs/hbb_common'
            for required in [common, common / 'Cargo.toml', common / 'src/lib.rs']:
                if required.is_symlink() or not required.exists() or not required.resolve().is_relative_to(dst.resolve()):
                    raise ValueError('Sanitized source lacks vendored common source')
            continue
        # Historical upstream mode intentionally retains the original workflow.
        git('remote', 'rename', 'origin', 'upstream')
        git('switch', '-c', 'fil/v0.1.0-dev')
        git('submodule', 'update', '--init', '--recursive')
        actual = [line.split()[:2] for line in git('submodule', 'status', '--recursive').splitlines()]
        expected = [line.split()[:2] for line in pin['submodules'].splitlines()]
        if actual != expected:
            raise ValueError('Submodule pin mismatch')
        patch = root / 'branding/patches' / (name + '.patch')
        if patch.exists():
            git('apply', '--check', str(patch))
            git('apply', str(patch))



def safe_failure_reason(error):
    """Only reviewed static messages may leave the controller boundary."""
    allowed = {
        'Vendored common digest mismatch', 'Source lock mismatch',
        'Source HEAD/tree mismatch', 'Bundle digest mismatch',
        'Bundle refs mismatch', 'Restored source is dirty',
        'Source destination already exists', 'Gitlinks forbidden in vendored source',
    }
    if type(error) is ValueError and error.args and isinstance(error.args[0], str) and error.args[0] in allowed:
        return error.args[0]
    return type(error).__name__ if type(error) in (ValueError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) else 'SourceRestoreError'


if __name__ == '__main__':
    try:
        restore(pathlib.Path(__file__).resolve().parents[1])
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('Pinned source restoration failed: ' + safe_failure_reason(error))
    print('Pinned source trees restored using their explicit source format.')
