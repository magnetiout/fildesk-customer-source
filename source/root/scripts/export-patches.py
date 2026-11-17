#!/usr/bin/env python3
"""Export committed local Fil changes against verified upstream pins."""
import json,pathlib,subprocess
root=pathlib.Path(__file__).resolve().parents[1]
pins=json.loads((root/'config/upstream.lock.json').read_text())
out=root/'branding/patches';out.mkdir(exist_ok=True)
for name,pin in pins.items():
    patch=subprocess.check_output(['git','-C',str(root/name),'diff','--binary',pin['commit'],'HEAD'])
    (out/f'{name}.patch').write_bytes(patch)
print('Exported committed fork changes. Generated local configuration is not part of the patches.')
