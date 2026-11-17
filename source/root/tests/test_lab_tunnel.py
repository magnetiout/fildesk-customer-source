import asyncio,importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tunnel',ROOT/'scripts/lab-udp-tunnel.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tunnel(unittest.IsolatedAsyncioTestCase):
    async def test_frame_and_invalid_length(self):
        r=asyncio.StreamReader();r.feed_data(b'\x00\x03abc');self.assertEqual(await m.read_frame(r),b'abc')
        r=asyncio.StreamReader();r.feed_data(b'\xff\xff')
        with self.assertRaises(ValueError):await m.read_frame(r)
    async def test_bounded_datagram_queue(self):
        q=m.DatagramQueue()
        for _ in range(100):q.datagram_received(b'test',('127.0.0.1',1))
        self.assertEqual(q.queue.qsize(),64)
    async def test_two_clients_separate_udp_endpoints(self):
        loop=asyncio.get_running_loop()
        class Echo(asyncio.DatagramProtocol):
            def connection_made(self,t):self.t=t;self.peers=set()
            def datagram_received(self,d,a):self.peers.add(a);self.t.sendto(d,a)
        echo,proto=await loop.create_datagram_endpoint(Echo,local_addr=('127.0.0.1',0))
        # Reserve TCP listener port; adapter retries are deliberately not hidden.
        reservation=await asyncio.start_server(lambda r,w:w.close(),'127.0.0.1',0)
        port=reservation.sockets[0].getsockname()[1];reservation.close();await reservation.wait_closed()
        task=asyncio.create_task(m.serve_tcp(port,echo.get_extra_info('sockname')[1]));writers=[]
        try:
            await asyncio.sleep(.05)
            for payload in [b'first-peer',b'second-peer']:
                reader,writer=await asyncio.open_connection('127.0.0.1',port);writers.append(writer)
                await m.write_frame(writer,payload);self.assertEqual(await m.read_frame(reader),payload)
            self.assertEqual(len(proto.peers),2)
        finally:
            for w in writers:w.close();await w.wait_closed()
            task.cancel();await asyncio.gather(task,return_exceptions=True);echo.close()
if __name__=='__main__':unittest.main(verbosity=2)
