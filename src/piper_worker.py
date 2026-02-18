#!/usr/bin/env python3
import sys
import os
import json
import time
import socket
import struct
import select
import subprocess
import audioop
import threading
from pathlib import Path
from queue import Queue, Empty

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

PIPER_BIN = "./piper/piper"
# ⚡ OPTIMIZATION 1: Use the LOW quality model
MODEL = "models/en_US-amy-low.onnx" 
MODEL_JSON = Path(MODEL + ".json")

SOURCE_PORT = 17032

# RTP Config
rtp_seq = 1
rtp_ts = 0
rtp_ssrc = 0x12345678
RTP_FRAME_MS = 20
SAMPLES_PER_FRAME_8K = 160
PCM_BYTES_PER_FRAME_8K = SAMPLES_PER_FRAME_8K * 2

cmd_q: "Queue[dict]" = Queue()
play_q: "Queue[str]" = Queue()

active_id = None
active_host = None
active_port = None
first_chunk = True
in_playback = False

_cancel_lock = threading.Lock()
_cancel_id = None

def set_cancel(stream_id: str | None):
    global _cancel_id
    with _cancel_lock:
        _cancel_id = stream_id

def is_cancelled(stream_id: str | None) -> bool:
    with _cancel_lock:
        if _cancel_id is None: return False
        if _cancel_id == "*": return True
        return stream_id is not None and _cancel_id == stream_id

def load_voice_sample_rate(default_sr=22050) -> int:
    try:
        cfg = json.loads(MODEL_JSON.read_text(encoding="utf-8"))
        return int(cfg.get("audio", {}).get("sample_rate", default_sr))
    except Exception:
        return default_sr

def stdin_reader():
    for line in sys.stdin:
        line = (line or "").strip()
        if not line: continue
        try:
            msg = json.loads(line)
            cmd = (msg.get("cmd") or "").lower()
            if cmd == "cancel":
                set_cancel(msg.get("id") or "*")
                cmd_q.put({"cmd": "__cancel__", "id": msg.get("id") or "*"})
                continue
            cmd_q.put(msg)
        except Exception:
            continue

def rtp_send_preroll(sock, dst_host, dst_port, frames, marker, stream_id):
    global rtp_seq, rtp_ts
    silence = b"\x00" * PCM_BYTES_PER_FRAME_8K
    ulaw = audioop.lin2ulaw(silence, 2)
    for i in range(frames):
        if is_cancelled(stream_id): return False
        mbit = 0x80 if (marker and i == 0) else 0x00
        hdr = struct.pack("!BBHII", 0x80, mbit, rtp_seq & 0xFFFF, rtp_ts, rtp_ssrc)
        sock.sendto(hdr + ulaw, (dst_host, dst_port))
        rtp_seq = (rtp_seq + 1) & 0xFFFF
        rtp_ts += SAMPLES_PER_FRAME_8K
        time.sleep(RTP_FRAME_MS / 1000.0)
    return True

def stream_chunk_to_rtp(sock: socket.socket, text: str, dst_host: str, dst_port: int, voice_sr: int,stream_id: str, is_first: bool):
    """
    ⚡ OPTIMIZATION 2: Stream & Resample simultaneously using audioop.ratecv
    """
    if not rtp_send_preroll(sock, dst_host, dst_port, 1, True, stream_id):
        return "cancelled"

    piper = subprocess.Popen(
        [PIPER_BIN, "-m", MODEL, "--output-raw"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0
    )
    
    try:
        piper.stdin.write((text.strip() + "\n").encode("utf-8"))
        piper.stdin.close()
    except Exception:
        return "cancelled" if is_cancelled(stream_id) else "error"

    out_fd = piper.stdout.fileno()
    os.set_blocking(out_fd, False)

    # State for streaming resampler
    resample_state = None
    accum_8k = bytearray()
    
    global rtp_seq, rtp_ts
    next_send = time.perf_counter()

    while True:
        if is_cancelled(stream_id):
            piper.kill()
            return "cancelled"

        # 1. Read small chunks from Piper (don't wait for EOF)
        r, _, _ = select.select([piper.stdout], [], [], 0.005)
        raw_chunk = b""
        if r:
            try:
                raw_chunk = piper.stdout.read(4096) # Read whatever is ready
            except BlockingIOError:
                pass
        
        is_eof = (piper.poll() is not None) and (not raw_chunk)

        # 2. Resample chunk immediately
        if raw_chunk:
            # audioop.ratecv maintains state, ensuring no clicks at chunk boundaries
            frag_8k, resample_state = audioop.ratecv(
                raw_chunk, 2, 1, voice_sr, 8000, resample_state
            )
            accum_8k.extend(frag_8k)

        # 3. Stream 8k frames as soon as we have enough data
        while len(accum_8k) >= PCM_BYTES_PER_FRAME_8K:
            if is_cancelled(stream_id): return "cancelled"

            # Strict timing control
            now = time.perf_counter()
            if now < next_send:
                time.sleep(next_send - now)

            frame_bytes = accum_8k[:PCM_BYTES_PER_FRAME_8K]
            del accum_8k[:PCM_BYTES_PER_FRAME_8K]

            ulaw = audioop.lin2ulaw(bytes(frame_bytes), 2)
            hdr = struct.pack("!BBHII", 0x80, 0x00, rtp_seq & 0xFFFF, rtp_ts, rtp_ssrc)
            sock.sendto(hdr + ulaw, (dst_host, dst_port))

            rtp_seq = (rtp_seq + 1) & 0xFFFF
            rtp_ts += SAMPLES_PER_FRAME_8K
            next_send += (RTP_FRAME_MS / 1000.0)

        if is_eof:
            break

    piper.stdout.close()
    try: piper.wait(timeout=0.5)
    except: pass
    return "ok"

def main():
    global active_id, active_host, active_port, first_chunk, in_playback
    voice_sr = load_voice_sample_rate()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", SOURCE_PORT))
    threading.Thread(target=stdin_reader, daemon=True).start()
    print(json.dumps({"type": "ready"}), flush=True)

    while True:
        try: msg = cmd_q.get(timeout=0.01)
        except Empty: msg = None

        if msg:
            cmd = (msg.get("cmd") or "").lower()
            if cmd == "begin":
                active_id = msg.get("id")
                active_host = (msg.get("host") or "").strip()
                active_port = int(msg.get("port") or 0)
                set_cancel(None)
                first_chunk = True
                while not play_q.empty(): play_q.get_nowait()
                print(json.dumps({"type": "begun", "id": active_id}), flush=True)
                continue
            if cmd == "__cancel__":
                # ... same cancel logic as before ...
                if active_id and not in_playback:
                     print(json.dumps({"type": "done", "id": active_id, "status": "cancelled"}), flush=True)
                     active_id = None
                continue
            if cmd == "chunk":
                if active_id and msg.get("id") == active_id:
                    play_q.put(msg.get("text"))
                continue
            if cmd == "end":
                if active_id and msg.get("id") == active_id:
                    play_q.put("__END__")
                continue

        try: item = play_q.get_nowait()
        except Empty: continue

        if item == "__END__":
            print(json.dumps({"type": "done", "id": active_id, "status": "ok"}), flush=True)
            active_id = None
            continue

        if active_id:
            in_playback = True
            try:
                status = stream_chunk_to_rtp(sock, item, active_host, active_port, voice_sr, active_id, first_chunk)
            finally:
                in_playback = False
            first_chunk = False
            if status == "cancelled":
                print(json.dumps({"type": "done", "id": active_id, "status": "cancelled"}), flush=True)
                active_id = None

if __name__ == "__main__":
    main()