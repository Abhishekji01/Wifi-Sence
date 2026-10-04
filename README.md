# WiSense

Camera-free sensing with Wi-Fi CSI. Two ESP32 boards, no camera, no image, no wearable.
WiSense reads how a person's body changes the Wi-Fi channel and turns that into presence, breathing rate and fall alerts.

*Sensing where cameras fail.* Screening aid, not a medical device.

## Live dashboard

Open `dashboard/index.html` in a browser. It needs no install and works offline.

- **Simulated signal (default).** A CSI generator runs in the page, so the demo works without hardware. Pick a scenario: empty room, sitting still, deep breathing, walking, fall.
- **Live from ESP32.** Press *Connect to ESP32 bridge* to switch to real CSI from your boards (see below).

The detection code is the same for both modes: Hampel filter, 0.1 to 0.6 Hz band-pass, 20 s FFT window, then rules for presence, breathing (0.2 to 0.5 Hz peak, rate = 60 × f) and fall (burst of movement, then stillness). Thresholds come from an empty-room calibration (first 12 s, or the *Calibrate on empty room* button), not from hard-coded numbers.

## Run with real hardware

1. Flash the receiver ESP32 with an ESP-IDF CSI firmware that prints `CSI_DATA,...,"[I Q I Q ...]"` lines over serial (for example the `esp-csi` `csi_recv` example), and the transmitter with the matching sender.
2. Install the bridge and start it:

```bash
pip install -r bridge/requirements.txt
python bridge/bridge.py --port COM5          # Linux/macOS: --port /dev/ttyUSB0
```

3. Open http://localhost:8000/ , press *Connect to ESP32 bridge*, keep the room empty, press *Calibrate on empty room*, then walk in.

No hardware yet? Replay a synthetic recording:

```bash
python samples/make_demo_recording.py
python bridge/bridge.py --replay samples/demo_breathing.csv
```

## Layout

| Path | What it is |
|---|---|
| `dashboard/index.html` | Single-file dashboard: room view, status, signal, spectrum, sub-carrier heatmap, pipeline, event log |
| `bridge/bridge.py` | Serial to WebSocket bridge, also serves the dashboard |
| `samples/` | Generator for a synthetic CSI recording |

## Status and limits

- The simulator, detection pipeline and bridge are tested against the simulated signal and the synthetic recording. They have not yet been tuned on real two-board captures, so expect to recalibrate and adjust thresholds per room.
- Parameters (about 100 packets/s, 20 s window, 921600 baud) are design targets until measured.
- Fall detection reacts to "burst, then still", so abruptly sitting down can false-alarm. Treat it as an alert to check, not a diagnosis.
