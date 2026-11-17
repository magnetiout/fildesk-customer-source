#!/usr/bin/env python3
"""Actual hbbs registration through both helper modes, locally; NOT SSH or Windows E2E."""
import asyncio,importlib.util,os,pathlib,socket,uuid
R=pathlib.Path(__file__).resolve().parents[1]
def module(name,path):
    s=importlib.util.spec_from_file_location(name,R/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=module('tunnel','scripts/lab-udp-tunnel.py');p=module('probe','tests/server_protocol.py')
async def run():
    # Bind probes first; refuse collisions and never terminate an existing listener.
    reserved=[]
    for kind,port in [(socket.SOCK_STREAM,32316),(socket.SOCK_DGRAM,32416)]:
        s=socket.socket(socket.AF_INET,kind);s.bind(('127.0.0.1',port));reserved.append(s)
    for s in reserved:s.close()
    tasks=[asyncio.create_task(m.serve_tcp(32316,21116)),asyncio.create_task(m.serve_udp(32416,32316))]
    sockets=[]
    try:
        await asyncio.sleep(.1);loop=asyncio.get_running_loop()
        for _ in range(2):
            s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('127.0.0.1',0));s.connect(('127.0.0.1',32416));s.setblocking(False);sockets.append(s)
            identity='fil-lab-'+uuid.uuid4().hex[:12]
            request=p.field(15,p.field(1,identity)+p.field(2,os.urandom(16))+p.field(3,os.urandom(32)))
            await loop.sock_sendall(s,request)
            reply=p.decode(await asyncio.wait_for(loop.sock_recv(s,4096),4));assert 16 in reply and p.decode(reply[16]).get(1,0)==0
            await loop.sock_sendall(s,p.field(6,p.field(1,identity)))
            reply=p.decode(await asyncio.wait_for(loop.sock_recv(s,4096),4));assert 7 in reply
        print('PASS two synthetic hbbs registrations through UDP -> TCP framing -> UDP; all loopback')
        print('NOT RUN SSH transport, Windows helper, desktop authentication/E2E')
    finally:
        for s in sockets:s.close()
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
if __name__=='__main__':asyncio.run(run())
