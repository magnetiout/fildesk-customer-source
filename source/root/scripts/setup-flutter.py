#!/usr/bin/env python3
"""Bootstrap official Flutter source without depending on the release archive index."""
import os,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
DEST=ROOT/'build/flutter'
SHA='dec2ee5c1f98f8e84a7d5380c05eb8a3d0a81668'
if not DEST.exists():
    subprocess.run(['git','clone','--depth','1','--branch','3.24.5','https://github.com/flutter/flutter.git',str(DEST)],check=True)
actual=subprocess.check_output(['git','-C',str(DEST),'rev-parse','HEAD'],text=True).strip()
if actual!=SHA:raise SystemExit('Flutter source SHA mismatch')
if os.environ.get('GITHUB_PATH'):
    with open(os.environ['GITHUB_PATH'],'a') as f:f.write(str(DEST/'bin')+'\n')
print('Verified official Flutter 3.24.5 source:',actual)
print('Flutter bootstraps the engine-pinned Dart SDK; no release-version substitution.')
