#!/usr/bin/env python3
"""Test-only UDP-over-TCP adapter. All listeners/destinations are loopback.
TCP must travel through an authenticated SSH local forward across machines.
No payload logging; bounded sessions, queue size, frame size and idle lifetime.
"""
import argparse,asyncio,contextlib,struct
LOOPBACK='127.0.0.1'
LIMIT=32
IDLE=60
class DatagramQueue(asyncio.DatagramProtocol):
    def __init__(self):self.queue=asyncio.Queue(64)
    def connection_made(self,transport):self.transport=transport
    def datagram_received(self,data,addr):
        if not self.queue.full():self.queue.put_nowait((data,addr))
async def read_frame(reader):
    n=struct.unpack('!H',await asyncio.wait_for(reader.readexactly(2),IDLE))[0]
    if n>65507:raise ValueError('Oversize UDP frame')
    return await asyncio.wait_for(reader.readexactly(n),IDLE)
async def write_frame(writer,data):
    writer.write(struct.pack('!H',len(data))+data)
    await asyncio.wait_for(writer.drain(),IDLE)
async def race(*coroutines):
    tasks=[asyncio.create_task(c) for c in coroutines]
    try:
        done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        for task in done:task.result()
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
async def serve_tcp(port,udp_port):
    active=set()
    async def handle(reader,writer):
        if len(active)>=LIMIT:
            writer.close();await writer.wait_closed();return
        active.add(writer);transport=None
        try:
            transport,protocol=await asyncio.get_running_loop().create_datagram_endpoint(DatagramQueue,remote_addr=(LOOPBACK,udp_port))
            async def incoming():
                while True:transport.sendto(await read_frame(reader))
            async def outgoing():
                while True:
                    data,_=await asyncio.wait_for(protocol.queue.get(),IDLE)
                    await write_frame(writer,data)
            await race(incoming(),outgoing())
        except (OSError,ValueError,asyncio.TimeoutError,asyncio.IncompleteReadError):pass
        finally:
            if transport:transport.close()
            writer.close()
            with contextlib.suppress(OSError):await writer.wait_closed()
            active.discard(writer)
    server=await asyncio.start_server(handle,LOOPBACK,port,limit=65536)
    async with server:await server.serve_forever()
async def serve_udp(port,tcp_port):
    transport,protocol=await asyncio.get_running_loop().create_datagram_endpoint(DatagramQueue,local_addr=(LOOPBACK,port))
    sessions={};tasks=set()
    async def session(addr,queue):
        writer=None
        try:
            reader,writer=await asyncio.wait_for(asyncio.open_connection(LOOPBACK,tcp_port),10)
            async def outgoing():
                while True:await write_frame(writer,await asyncio.wait_for(queue.get(),IDLE))
            async def incoming():
                while True:transport.sendto(await read_frame(reader),addr)
            await race(outgoing(),incoming())
        except (OSError,ValueError,asyncio.TimeoutError,asyncio.IncompleteReadError):pass
        finally:
            if writer:
                writer.close()
                with contextlib.suppress(OSError):await writer.wait_closed()
            sessions.pop(addr,None)
    try:
        while True:
            data,addr=await protocol.queue.get()
            if addr not in sessions:
                if len(sessions)>=LIMIT:continue
                queue=asyncio.Queue(64);sessions[addr]=queue
                task=asyncio.create_task(session(addr,queue));tasks.add(task);task.add_done_callback(tasks.discard)
            if not sessions[addr].full():sessions[addr].put_nowait(data)
    finally:
        transport.close()
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
def port(value):
    value=int(value)
    if not 1024<=value<=65535:raise argparse.ArgumentTypeError('Use unprivileged port 1024..65535')
    return value
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['server','client'])
    p.add_argument('--listen',type=port,required=True)
    p.add_argument('--forward',type=port,required=True)
    a=p.parse_args()
    try:asyncio.run((serve_tcp if a.mode=='server' else serve_udp)(a.listen,a.forward))
    except KeyboardInterrupt:pass
