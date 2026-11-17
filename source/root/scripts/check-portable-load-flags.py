#!/usr/bin/env python3
"""Require AMD64 PE loader's pre-entrypoint System32-only dependency policy."""
import pathlib,struct,sys
b=pathlib.Path(sys.argv[1]).read_bytes()
def u16(p):return struct.unpack_from('<H',b,p)[0]
def u32(p):return struct.unpack_from('<I',b,p)[0]
assert b[:2]==b'MZ'
p=u32(0x3c);assert b[p:p+4]==b'PE\0\0' and u16(p+4)==0x8664 and u16(p+24)==0x20b
rva=u32(p+24+112+10*8);size=u32(p+24+112+10*8+4);assert size>=80
sections=p+24+u16(p+20)
for i in range(u16(p+6)):
 s=sections+i*40;va=u32(s+12);rawsize=u32(s+16)
 if va<=rva and rva+80<=va+rawsize:
  at=u32(s+20)+rva-va
  assert u32(at)>=80 and u16(at+78)==0x800,'Missing System32-only dependent load flags'
  print('PASS PE32+ AMD64 / DependentLoadFlags=0x800 (Windows10 RS1+)')
  break
else:raise ValueError('No file-backed load configuration')
