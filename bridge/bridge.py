#!/usr/bin/env python3
"""WiSense bridge: ESP32 serial (ESP-IDF CSI output) -> WebSocket -> dashboard.

Reads lines like
    CSI_DATA,<seq>,<mac>,<rssi>,...,<len>,<first_word>,"[I Q I Q ...]"
from the receiver ESP32, converts each I/Q pair to an amplitude, and broadcasts
    {"seq": n, "rssi": r, "amp": [64 floats]}
to every connected dashboard on ws://localhost:8765.

It also serves the dashboard folder on http://localhost:8000 so one command is enough.

Examples
    python bridge/bridge.py --port COM5                 # Windows
    python bridge/bridge.py --port /dev/ttyUSB0         # Linux / macOS
    python bridge/bridge.py --replay samples/demo.csv   # no hardware: replay a recording
"""
import argparse, asyncio, functools, http.server, json, math, re, threading, time
from pathlib import Path

N_SC = 64
ARRAY = re.compile(r'\[([^\]]*)\]')


def parse_line(line: str):
    """Return dict(seq, rssi, amp) for a CSI_DATA line, or None."""
    line = line.strip()
    if not line.startswith('CSI_DATA'):
        return None
    m = ARRAY.search(line)
    if not m:
        return None
    try:
        vals = [int(v) for v in m.group(1).replace(',', ' ').split()]
    except ValueError:
        return None
    if len(vals) < 2 * N_SC:
        return None
    head = line[:m.start()].split(',')
    try:
        seq = int(head[1]); rssi = int(head[3])
    except (IndexError, ValueError):
        seq, rssi = 0, 0
    amp = [round(math.hypot(vals[2 * k], vals[2 * k + 1]), 2) for k in range(N_SC)]
    return {'seq': seq, 'rssi': rssi, 'amp': amp}


def serial_lines(port, baud):
    import serial  # imported late so --replay works without pyserial
    with serial.Serial(port, baud, timeout=1) as ser:
        print(f'[bridge] reading {port} @ {baud} baud')
        while True:
            raw = ser.readline()
            if raw:
                yield raw.decode('utf-8', errors='ignore')


def replay_lines(path, rate):
    lines = [l for l in Path(path).read_text().splitlines() if l.startswith('CSI_DATA')]
    if not lines:
        raise SystemExit(f'no CSI_DATA lines in {path}')
    print(f'[bridge] replaying {len(lines)} frames from {path} at {rate} pkt/s (looping)')
    while True:
        for l in lines:
            yield l
            time.sleep(1 / rate)


def start_http(root, port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f'[bridge] dashboard at http://localhost:{port}/')


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', help='serial port of the receiver ESP32 (e.g. COM5, /dev/ttyUSB0)')
    ap.add_argument('--baud', type=int, default=921600)
    ap.add_argument('--replay', help='replay CSI_DATA lines from a text/CSV file instead of a serial port')
    ap.add_argument('--replay-rate', type=float, default=100)
    ap.add_argument('--ws-port', type=int, default=8765)
    ap.add_argument('--http-port', type=int, default=8000)
    ap.add_argument('--no-http', action='store_true')
    a = ap.parse_args()
    if not a.port and not a.replay:
        ap.error('give --port <serial port> or --replay <file>')

    import websockets
    clients = set()

    async def handler(ws):
        clients.add(ws)
        print(f'[bridge] dashboard connected ({len(clients)})')
        try:
            await ws.wait_closed()
        finally:
            clients.discard(ws)

    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    loop = asyncio.get_running_loop()

    def reader():
        src = replay_lines(a.replay, a.replay_rate) if a.replay else serial_lines(a.port, a.baud)
        bad = 0
        for line in src:
            f = parse_line(line)
            if f is None:
                bad += 1
                if bad in (1, 50) and not a.replay:
                    print(f'[bridge] skipped a non-CSI line: {line.strip()[:70]!r}')
                continue
            loop.call_soon_threadsafe(lambda f=f: queue.put_nowait(f) if not queue.full() else None)

    threading.Thread(target=reader, daemon=True).start()
    if not a.no_http:
        start_http(Path(__file__).resolve().parent.parent / 'dashboard', a.http_port)

    async with websockets.serve(handler, '127.0.0.1', a.ws_port):
        print(f'[bridge] websocket on ws://localhost:{a.ws_port}')
        n = 0
        while True:
            f = await queue.get()
            n += 1
            if clients:
                msg = json.dumps(f)
                await asyncio.gather(*(c.send(msg) for c in list(clients)), return_exceptions=True)
            if n % 500 == 0:
                print(f'[bridge] {n} frames forwarded')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
