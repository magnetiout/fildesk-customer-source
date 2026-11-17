#!/usr/bin/env python3
"""Rasterize the official mark: transparent UI logo and fine-edged shell icons.
Run with build/branding-venv/bin/python; see branding/renderer-requirements.txt.
"""
import hashlib, io, json, pathlib, struct
import cairosvg
from PIL import Image, ImageFilter

root = pathlib.Path(__file__).resolve().parents[1]
source = root / 'branding/assets/official/Fil_Logo_svg.svg'
raw = source.read_bytes()
expected = json.loads((source.parent / 'source.json').read_text())['sha256']
assert hashlib.sha256(raw).hexdigest() == expected, 'Official source hash changed'
sizes = (16, 24, 32, 48, 64, 128, 256)
outputs = []
def write(path, data):
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    outputs.append({'path': path, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
def png(size, shell=False, dark=False):
    # Supersampling retains the original strokes; no invented monogram or cropping.
    n = max(1024, size * 4)
    # Dark variant is a 40% white tint of the original green, identical geometry.
    vector = raw.replace(b'#2D7A3A', b'#81AF89') if dark else raw
    mark = Image.open(io.BytesIO(cairosvg.svg2png(bytestring=vector, output_width=n, output_height=n))).convert('RGBA')
    canvas = Image.new('RGBA', (n, n))
    if shell:
        # A subpixel outline follows the existing alpha, never a filled plate.
        radius = max(1, round((0.55 if size <= 32 else 0.45) * n / size))
        edge = mark.getchannel('A').filter(ImageFilter.MaxFilter(radius * 2 + 1))
        canvas = Image.new('RGBA', (n, n), (223, 232, 225, 0))
        canvas.putalpha(edge)
    canvas.alpha_composite(mark)
    canvas = canvas.resize((size, size), Image.Resampling.LANCZOS)
    out = io.BytesIO(); canvas.save(out, format='PNG')
    return out.getvalue()
images = [png(n, shell=True) for n in sizes]
ico = struct.pack('<HHH', 0, 1, len(sizes)); offset = 6 + 16*len(sizes)
for n, data in zip(sizes, images):
    ico += struct.pack('<BBBBHHII', n%256, n%256, 0, 0, 1, 32, len(data), offset)
    offset += len(data)
ico += b''.join(images)
for path in ('branding/assets/fildesk.ico', 'client/res/icon.ico', 'client/res/tray-icon.ico',
             'client/flutter/windows/runner/resources/app_icon.ico', 'client/flutter/assets/icon.ico'):
    write(path, ico)
for n, data in zip(sizes, images):
    write(f'branding/assets/official/icon-{n}.png', data)
for path in ('branding/assets/fildesk.png', 'client/flutter/assets/icon.png'):
    write(path, images[-1])
write('client/flutter/assets/logo.png', png(256))
write('client/flutter/assets/logo_dark.png', png(256, dark=True))
write('branding/assets/official/logo-dark-1024.png', png(1024, dark=True))
write('branding/assets/official/logo-dark.svg', raw.replace(b'#2D7A3A', b'#81AF89'))
write('branding/assets/official/logo-1024.png', png(1024))
# No vector geometry/color change; remove only source trailing whitespace.
svg = '\n'.join(line.rstrip() for line in raw.decode().splitlines())
write('client/flutter/assets/icon.svg', svg.encode())
write('integration/nextjs/public/fildesk/fil-teknoloji.svg', svg.encode())
for name, size in [('StoreLogo',50), ('Square44x44Logo',44), ('Square150x150Logo',150),
                   ('Square44x44Logo.scale-200',88), ('Square150x150Logo.scale-200',300)]:
    write(f'deployment/msix/Assets/{name}.png', png(size, shell=True))
(root/'branding/assets/official/generated.json').write_text(json.dumps({'source_sha256':expected, 'sizes':sizes,
 'treatment':'Original geometry; transparent original-green UI/web logo; dark UI tint #81AF89 (40% white blend); original-green shell/MSIX icons with subpixel neutral alpha outline; no plate or invented monogram',
 'files':outputs}, indent=2)+'\n')
print(f'Generated {len(outputs)} official-logo assets')
