"""Find the job (destination city/company, cargo) and the navigation distance/time left in the telemetry
memory maps. Run while the game is running WITH a job and you are DRIVING (navigator on):
  probe_job.py [seconds]   (default 25)
Dumps strings with offsets, then lists numbers that went DOWN like a distance/time-to-go -> probe_job.txt"""
import ctypes
import struct
import sys
import time
from ctypes import wintypes
from pathlib import Path

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.OpenFileMappingW.restype = wintypes.HANDLE
k.MapViewOfFile.restype = ctypes.c_void_p
k.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p), ("AllocationProtect", wintypes.DWORD),
                ("PartitionId", wintypes.WORD), ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]


def snap(name):
    h = k.OpenFileMappingW(4, False, name)
    if not h:
        return None
    p = k.MapViewOfFile(h, 4, 0, 0, 0)
    m = MBI()
    k.VirtualQuery(ctypes.c_void_p(p), ctypes.byref(m), ctypes.sizeof(m))
    return ctypes.string_at(p, min(m.RegionSize, 64 * 1024))


def strings(b, minlen=3):
    out, cur, start = [], bytearray(), 0
    for i, c in enumerate(b):
        if 32 <= c < 127 or c >= 0xC0 or (0x80 <= c < 0xC0 and cur):
            if not cur:
                start = i
            cur.append(c)
        else:
            if len(cur) >= minlen:
                out.append((start, cur.decode("utf-8", "replace")))
            cur = bytearray()
    return out


def main():
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 25
    names = ["Local\\SimTelemetryETS2", "Local\\SHSCSTelemetry", "Local\\SCSTelemetry", "Local\\Ets2TelemetryServer"]
    a = {n: snap(n) for n in names}
    lines = []
    for n, b in a.items():
        lines.append(f"== {n}: {'нет' if b is None else len(b)} байт")
        if b:
            for off, s in strings(b):
                if any(ch.isalpha() for ch in s) and len(s.strip()) >= 3:
                    lines.append(f"  str @{off}: {s[:80]}")
    # the game pauses when its window loses focus: wait until it really drives, then measure while driving
    def driving():
        b = snap("Local\SimTelemetryETS2")
        return b and not struct.unpack_from("<I", b, 4)[0], b and struct.unpack_from("<I", b, 0)[0]
    t_end = time.time() + 900
    while time.time() < t_end:
        ok1, t1 = driving()
        time.sleep(1.0)
        ok2, t2 = driving()
        if ok1 and ok2 and t1 != t2:
            break
    else:
        print("игра так и не поехала за 15 минут"); return
    a = {n: snap(n) for n in names}
    print(f"игра едет: замер {secs:.0f} с...", flush=True)
    time.sleep(secs)
    if not driving()[0]:
        print("игра встала на паузу во время замера — повтори"); return
    for n in names:
        b0, b1 = a[n], snap(n)
        if not b0 or not b1:
            continue
        lines.append(f"== {n}: числа, которые уменьшились за {secs:.0f} с")
        for off in range(0, min(len(b0), len(b1)) - 4, 4):
            for fmt, kind in (("<f", "f32"), ("<i", "i32")):
                v0, v1 = struct.unpack_from(fmt, b0, off)[0], struct.unpack_from(fmt, b1, off)[0]
                if not (v0 == v0 and v1 == v1) or v0 == v1:
                    continue
                d = v0 - v1
                if 50 < v0 < 5e6 and 0 < d < 0.2 * v0 and d > 1:   # a distance in m or a time in s going down
                    lines.append(f"  {kind} @{off}: {v0:.1f} -> {v1:.1f} (−{d:.1f})")
    out = Path(__file__).resolve().parents[1] / "probe_job.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"готово: {out} ({len(lines)} строк)")


if __name__ == "__main__":
    main()
