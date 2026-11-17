#!/usr/bin/env python3

import os
import optparse
import subprocess
from hashlib import md5, sha256
import json
import re
import brotli
import datetime

# 4GB maximum
length_count = 4
# encoding
encoding = 'utf-8'

# output: {path: (compressed_data, file_md5)}


def normalize(path: str) -> str:
    path = path.replace('\\', '/')
    while path.startswith('./'):
        path = path[2:]
    return path.lower()


def generate_md5_table(folder: str, level, exclude: str = None) -> dict:
    res: dict = dict()
    skip = normalize(exclude) if exclude else None
    excluded = False
    # os.curdir is the literal ".", so restoring it left us inside `folder`.
    curdir = os.getcwd()
    os.chdir(folder)
    seen = set()
    for root, directories, files in os.walk('.'):
        directories.sort()
        files.sort()
        if any(os.path.islink(os.path.join(root, d)) for d in directories):
            raise ValueError("Symlink directory rejected")
        # remove ./
        for f in files:
            md5_generator = md5()
            full_path = os.path.join(root, f)
            canonical = full_path.replace('\\', '/').removeprefix('./')
            parts = canonical.split('/')
            reserved = {'CON','PRN','AUX','NUL','CLOCK$'} | {f'{p}{i}' for p in ('COM','LPT') for i in range(1,10)}
            if len(canonical) > 180 or any(not re.fullmatch(r'[A-Za-z0-9._ -]+', p) or p in ('.','..') or p.endswith(('.', ' ')) or p.split('.')[0].upper() in reserved for p in parts):
                raise ValueError("Unsafe Windows path")
            if canonical.lower() in seen or os.path.islink(full_path):
                raise ValueError("Duplicate/symlink payload rejected")
            seen.add(canonical.lower())
            if skip and normalize(full_path) == skip:
                print(f"Excluding {full_path}...")
                excluded = True
                continue
            print(f"Processing {full_path}...")
            with open(full_path, "rb") as source:
                content = source.read(256*1024*1024+1)
            if len(content) > 256*1024*1024:
                raise ValueError("Payload file too large")
            content_compressed = brotli.compress(
                content, quality=level)
            md5_generator.update(content)
            md5_code = md5_generator.hexdigest().encode(encoding=encoding)
            res[full_path] = (content_compressed, md5_code)
    os.chdir(curdir)
    if skip and not excluded:
        raise ValueError(f"excluded file was not found in {folder}: {exclude}")
    return res


def write_package_metadata(md5_table: dict, output_folder: str, exe: str):
    write_blob(md5_table, os.path.join(output_folder, "data.bin"), exe)
    profile = os.environ.get('FIL_PROFILE')
    if profile not in ('customer', 'operator'):
        raise ValueError('FIL_PROFILE customer/operator is required')
    require_signature = os.environ.get('FIL_REQUIRE_AUTHENTICODE', '0')
    if require_signature not in ('0','1'):
        raise ValueError('FIL_REQUIRE_AUTHENTICODE must be 0 or 1')
    inventory = []
    total = 0
    for name, (compressed, _) in md5_table.items():
        content = brotli.decompress(compressed)
        total += len(content)
        inventory.append((name.replace('\\','/').removeprefix('./'),len(content),sha256(content).hexdigest()))
    if total > 512*1024*1024:
        raise ValueError('Payload exceeds total limit')
    with open(os.path.join(output_folder, 'data.bin'), 'rb') as blob:
        digest = sha256(blob.read()).hexdigest()
    with open(os.path.join(output_folder, 'fil_payload.rs'), 'w', encoding='utf-8') as f:
        f.write('pub const PROFILE: &str = '+json.dumps(profile)+';\n')
        f.write('pub const REQUIRE_SIGNATURE: bool = '+('true' if require_signature == '1' else 'false')+';\n')
        f.write('pub const PAYLOAD_SHA256: &str = '+json.dumps(digest)+';\n')
        f.write('pub const FILES: &[(&str,u64,&str)] = &[\n')
        for name, size, digest in inventory:
            f.write(f'({json.dumps(name)},{size},{json.dumps(digest)}),\n')
        f.write('];\n')


