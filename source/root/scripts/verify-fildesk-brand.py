#!/usr/bin/env python3
"""Read the actual PE resource section; verify brand metadata and exact official logo icon bytes."""
import argparse,json,pathlib,struct,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('directory',type=pathlib.Path);p.add_argument('--profile',choices=['customer','operator'],action='append');a=p.parse_args()
def resource(b):
 assert b[:2]==b'MZ'
 pe=struct.unpack_from('<I',b,0x3c)[0];assert b[pe:pe+4]==b'PE\0\0'
 n=struct.unpack_from('<H',b,pe+6)[0];size=struct.unpack_from('<H',b,pe+20)[0]
 for i in range(n):
  off=pe+24+size+40*i
  if b[off:off+8].rstrip(b'\0')==b'.rsrc':
   length,start=struct.unpack_from('<II',b,off+16);assert start+length<=len(b);return b[start:start+length]
 raise ValueError('Missing resource section')
def value(r,key):
 needle=(key+'\0').encode('utf-16le');values=[];at=0
 while (at:=r.find(needle,at))>=0:
  start=at-6
  if start>=0:
   length,units,kind=struct.unpack_from('<HHH',r,start);v=(at+len(needle)+3)&~3
   if kind==1 and units and v+units*2<=start+length<=len(r):
    values.append(r[v:v+units*2].decode('utf-16le').rstrip('\0'))
  at+=len(needle)
 assert len(values)==1,(key,values)
 return values[0]
rows=[]
for profile in a.profile or ('customer','operator'):
 base=a.directory/profile;outer=(base/'FilDesk.exe').read_bytes()
 with zipfile.ZipFile(base/'FilDesk-bundle.zip') as z:inner=z.read('FilDesk.exe');dll=z.read('librustdesk.dll')
 for part,b in [('portable',outer),('application',inner)]:
  r=resource(b);fields={k:value(r,k) for k in ['ProductName','CompanyName','OriginalFilename','InternalName','FileDescription']}
  assert fields==dict(ProductName='FilDesk',CompanyName='Fil Teknoloji',OriginalFilename='FilDesk.exe',InternalName='FilDesk',FileDescription='FilDesk development build'),fields
  for size in (16,24,32,48,64,128,256):
   assert (ROOT/f'branding/assets/official/icon-{size}.png').read_bytes() in r, f'Official icon {size}px resource mismatch'
  rows.append({'profile':profile,'part':part,'metadata':fields,'embedded_official_logo':'PASS'})
 assert (ROOT/'client/res/tray-icon.ico').read_bytes() in dll,'Compiled runtime tray icon mismatch'
print(json.dumps({'status':'PASS','scope':'Static actual PE VERSIONINFO, official logo resource bytes and compiled tray icon; not GUI/tray runtime acceptance','files':rows},indent=2))
