#!/usr/bin/env python3
"""Read-only loopback lab probe, runnable on TAO or Windows Python 3.10+.
No peer registration: the deliberately short ID is rejected before DB/peer writes
in pinned server/src/rendezvous_server.rs handle_udp (UUID_MISMATCH).
This is transport evidence, never desktop authentication/remote-control E2E.
"""
import argparse, json, socket, sys

def varint(n):
    result = bytearray()
    while n > 127:
        result.append((n & 127) | 128); n >>= 7
    result.append(n)
    return bytes(result)

def field(number, data):
    return varint(number * 8 + 2) + varint(len(data)) + data

def decode(data):
    offset = 0; result = {}
    def integer():
        nonlocal offset
        value = 0
        for shift in range(0, 70, 7):
            if offset >= len(data): raise ValueError('Truncated response')
            b = data[offset]; offset += 1; value |= (b & 127) << shift
            if b < 128: return value
        raise ValueError('Oversized varint')
    while offset < len(data):
        tag = integer(); kind = tag & 7
        if kind == 0: value = integer()
        elif kind == 2:
            size = integer()
            if size > len(data) - offset: raise ValueError('Truncated field')
            value = data[offset:offset + size]; offset += size
        else: raise ValueError('Unexpected protobuf wire type')
        result[tag >> 3] = value
    return result

def exact(sock, n):
    result = bytearray()
    while len(result) < n:
        data = sock.recv(n - len(result))
        if not data: raise ValueError('Connection closed')
        result.extend(data)
    return bytes(result)

def nat():
    with socket.create_connection(('127.0.0.1', 21115), timeout=3) as sock:
        request = field(20, b'')
        sock.sendall(bytes([len(request) << 2]) + request)
        head = exact(sock, 1)
        head += exact(sock, (head[0] & 3))
        size = int.from_bytes(head, 'little') >> 2
        if not 0 < size <= 4096: raise ValueError('Invalid frame size')
        if 21 not in decode(exact(sock, size)): raise ValueError('Not TestNatResponse')

def udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(3)
        # Valid message, invalid ID: early rejection, no generated identity/key.
        request = field(15, field(1, b'probe') + field(2, b'lab') + field(3, b'lab'))
        sock.sendto(request, ('127.0.0.1', 21116))
        data, sender = sock.recvfrom(4096)
        if sender != ('127.0.0.1', 21116): raise ValueError('Unexpected response source')
        if decode(decode(data)[16]).get(1) != 2: raise ValueError('Not UUID_MISMATCH')

def connect(port):
    with socket.create_connection(('127.0.0.1', port), timeout=3): pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator-relay', action='store_true',
                        help='TCP-only transport check for outgoing-only forced-relay lab; UDP stays NOT RUN')
    args = parser.parse_args()
    results = []
    for label, call in [('tcp21115_nat_protocol', nat), ('udp21116_early_reject_roundtrip', udp),
                        ('tcp21116_connect_only', lambda: connect(21116)),
                        ('tcp21117_connect_only', lambda: connect(21117))]:
        if args.operator_relay and label.startswith('udp'):
            results.append({'check': label, 'status': 'NOT RUN', 'required': False,
                            'reason': 'Operator outgoing-only forced-relay lab checks TCP only'})
            continue
        try: call(); results.append({'check': label, 'status': 'PASS'})
        except (OSError, ValueError, KeyError, TypeError) as error:
            results.append({'check': label, 'status': 'FAIL', 'reason': type(error).__name__})
    print(json.dumps({'scope': 'Local transport/protocol probe; not registration, key trust, GUI or E2E',
                      'platform': sys.platform, 'operator_relay_probe': args.operator_relay, 'target': '127.0.0.1', 'results': results}, indent=2))
    sys.exit(0 if all(r['status'] == 'PASS' for r in results if r.get('required', True)) else 1)
