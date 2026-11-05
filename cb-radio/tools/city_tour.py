"""City tour: teleport the truck to every city with the game console (`goto <token>`) and record the
world coordinates from telemetry. Run in a SEPARATE profile; the game window must stay in front.

  city_tour.py test        three cities (berlin, warszawa, madrid) to check the method
  city_tour.py             all cities from map/city_list.json (resumes; done ones are skipped)
Output: map/cities.json  {token: {"name","country","x","y","z"}}; log in map/city_tour.log.
"""
import ctypes
import ctypes.wintypes as w
import json
import math
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / "map" / "city_list.json"
OUT = ROOT / "map" / "cities.json"
LOG = ROOT / "map" / "city_tour.log"
GAME_LOG = Path(r"C:\Users\stray\OneDrive\Документы\Euro Truck Simulator 2\game.log.txt")

u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenFileMappingW.restype = ctypes.c_void_p
k32.MapViewOfFile.restype = ctypes.c_void_p
k32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]

# ---------------------------------------------------------------- keyboard (SendInput)
INPUT_KEYBOARD, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, KEYEVENTF_SCANCODE = 1, 0x2, 0x4, 0x8


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD), ("time", w.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", w.DWORD), ("u", _U)]


def _send(ki):
    i = INPUT(type=INPUT_KEYBOARD)
    i.ki = ki
    u32.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))


def scan(code, hold=0.04):
    _send(KEYBDINPUT(0, code, KEYEVENTF_SCANCODE, 0, 0))
    time.sleep(hold)
    _send(KEYBDINPUT(0, code, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, 0))
    time.sleep(0.05)


def type_text(s):
    for ch in s:
        _send(KEYBDINPUT(0, ord(ch), KEYEVENTF_UNICODE, 0, 0))
        _send(KEYBDINPUT(0, ord(ch), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0))
        time.sleep(0.02)


SC_CONSOLE, SC_ENTER, SC_BACK = 0x56, 0x1C, 0x0E      # console = "§" key on the user's Mac keyboard (0x29 did not work), Enter, Backspace


# ---------------------------------------------------------------- game window / telemetry / log
def game_hwnd():
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, _):
        buf = ctypes.create_unicode_buffer(256)
        u32.GetWindowTextW(h, buf, 256)
        if buf.value.startswith("Euro Truck Simulator 2") and u32.IsWindowVisible(h):
            found.append(h)
        return True
    u32.EnumWindows(cb, 0)
    return found[0] if found else None


def ensure_front():
    h = game_hwnd()
    if not h:
        raise SystemExit("окно игры не найдено")
    if u32.GetForegroundWindow() != h:
        u32.ShowWindow(h, 9)
        u32.SetForegroundWindow(h)
        time.sleep(0.5)
    return u32.GetForegroundWindow() == h


class Tele:
    def __init__(self):
        h = k32.OpenFileMappingW(4, False, "Local\\SimTelemetryETS2")
        if not h:
            raise SystemExit("нет телеметрии — игра запущена?")
        self.p = k32.MapViewOfFile(h, 4, 0, 0, 0)

    def read(self):
        b = ctypes.string_at(self.p, 64)
        t, paused = struct.unpack_from("<II", b, 0)
        x, y, z = struct.unpack_from("<3f", b, 40)
        return t, paused, x, y, z


def log_size():
    return GAME_LOG.stat().st_size if GAME_LOG.exists() else 0


def log_since(pos):
    with GAME_LOG.open("rb") as f:
        f.seek(pos)
        return f.read().decode("utf-8", "replace")