def write_blob(md5_table: dict, output_path: str, exe: str):
    with open(output_path, "wb") as f:
        f.write("rustdesk".encode(encoding=encoding))
        for path in md5_table.keys():
            (compressed_data, md5_code) = md5_table[path]
            data_length = len(compressed_data)
            path = path.encode(encoding=encoding)
            # path length & path
            f.write((len(path)).to_bytes(length=length_count, byteorder='big'))
            f.write(path)
            # data length & compressed data
            f.write(data_length.to_bytes(
                length=length_count, byteorder='big'))
            f.write(compressed_data)
            # md5 code
            f.write(md5_code)
        # end
        f.write("rustdesk".encode(encoding=encoding))
        # executable
        f.write(exe.encode(encoding='utf-8'))
    print(f"Metadata has been written to {output_path}")

def write_app_metadata(output_folder: str):
    output_path = os.path.join(output_folder, "app_metadata.toml")
    with open(output_path, "w") as f:
        f.write(f"timestamp = {int(datetime.datetime.now().timestamp() * 1000)}\n")
    print(f"App metadata has been written to {output_path}")

def build_portable(output_folder: str, target: str):
    current_dir = os.getcwd()
    try:
        os.chdir(output_folder)
        cmd = ["cargo", "build", "--locked", "--release"]
        if target:
            cmd.extend(["--target", target])
        subprocess.run(cmd, check=True)
    finally:
        os.chdir(current_dir)

# Linux: python3 generate.py -f ../rustdesk-portable-packer/test -o . -e ./test/main.py
# Windows: python3 .\generate.py -f ..\rustdesk\flutter\build\windows\runner\Debug\ -o . -e ..\rustdesk\flutter\build\windows\runner\Debug\rustdesk.exe


if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option("-f", "--folder", dest="folder",
                      help="folder to compress")
    parser.add_option("-o", "--output", dest="output_folder",
                      help="the root of portable packer project, default is './'")
    parser.add_option("-e", "--executable", dest="executable",
                      help="specify startup file in --folder, default is rustdesk.exe")
    parser.add_option("-t", "--target", dest="target",
                      help="the target used by cargo")
    parser.add_option("-l", "--level", dest="level", type="int",
                      help="compression level, default is 11, highest", default=11)
    parser.add_option("--package", dest="package",
                      help="write the per-customer blob to this path instead of "
                           "data.bin, and skip the cargo build. Injected into the "
                           "template's RDPKG resource so customizing needs no rebuild")
    parser.add_option("--exclude-exe", dest="exclude_exe", action="store_true",
                      default=False,
                      help="omit the executable from the blob, for a template whose "
                           "executable ships in the package instead")
    (options, args) = parser.parse_args()
    if options.package or options.exclude_exe:
        parser.error('Fil hardened portable requires a complete immutable embedded payload')
    folder = options.folder or './rustdesk'
    output_folder = os.path.abspath(options.output_folder or './')

    if not options.executable:
        options.executable = 'rustdesk.exe'
    if not options.executable.startswith(folder):
        options.executable = folder + '/' + options.executable
    # Note: the simple check `options.executable.startswith(folder)` is incorrect.
    # `python generate.py -f rustdesk -e rustdesk.exe` or `python generate.py -f rustdesk`
    # will result the print "Executable path: ..exe".
    # So we need to check if the executable is in the folder, and if so, concat again.
    if os.path.exists(os.path.join(folder, options.executable)):
        options.executable = os.path.join(folder, options.executable)
    folder_path = os.path.abspath(folder)
    exe: str = os.path.abspath(options.executable)
    try:
        in_source_folder = os.path.commonpath([folder_path, exe]) == folder_path
    except ValueError:
        in_source_folder = False
    if not in_source_folder:
        print("The executable must locate in source folder")
        exit(-1)
    exe = '.' + exe[len(folder_path):]
    print("Executable path: " + exe)
    print("Compression level: " + str(options.level))
    md5_table = generate_md5_table(
        folder, options.level, exe if options.exclude_exe else None)
    if options.package:
        write_blob(md5_table, os.path.abspath(options.package), exe)
    else:
        write_package_metadata(md5_table, output_folder, exe)
        write_app_metadata(output_folder)
        build_portable(output_folder, options.target)
