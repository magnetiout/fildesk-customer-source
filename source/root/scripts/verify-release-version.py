#!/usr/bin/env python3
"""Check display/PE metadata without changing the proven wire protocol version."""
import argparse
import json
import pathlib
import re
import tomllib


def validate(client, expected=None):
    pubspec = (client/'flutter/pubspec.yaml').read_text(encoding='utf-8')
    version = re.search(r'^version:\s*(\S+)', pubspec, re.M).group(1)
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)\+(\d+)', version)
    if not match or (expected and expected != version):
        raise ValueError('release version mismatch')
    parts = tuple(map(int, match.groups()))
    if any(p > 65535 for p in parts):
        raise ValueError('PE version component overflow')
    native = (client/'src/fil_connection_status.rs').read_text(encoding='utf-8')
    if f'pub const BUILD: &str = "{version}";' not in native:
        raise ValueError('native display version mismatch')
    ffi = (client/'src/flutter_ffi.rs').read_text(encoding='utf-8')
    function = re.search(r'pub fn main_get_version\(\) -> String \{([^}]+)\}', ffi).group(1)
    if 'crate::fil_connection_status::BUILD.to_owned()' not in function:
        raise ValueError('About version is not bound to display identity')
    about = (client/'flutter/lib/desktop/pages/desktop_setting_page.dart').read_text(encoding='utf-8')
    if 'Fil Teknoloji • v$version • İmzasız özel test sürümü' not in about:
        raise ValueError('About header has stale identity')
    resource = (client/'flutter/windows/runner/Runner.rc').read_text(encoding='utf-8')
    for text in ('FILEVERSION VERSION_AS_NUMBER', 'PRODUCTVERSION VERSION_AS_NUMBER',
                 '"FileVersion", VERSION_AS_STRING', '"ProductVersion", VERSION_AS_STRING'):
        if text not in resource:
            raise ValueError('runtime PE version is not bound to Flutter version')
    if '0.1.0-dev' in resource:
        raise ValueError('stale runtime resource')
    packer = (client/'libs/portable/build.rs').read_text(encoding='utf-8')
    file_version = '.'.join(map(str, parts))
    packed = sum(part << ((3-i)*16) for i, part in enumerate(parts))
    if f'.set("ProductVersion", "{version}")' not in packer or f'.set("FileVersion", "{file_version}")' not in packer:
        raise ValueError('outer portable PE string mismatch')
    for field in ('PRODUCTVERSION', 'FILEVERSION'):
        literal = re.search(r'set_version_info\(winres::VersionInfo::'+field+r',\s*(0x[\da-fA-F_]+)\)', packer)
        if not literal or int(literal.group(1), 16) != packed:
            raise ValueError('outer portable PE fixed version mismatch')
    wire = tomllib.loads((client/'Cargo.toml').read_text(encoding='utf-8'))['package']['version']
    if wire != '1.5.0':
        raise ValueError('73 wire protocol version unexpectedly changed')
    return {'status': 'PASS', 'displayVersion': version, 'windowsFixedVersion': file_version,
            'wireProtocolVersion': wire, 'scope': 'source metadata only; Windows PE verification remains mandatory'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--client', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1]/'client')
    parser.add_argument('--expected')
    args = parser.parse_args()
    print(json.dumps(validate(args.client, args.expected), indent=2))
