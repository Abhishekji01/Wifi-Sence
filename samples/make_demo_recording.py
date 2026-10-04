#!/usr/bin/env python3
"""Write a synthetic recording in the ESP-IDF CSI_DATA format so the bridge can be tried without hardware.

    python samples/make_demo_recording.py            # writes samples/demo_breathing.csv
    python bridge/bridge.py --replay samples/demo_breathing.csv
"""
import math, random, sys
from pathlib import Path

random.seed(1)
frames = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
base = [28 + 6 * math.sin(k / 9) for k in range(64)]
rows = []
for i in range(frames):
    t = i / 100
    amp = [b + 0.3 * math.sin(2 * math.pi * 0.3 * t) * (0.5 + (k % 7) / 7) + random.gauss(0, 0.5) for k, b in enumerate(base)]
    iq = []
    for a in amp:
        ph = random.uniform(0, 2 * math.pi)
        iq += [int(a * math.cos(ph)), int(a * math.sin(ph))]
    rows.append(f'CSI_DATA,{i},aa:bb:cc:dd:ee:ff,-45,11,1,6,0,1,1,0,0,0,0,0,-92,0,6,0,{i * 10000},0,0,0,{len(iq)},0,"[{",".join(map(str, iq))}]"')
out = Path(__file__).with_name('demo_breathing.csv')
out.write_text('\n'.join(rows) + '\n')
print('wrote', out, f'({frames} frames, breathing at 0.30 Hz = 18/min)')
