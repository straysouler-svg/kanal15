"""Read an ETS2 save (game.sii): ScsC (AES-256-CBC + zlib) -> BSII binary -> {unit type: [units]}.
Only READS a copy of the user's own save, never writes. Used to find the player's hired drivers.
  savegame.py [path to game.sii]    (default: newest save of the most recently played profile on this PC) -> prints drivers
Format notes: public community knowledge (SII_Decrypt); value types handled below, unknown type = stop."""
import struct
import sys
import zlib
from pathlib import Path

KEY = bytes([0x2a, 0x5f, 0xcb, 0x17, 0x91, 0xd2, 0x2f, 0xb6, 0x02, 0x45, 0xb3, 0xd8, 0x36, 0x9e, 0xd0, 0xb2,
             0xc2, 0x73, 0x71, 0x56, 0x3f, 0xbf, 0x1f, 0x3c, 0x9e, 0xdf, 0x6b, 0x11, 0x82, 0x5a, 0x5d, 0x0a])
def _find_saves():
    """The save folder of the most recently played ETS2 profile on this PC (Steam Cloud or local Documents)."""
    import os
    roots = []
    steams = [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"]
    try:                                    # any player's PC: Steam may live on another drive (D:\Steam ...)
        import winreg
        for hive, key, name in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    steams.append(winreg.QueryValueEx(k, name)[0])
            except OSError:
                pass
    except ImportError:
        pass
    for steam in dict.fromkeys(str(Path(s)).lower() for s in steams):
        roots += Path(steam, "userdata").glob("*/227300/remote/profiles/*/save")
    docs = Path(os.path.expanduser("~")) / "Documents" / "Euro Truck Simulator 2"
    onedrive = Path(os.environ.get("OneDrive", "")) / "Документы" / "Euro Truck Simulator 2"
    for base in (docs, onedrive):
        roots += base.glob("profiles/*/save")
        roots += base.glob("steam_profiles/*/save")
    roots = [r for r in roots if any(r.glob("*/game.sii"))]
    if not roots:
        return Path("__no_ets2_saves__")
    return max(roots, key=lambda r: max(f.stat().st_mtime for f in r.glob("*/game.sii")))


SAVES = _find_saves()
CHARS = "0123456789abcdefghijklmnopqrstuvwxyz_"


def aes_cbc_decrypt(key, iv, data):
    """AES via Windows CNG (bcrypt.dll) - no extra Python packages needed."""
    import ctypes
    from ctypes import wintypes
    bc = ctypes.WinDLL("bcrypt")
    alg, hkey = ctypes.c_void_p(), ctypes.c_void_p()
    if bc.BCryptOpenAlgorithmProvider(ctypes.byref(alg), "AES", None, 0):
        raise OSError("BCryptOpenAlgorithmProvider")
    mode = "ChainingModeCBC"
    bc.BCryptSetProperty(alg, "ChainingMode", ctypes.create_unicode_buffer(mode), (len(mode) + 1) * 2, 0)
    kb = ctypes.create_string_buffer(key, len(key))
    if bc.BCryptGenerateSymmetricKey(alg, ctypes.byref(hkey), None, 0, kb, len(key), 0):
        raise OSError("BCryptGenerateSymmetricKey")
    ivb = ctypes.create_string_buffer(iv, len(iv))
    inb = ctypes.create_string_buffer(data, len(data))
    out = ctypes.create_string_buffer(len(data))
    n = wintypes.ULONG()
    st = bc.BCryptDecrypt(hkey, inb, len(data), None, ivb, len(iv), out, len(data), ctypes.byref(n), 0)
    bc.BCryptDestroyKey(hkey)
    bc.BCryptCloseAlgorithmProvider(alg, 0)
    if st:
        raise OSError(f"BCryptDecrypt {st:#x}")
    return out.raw[:n.value]


def decrypt(raw):
    if raw[:4] != b"ScsC":
        return raw
    iv, size = raw[36:52], struct.unpack_from("<I", raw, 52)[0]
    out = zlib.decompress(aes_cbc_decrypt(KEY, iv, raw[56:]))
    assert len(out) == size
    return out


class R:
    def __init__(self, b):
        self.b, self.i = b, 0

    def u8(self):
        self.i += 1
        return self.b[self.i - 1]

    def un(self, fmt):
        v = struct.unpack_from(fmt, self.b, self.i)
        self.i += struct.calcsize(fmt)
        return v if len(v) > 1 else v[0]

    def s(self):
        n = self.un("<I")
        self.i += n
        return self.b[self.i - n:self.i].decode("utf-8", "replace")

    def enc(self):
        v = self.un("<Q")
        out = []
        while v:
            v, r = divmod(v, 38)
            out.append(CHARS[r - 1] if r else "")
        return "".join(out)

    def uid(self):
        n = self.u8()
        if n == 0xFF:
            return "_nameless." + format(self.un("<Q"), "x")
        return ".".join(self.enc() for _ in range(n))


def parse(b):
    r = R(b)
    assert b[:4] == b"BSII", b[:4]
    r.i = 4
    ver = r.un("<I")
    structs, units = {}, {}
    while r.i < len(b):
        bt = r.un("<I")
        if bt == 0:
            if r.u8() == 0:
                break
            sid, name, fields = r.un("<I"), r.s(), []
            while True:
                vt = r.un("<I")
                if vt == 0:
                    break
                fname = r.s()
                ords = None
                if vt == 0x37:
                    ords = {}
                    for _ in range(r.un("<I")):
                        k = r.un("<I")
                        ords[k] = r.s()
                fields.append((vt, fname, ords))
            structs[sid] = (name, fields)
            continue
        name, fields = structs[bt]
        unit = {"_id": r.uid()}
        for vt, fname, ords in fields:
            unit[fname] = value(r, vt, ords, ver)
        units.setdefault(name, []).append(unit)
    return units


def value(r, vt, ords, ver):
    arr = lambda f: [f() for _ in range(r.un("<I"))]   # noqa: E731
    if vt == 0x01: return r.s()
    if vt == 0x02: return arr(r.s)
    if vt == 0x03: return r.enc()
    if vt == 0x04: return arr(r.enc)
    if vt == 0x05: return r.un("<f")
    if vt == 0x06: return arr(lambda: r.un("<f"))
    if vt == 0x07: return r.un("<2f")
    if vt == 0x08: return arr(lambda: r.un("<2f"))
    if vt == 0x09: return r.un("<3f")
    if vt == 0x0A: return arr(lambda: r.un("<3f"))
    if vt == 0x11: return r.un("<3i")
    if vt == 0x12: return arr(lambda: r.un("<3i"))
    if vt == 0x17: return r.un("<4f")
    if vt == 0x18: return arr(lambda: r.un("<4f"))
    if vt == 0x19: return r.un("<8f")
    if vt == 0x1A: return arr(lambda: r.un("<8f"))
    if vt == 0x25: return r.un("<i")
    if vt == 0x26: return arr(lambda: r.un("<i"))
    if vt in (0x27, 0x2F): return r.un("<I")
    if vt == 0x28: return arr(lambda: r.un("<I"))
    if vt == 0x29: return r.un("<h")
    if vt == 0x2A: return arr(lambda: r.un("<h"))
    if vt == 0x2B: return r.un("<H")
    if vt == 0x2C: return arr(lambda: r.un("<H"))
    if vt == 0x31: return r.un("<q")
    if vt == 0x32: return arr(lambda: r.un("<q"))
    if vt == 0x33: return r.un("<Q")
    if vt == 0x34: return arr(lambda: r.un("<Q"))
    if vt == 0x35: return bool(r.u8())
    if vt == 0x36: return arr(lambda: bool(r.u8()))
    if vt == 0x37:
        k = r.un("<I")
        return ords.get(k, k) if ords else k
    if vt in (0x39, 0x3B, 0x3D): return r.uid()
    if vt in (0x3A, 0x3C, 0x3E): return arr(r.uid)
    raise ValueError(f"unknown value type {vt:#x} at {r.i}")


def newest_save():
    return max(SAVES.glob("*/game.sii"), key=lambda p: p.stat().st_mtime)


def load(path=None):
    p = Path(path) if path else newest_save()
    return parse(decrypt(p.read_bytes())), p


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    units, p = load(sys.argv[1] if len(sys.argv) > 1 else None)
    print(p, {k: len(v) for k, v in sorted(units.items(), key=lambda kv: -len(kv[1]))[:25]})
    for d in units.get("driver_ai", [])[:3]:
        print(d)
