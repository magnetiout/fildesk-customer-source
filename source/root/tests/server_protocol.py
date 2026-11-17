#!/usr/bin/env python3
"""Real OSS wire probes, NOT desktop authentication or encrypted screen-sharing E2E.
Encoding from pinned hbb_common/protos/rendezvous.proto and src/bytes_codec.rs.
"""
import json, os, pathlib, socket, time, uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
def varint(n):
    out=bytearray()
    while n>127:out.append((n&127)|128);n>>=7
    out.append(n);return bytes(out)
def field(n,b):
    if isinstance(b,str):b=b.encode()
    return varint(n*8+2)+varint(len(b))+b

def decode(b):
    pos=0; result={}
    def integer():
        nonlocal pos
        n=0;s=0
        while True:
            v=b[pos];pos+=1;n|=(v&127)<<s
            if v<128:return n
            s+=7
    while pos<len(b):
        tag=integer();n=tag>>3;t=tag&7
        if t==0:v=integer()
        elif t==2:
            size=integer();v=b[pos:pos+size];pos+=size
        else:raise ValueError(f'Unsupported wire type {t}')
        result[n]=v
    return result

def framed(b):
    for n in range(1,5):
        if len(b)<(1<<(8*n-2)):return ((len(b)<<2)|(n-1)).to_bytes(n,'little')+b
    raise ValueError('Too large')
def exact(s,n):
    b=b''
    while len(b)<n:
        part=s.recv(n-len(b))
        if not part:raise EOFError()
        b+=part
    return b
def receive(s):
    h=exact(s,1);n=(h[0]&3)+1;h+=exact(s,n-1)
    return decode(exact(s,int.from_bytes(h,'little')>>2))
def tcp(port):
    s=socket.create_connection(('127.0.0.1',port),timeout=4);return s

def run(base_port=21115, data_dir=None, profiles_path=None):
    key=((data_dir or ROOT/'deployment/development/data')/'id_ed25519.pub').read_text().strip()
    path=profiles_path or ROOT/'build/probe-profiles.json'
    if path.exists():profiles=json.loads(path.read_text())
    else:
        profiles=[{'id':f'filtest{uuid.uuid4().hex[:12]}','uuid':os.urandom(16).hex(),'pk':os.urandom(32).hex()} for _ in range(2)]
        path.write_text(json.dumps(profiles));path.chmod(0o600)
    sockets=[]
    try:
        for p in profiles:
            s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(4);s.bind(('127.0.0.1',0));sockets.append(s)
            msg=field(15,field(1,p['id'])+field(2,bytes.fromhex(p['uuid']))+field(3,bytes.fromhex(p['pk'])))
            s.sendto(msg,('127.0.0.1',base_port+1));result=decode(s.recv(4096))
            assert 16 in result and decode(result[16]).get(1,0)==0, 'RegisterPk rejected'
            s.sendto(field(6,field(1,p['id'])),('127.0.0.1',base_port+1));result=decode(s.recv(4096))
            assert 7 in result and decode(result[7]).get(2,0)==0,'Registration state missing'
        print('PASS two synthetic peer profiles registered by UDP; NOT desktop clients')
        with tcp(base_port) as s:
            s.sendall(framed(field(20,b'')));assert 21 in receive(s)
        print('PASS TCP NAT probe')
        with tcp(base_port+1) as s:
            s.sendall(framed(field(8,field(1,profiles[0]['id'])+field(3,'wrong-public-key'))))
            response=receive(s);assert decode(response[11]).get(3)==3,response
        print('PASS hbbs wrong infrastructure key rejected')
        with tcp(base_port+2) as s:
            s.sendall(framed(field(18,field(2,uuid.uuid4().hex)+field(6,'wrong-public-key'))))
            assert s.recv(1)==b''
        print('PASS hbbr wrong infrastructure key rejected')
        pair=uuid.uuid4().hex
        with tcp(base_port+2) as a,tcp(base_port+2) as b:
            request=framed(field(18,field(2,pair)+field(6,key)))
            a.sendall(request);time.sleep(.15);b.sendall(request);time.sleep(.15)
            a.sendall(b'fil-relay-probe');assert exact(b,15)==b'fil-relay-probe'
            b.sendall(b'ack');assert exact(a,3)==b'ack'
        print('PASS hbbr pairs two sockets and relays bidirectionally; sockets closed')
    finally:
        for s in sockets:s.close()
if __name__=='__main__':run()