def note(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------- one jump
def jump(tele, token, timeout=20.0):
    """-> (x, y, z) or (None, reason)"""
    if not ensure_front():
        return None, "окно игры не на переднем плане"
    before = tele.read()
    pos = log_size()
    scan(SC_CONSOLE)
    time.sleep(0.4)
    type_text(f"goto {token}")
    time.sleep(0.1)
    scan(SC_ENTER)
    time.sleep(0.6)
    scan(SC_CONSOLE)                                  # close the console so the game runs on
    txt = log_since(pos)
    if f"goto {token}" not in txt:
        return None, "консоль не приняла команду (не открылась?)"
    if "unknown" in txt.lower() or "not found" in txt.lower() or "<ERROR> [cmd]" in txt:
        return None, "игра не знает такой город: " + txt.strip().splitlines()[-1][:120]
    t0 = time.time()
    last, stable_since = None, None
    while time.time() - t0 < timeout:
        time.sleep(0.25)
        t, paused, x, y, z = tele.read()
        moved = abs(x - before[2]) + abs(z - before[4]) > 50
        if not moved:
            continue
        cur = (round(x), round(z))
        if cur == last:
            if stable_since and time.time() - stable_since > 1.0:
                return (x, y, z), ""
            stable_since = stable_since or time.time()
        else:
            last, stable_since = cur, time.time()
    return None, "координаты не изменились за отведённое время"


PLACE = __import__("re").compile(r"Last camera placement: ([-\d.]+);([-\d.]+);([-\d.]+)")


def tour_by_camera(tokens, wait=8.0):
    """`goto` moves the developer CAMERA, not the truck. The game logs "Last camera placement: x;y;z" at
    every goto = where the camera was BEFORE the jump, i.e. the previous city. Keep the console open,
    jump city after city and pair each placement with the previous token. -> {token: (x, y, z)}"""
    res, prev = {}, None

    def wait_click():
        # focus given by SetForegroundWindow is not enough: the game ignores the keyboard until the
        # user CLICKS into it. So just wait for that.
        if u32.GetForegroundWindow() == game_hwnd():
            return
        note("жду: щёлкни мышью по окну игры (дальше ничего не трогай)")
        while u32.GetForegroundWindow() != game_hwnd():
            time.sleep(0.5)
        time.sleep(1.5)
        scan(SC_CONSOLE)
        time.sleep(0.5)

    wait_click()
    scan(SC_CONSOLE)
    time.sleep(0.4)
    misses = 0
    for i, tok in enumerate(tokens + [tokens[0]], 1):      # one extra jump to log the last city
        for attempt in range(3):
            wait_click()
            pos = log_size()
            for _ in range(40):
                scan(SC_BACK, hold=0.005)                   # clear the console line
            type_text(f"goto {tok}")
            scan(SC_ENTER)
            t0, txt = time.time(), ""
            while time.time() - t0 < wait:
                time.sleep(0.2)
                txt = log_since(pos)
                if "Sector force finished" in txt or "<ERROR> [cmd]" in txt:
                    break
            if f"goto {tok}" in txt:
                misses = 0
                break
            # the console got closed (focus blip, a menu...): open it again and retry the same city
            note(f"  {tok}: команда не дошла — открываю консоль заново")
            misses += 1
            if misses >= 6:
                note("6 раз подряд не дошло — останавливаюсь")
                return
            if misses % 3 == 0:          # keys are ignored: probably needs a real click again
                note("игра не принимает клавиши — щёлкни мышью по окну игры")
                while True:
                    time.sleep(0.5)
                    if u32.GetForegroundWindow() != game_hwnd():
                        break
                wait_click()
                continue
            scan(SC_CONSOLE)
            time.sleep(0.6)
        m = PLACE.search(txt)
        if f"goto {tok}" not in txt:
            continue
        elif "<ERROR> [cmd]" in txt:
            note(f"  {tok}: игра не знает такой город")
            continue                                        # camera didn't move: prev stays
        if m and prev and prev not in res:
            res[prev] = tuple(float(v) for v in m.groups())
            yield prev, res[prev]
        prev = tok
    scan(SC_CONSOLE)


def tour_verified(tokens, tele):
    """Robust version: `goto X` twice. The 2nd command logs the camera placement AFTER the 1st jump, i.e. X
    itself; we accept it only if the camera really moved (placement before the 1st jump differs).
    Waits when the game is not in front or is paused (menu open). Yields (token, (x,y,z)) or (token, None)."""
    state = {"console": False}

    def ready():
        said = False
        while True:
            front = u32.GetForegroundWindow() == game_hwnd()
            paused = tele.read()[1]
            if front and not paused:
                if said:
                    time.sleep(1.5)
                    state["console"] = False
                return
            if not said:
                note("жду: щёлкни по окну игры" + (" и закрой меню (Esc)" if front and paused else "")
                     + " — дальше ничего не трогай")
                said = True
            time.sleep(0.5)

    def cmd(text, wait=8.0):
        if not state["console"]:
            scan(SC_CONSOLE)
            time.sleep(0.5)
            state["console"] = True
        pos = log_size()
        for _ in range(40):
            scan(SC_BACK, hold=0.005)
        type_text(text)
        scan(SC_ENTER)
        t0 = time.time()
        while time.time() - t0 < wait:
            time.sleep(0.2)
            txt = log_since(pos)
            if text in txt and ("Sector force finished" in txt or "<ERROR> [cmd]" in txt):
                return txt
        txt = log_since(pos)
        if text in txt:
            return txt
        state["console"] = False          # console was closed (or keys ignored): toggle it next time
        return None

    def placement(txt):
        m = PLACE.search(txt or "")
        return tuple(float(v) for v in m.groups()) if m else None

    for tok in tokens:
        got = None
        for attempt in range(4):
            ready()
            t1 = cmd(f"goto {tok}")
            if t1 is None:
                continue
            if "<ERROR> [cmd]" in t1:
                note(f"  {tok}: игра не знает такой город")
                break
            t2 = cmd(f"goto {tok}")
            if t2 is None:
                continue
            p1, p2 = placement(t1), placement(t2)
            if p1 and p2 and math.hypot(p2[0] - p1[0], p2[2] - p1[2]) > 100:
                got = p2
                break
            note(f"  {tok}: камера не сдвинулась, ещё раз")
        yield tok, got


def main(argv):
    if not (argv and argv[0] == "old"):
        return main_verified(argv)
    cities = json.loads(LIST.read_text(encoding="utf-8"))
    cities = [c for c in cities if c["country"].lower() != "halloween"]
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if argv and argv[0] == "test":
        cities = [c for c in cities if c["token"] in ("berlin", "warszawa", "madrid")]
    todo = [c for c in cities if c["token"] not in done]
    by_tok = {c["token"]: c for c in todo}
    note(f"экскурсия камерой: {len(todo)} городов (уже есть {len(done)})")
    n = 0
    for tok, (x, y, z) in tour_by_camera([c["token"] for c in todo]):
        c = by_tok[tok]
        done[tok] = {"name": c["name"], "country": c["country"].lower(), "x": round(x, 1), "y": round(y, 1), "z": round(z, 1)}
        OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        n += 1
        note(f"[{n}/{len(todo)}] {c['name']} ({c['country']}): x={x:.0f} z={z:.0f}")
    note(f"готово: в таблице {len(done)} городов")


def main_verified(argv):
    cities = [c for c in json.loads(LIST.read_text(encoding="utf-8")) if c["country"].lower() != "halloween"]
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if argv and argv[0] == "test":
        cities = [c for c in cities if c["token"] in ("berlin", "warszawa", "madrid")]
    todo = [c for c in cities if c["token"] not in done]
    by_tok = {c["token"]: c for c in todo}
    note(f"экскурсия (двойной прыжок): {len(todo)} городов (уже есть {len(done)})")
    tele = Tele()
    for n, (tok, p) in enumerate(tour_verified([c["token"] for c in todo], tele), 1):
        c = by_tok[tok]
        if not p:
            note(f"[{n}/{len(todo)}] {c['name']}: НЕТ")
            continue
        done[tok] = {"name": c["name"], "country": c["country"].lower(), "x": round(p[0], 1),
                     "y": round(p[1], 1), "z": round(p[2], 1), "verified": "double-goto"}
        OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        note(f"[{n}/{len(todo)}] {c['name']} ({c['country']}): x={p[0]:.0f} z={p[2]:.0f}")
    scan(SC_CONSOLE)
    note(f"готово: в таблице {len(done)} городов")


def main_old(argv):
    cities = json.loads(LIST.read_text(encoding="utf-8"))
    cities = [c for c in cities if c["country"].lower() != "halloween"]
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if argv and argv[0] == "test":
        cities = [c for c in cities if c["token"] in ("berlin", "warszawa", "madrid")]
    todo = [c for c in cities if c["token"] not in done]
    note(f"экскурсия: {len(todo)} городов (уже есть {len(done)})")
    tele = Tele()
    fails = 0
    for i, c in enumerate(todo, 1):
        res, why = jump(tele, c["token"])
        if res:
            done[c["token"]] = {"name": c["name"], "country": c["country"].lower(),
                                "x": round(res[0], 1), "y": round(res[1], 1), "z": round(res[2], 1)}
            OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
            note(f"[{i}/{len(todo)}] {c['name']} ({c['country']}): x={res[0]:.0f} z={res[2]:.0f}")
            fails = 0
        else:
            note(f"[{i}/{len(todo)}] {c['name']}: НЕТ — {why}")
            fails += 1
            if fails >= 5:
                note("5 неудач подряд — останавливаюсь, надо посмотреть")
                break
    note(f"готово: в таблице {len(done)} городов")


if __name__ == "__main__":
    main(sys.argv[1:])
