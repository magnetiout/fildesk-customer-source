#!/usr/bin/env python3
"""Delegate to the source-matched Cargo helper tests. No SYSTEM launch occurs."""
import argparse
import pathlib
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--client', required=True, type=pathlib.Path)
parser.add_argument('--output', required=True, type=pathlib.Path)
args = parser.parse_args()
client = args.client.resolve(strict=True)
runner = client/'tests/fil_windows_helpers/run.py'
if not runner.is_file():
    raise SystemExit('Source-matched licensed native tests missing')
raise SystemExit(subprocess.call([sys.executable, str(runner), '--client', str(client), '--output', str(args.output.resolve())]))
