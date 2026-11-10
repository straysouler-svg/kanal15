"""CB radio for ETS2, level 3: rare idle chatter from pre-generated phrases.

Runs in the background next to the game. Plays one random phrase every few minutes
while you drive; silent when the game is paused, in a menu, closed, or the engine is off.
Phrases never repeat until all of them have been heard (state survives restarts).

  cb_radio.py            normal mode (waits for the game)
  cb_radio.py --listen   play every phrase now, one by one, no game needed
  cb_radio.py --now      play one phrase from the deck right now
  cb_radio.py --devices  list audio outputs (for "device" in config.json)
  cb_radio.py --ptt-test print every wheel/joystick button press (to find the push-to-talk number)
Push-to-talk ("ptt" in config.json: SDL device name part + 0-based button): while held, the radio
goes quiet (you are transmitting) and your microphone ("mic" in config.json, default fifine) is recorded;
after release your words are recognised LOCALLY (faster-whisper small, CPU) and understood by intents.py
(topic + who you called by name) - the right person answers with a pre-voiced line.
Last recording: last_ptt.wav (for checking what was heard).
No network is used.
"""
import os

os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# numpy and scipy each bring OpenBLAS, which reserves ~32 MB per CPU thread (20 here) -> +1.2 GB of commit for
# nothing (we never do big matrix maths). With ETS2 committing 16 GB the system ran out of virtual memory and
# MOZA Pit House died (2026-11-03). One thread is plenty.
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import ctypes  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import socket  # noqa: E402
import struct  # noqa: E402
import threading  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import sounddevice as sd  # noqa: E402
import soundfile as sf  # noqa: E402

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent   # next to CB-Radio.exe when frozen
CFG_FILE = ROOT / "config.json"
STATE_FILE = ROOT / "state.json"
LOG_FILE = ROOT / "cb_radio.log"

AUDIO = ROOT / "audio" / "level3"
SCENES = ROOT / "audio" / "scenes"
FX = ROOT / "audio" / "fx"
REACT = ROOT / "audio" / "reactions"
PHRASES_JSON = ROOT / "phrases" / "level3_eleven.json"
AUDIO_ROOT = ROOT / "audio"


def snd(p):
    """A sound file as .wav or, in a shared (compressed) build, .ogg (Opus) - whichever exists."""
    p = Path(p)
    if p.exists():
        return p
    o = p.with_suffix(".ogg")
    return o if o.exists() else p


def snd_glob(d, pattern):
    """glob for sounds in either format ("*.wav" also finds the .ogg ones), one per name."""
    seen = {}
    for ext in (".wav", ".ogg"):
        for f in Path(d).glob(pattern.replace(".wav", ext)):
            seen.setdefault((f.parent, f.stem), f)
    return sorted(seen.values())


# ---- which version of the lines that call the player by name (config "variant", 2026-11-04):
# "" = the original (Железяка), "kirill" = for Кирилл, "neutral" = no name (public build).
VARIANT = ""
BUILD_NAME = ""               # config "build" (set by pack_release): kirill / <customer> -> reactions/only_<build>
HANDLE_LINES = set()          # "reactions/player/greet/01", ... - lines that call the player by name


def load_variant(cfg):
    global VARIANT, BUILD_NAME
    BUILD_NAME = str(cfg.get("build") or "")
    VARIANT = str(cfg.get("variant") or "")
    if not VARIANT:
        return
    try:
        d = json.loads(PHRASES_JSON.read_text(encoding="utf-8"))
        for sid, ls in d.get("scenes", {}).items():
            for i, ln in enumerate(ls, 1):
                if "v_neutral" in ln:
                    HANDLE_LINES.add(f"scenes/{sid}/{i:02d}")
        for g, ks in d.get("reactions", {}).items():
            if g.startswith("_"):
                continue
            for k, ls in ks.items():
                if k.startswith("_"):
                    continue
                for i, ln in enumerate(ls, 1):
                    if "v_neutral" in ln:
                        HANDLE_LINES.add(f"reactions/{g}/{k}/{i:02d}")
    except (OSError, ValueError):
        pass


def _rel(p):
    try:
        return Path(p).relative_to(AUDIO_ROOT).with_suffix("").as_posix()
    except ValueError:
        return None


def variant_of(p):
    """The file to play for this line in the chosen variant; None = this line must not be played
    (it calls the player by a name and has no version for this variant yet)."""
    if not VARIANT:
        return p
    rel = _rel(p)
    if rel is None or rel not in HANDLE_LINES:
        return p
    alt = snd(AUDIO_ROOT / "variants" / VARIANT / (rel + ".wav"))
    return alt if alt.exists() else None
OFFLINE_S = 40 * 60     # after a sign-off the actor is silent this long

DEFAULT_CFG = {
    "gap_min_s": 300,          # pause between phrases: random in [min, max]
    "gap_max_s": 720,
    "first_after_s": [60, 180],  # first phrase after this much driving
    "volume": 0.8,
    "device": None,            # None = Windows default output; or part of a device name
    "require_engine_on": True,
    "kerchunk_gap_s": [100, 320],  # empty push-to-talk clicks between phrases; [] = off
    "greet_reply_chance": 0.85,    # someone answers an actor's hello
    "ptt": {"device": "R5 Base", "button": 23},  # 0-based (pygame); ETS2 controls.sii joy.bN = N-1
    "lock_port": 47819,
    "update": {"url": "", "channel": "public", "auto": True},   # tools/pack_release.py fills url + channel per build
}


def log(msg, ch=None):
    """Журнал рации (переделка 09.11, спека в STATUS.md): новые строки СВЕРХУ файла (запись
    порциями-буфером), схлопывание повторов ×N, префиксы-каналы [эфир]/[тангента]/[дружба]/[тех]/
    [ОШИБКА], тех. шум — только при --verbose, кап ~10 МБ (хвост — в cb_radio_archive.log),
    ошибки с traceback — в cb_radio_errors.log."""
    now = datetime.now()
    if ch is None:
        low = msg.lower()
        ch = ("ОШИБКА" if low.startswith(("traceback", "ошибк", "error", "крэш"))
              else "тангента" if low.startswith("тангента")
              else "дружба" if low.startswith(("дружба", "настроение", "переход"))
              else "тех" if low.startswith(("компания", "обновления", "плагин", "значок", "папка рации",
                                            "доставки", "установщик", "тангента через", "winmm", "selftest"))
              else "эфир")
    if ch == "тех" and not VERBOSE:
        return
    line = f"{now:%H:%M:%S} [{ch}] {msg}"
    try:
        print(line, flush=True)
    except (UnicodeEncodeError, OSError, ValueError, AttributeError):
        pass    # a cp1251 console can't print «→» (06.11: the radio died on start); the log file is what matters
    if ch == "ОШИБКА":
        _append_file(ERR_FILE, line + "\n", ERR_CAP)
    if _log_buf and _log_buf[-1][0] == line:
        _log_buf[-1][1] += 1
        return
    _log_buf.append([line, 1])
    now_m = time.monotonic()
    if now_m - _flush_t[0] > _FLUSH_EVERY:
        _flush_log()


LOG_CAP = 10 * 1024 * 1024            # головной cb_radio.log ~10 МБ, хвост — в архив
ERR_CAP = 5 * 1024 * 1024
ARC_KEEP = 90 * 1024 * 1024           # архив: одна ротация, суммарно ≤100 МБ
ERR_FILE = ROOT / "cb_radio_errors.log"
ARC_FILE = ROOT / "cb_radio_archive.log"
VERBOSE = "--verbose" in sys.argv
_FLUSH_EVERY = 2.0
_log_buf = []          # [[text, count]] — порция до флаша
_flush_t = [time.monotonic()]


def _append_file(path, chunk, cap):
    try:
        old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        body = chunk + old
        enc = body.encode("utf-8")
        if len(enc) > cap:
            keep = enc[: cap // 2].decode("utf-8", "ignore")
            body = keep
        path.write_text(body, encoding="utf-8")
    except OSError:
        pass


def _flush_log():
    """Записать накопленную порцию СВЕРХУ файла; при превышении капа — хвост в архив."""
    if not _log_buf:
        return
    _flush_t[0] = time.monotonic()
    chunk = "".join(t + (f"  ×{n}" if n > 1 else "") + "\n" for t, n in reversed(_log_buf))
    _log_buf.clear()
    try:
        old = LOG_FILE.read_text(encoding="utf-8", errors="replace") if LOG_FILE.exists() else ""
        body = chunk + old
        enc = body.encode("utf-8")
        if len(enc) > LOG_CAP:
            head_b = enc[: LOG_CAP // 2]
            tail_b = enc[LOG_CAP // 2:]
            try:
                arc_old = ARC_FILE.read_bytes() if ARC_FILE.exists() else b""
                ARC_FILE.write_bytes((tail_b + arc_old)[:ARC_KEEP])
            except OSError:
                pass
            body = head_b.decode("utf-8", "ignore")
        LOG_FILE.write_text(body, encoding="utf-8")
    except OSError:
        pass


def _log_excepthook(exc_type, exc, tb):
    import traceback
    _append_file(ERR_FILE, "".join(traceback.format_exception(exc_type, exc, tb)), ERR_CAP)
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _log_excepthook
try:
    threading.excepthook = lambda a: _append_file(
        ERR_FILE, "".join(__import__("traceback").format_exception(a.exc_type, a.exc_value, a.exc_tb)), ERR_CAP)
except (AttributeError, OSError):
    pass
import atexit  # noqa: E402
atexit.register(_flush_log)


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    if CFG_FILE.exists():
        cfg.update(json.loads(CFG_FILE.read_text(encoding="utf-8-sig")))
    else:
        CFG_FILE.write_text(json.dumps(DEFAULT_CFG, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


# ---------------------------------------------------------------- telemetry
_k = ctypes.WinDLL("kernel32", use_last_error=True)
_k.OpenFileMappingW.restype = ctypes.c_void_p
_k.MapViewOfFile.restype = ctypes.c_void_p
_k.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]


class Game:
    """Is the player driving right now? Reads Local\\SimTelemetryETS2 (Funbit plugin, already installed)."""

    def __init__(self):
        self._p = None
        self._last_t = None
        self._last_change = 0.0

    def _open(self):
        h = _k.OpenFileMappingW(4, False, "Local\\SimTelemetryETS2")
        if h:
            self._p = _k.MapViewOfFile(h, 4, 0, 0, 0)

    def state(self, require_engine):
        if not self._p:
            self._open()
            if not self._p:
                return "no_game"
        b = ctypes.string_at(self._p, 600)
        t, paused = struct.unpack_from("<II", b, 0)
        now = time.monotonic()
        if t != self._last_t:
            self._last_t, self._last_change = t, now
        if paused:
            return "paused"
        if now - self._last_change > 3:      # game time frozen: closed or loading
            return "no_game"
        if require_engine and not b[585]:
            return "engine_off"
        return "driving"

    def wipers(self):
        """Your wipers are on = it rains around you (Funbit map byte 581)."""
        if not self._p:
            return False
        return bool(ctypes.string_at(self._p, 600)[581])

    def pos(self):
        """(x, z, game minutes) - truck world position and the game clock (minutes since game start)."""
        if not self._p:
            return None
        b = ctypes.string_at(self._p, 200)
        x, _, z = struct.unpack_from("<3f", b, 40)
        return x, z, struct.unpack_from("<I", b, 160)[0]


class Fines:
    """Your fines from the SimHub telemetry map (Local\\SHSCSTelemetry; offsets found 2026-11-03:
    offence string @3436, amount int32 @4216, flag @4304). poll() -> offence string once per new fine."""
    def __init__(self):
        self._p, self._last = None, None

    def dest(self):
        """Destination city id of your job (offset found 2026-11-04 with tools/probe_job.py), "" = no job."""
        if not self._p:
            return ""
        return ctypes.string_at(self._p + 2684, 64).split(b"\0")[0].decode("ascii", "replace")

    def poll(self):
        if not self._p:
            # 1.26: our own RenCloud plugin first (ships with the radio), SimHub's renamed copy as a fallback
            for name in ("Local\\SCSTelemetry", "Local\\SHSCSTelemetry"):
                h = _k.OpenFileMappingW(4, False, name)
                if h:
                    self._p = _k.MapViewOfFile(h, 4, 0, 0, 0)
                    log("штрафы и заказ: читаю " + name.split(chr(92))[-1])
                    break
            if not self._p:
                return None
        b = ctypes.string_at(self._p, 4400)
        offence = b[3436:3500].split(b"\0")[0].decode("ascii", "replace")
        sig = (offence, struct.unpack_from("<i", b, 4216)[0], struct.unpack_from("<i", b, 4304)[0])
        if self._last is None:
            self._last = sig                 # whatever was there before we started is old news
            return None
        if sig != self._last and offence:
            self._last = sig
            return offence
        self._last = sig
        return None


# ---------------------------------------------------------------- push-to-talk
class _JOYCAPSW(ctypes.Structure):
    _fields_ = ([("wMid", ctypes.c_uint16), ("wPid", ctypes.c_uint16), ("szPname", ctypes.c_wchar * 32)]
                + [(n, ctypes.c_uint) for n in ("wXmin", "wXmax", "wYmin", "wYmax", "wZmin", "wZmax", "wNumButtons",
                                               "wPeriodMin", "wPeriodMax", "wRmin", "wRmax", "wUmin", "wUmax", "wVmin",
                                               "wVmax", "wCaps", "wMaxAxes", "wNumAxes", "wMaxButtons")]
                + [("szRegKey", ctypes.c_wchar * 32), ("szOEMVxD", ctypes.c_wchar * 260)])


class _JOYINFOEX(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint32) for n in ("dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos",
                                               "dwVpos", "dwButtons", "dwButtonNumber", "dwPOV", "dwR1", "dwR2")]


def _oem_name(vid, pid):
    """Device name Windows shows in joy.cpl ("R5 Base") - winmm itself only says "PC joystick"."""
    import winreg
    key = rf"System\CurrentControlSet\Control\MediaProperties\PrivateProperties\Joystick\OEM\VID_{vid:04X}&PID_{pid:04X}"
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, key) as k:
                return winreg.QueryValueEx(k, "OEMName")[0]
        except OSError:
            pass
    return ""


def _input_name(key):
    """pynput key/button -> the name config.json stores (one rule for PTT and the rebind dialog)."""
    return key.name if hasattr(key, "name") else (key.char if getattr(key, "char", None) else str(key))


_WINMM_LOCK = threading.RLock()    # все вызовы winmm из любого потока — только через него (crash.log 08.11.2026);
                                   # RLock: _scan_winmm лочит и вызывает _winmm_buttons


def _winmm_buttons(mm, ids=range(16)):
    """{id: (device name, pressed-buttons bitmask)} of winmm joysticks - shared by PTT and the rebind dialog.
    ctypes отпускает GIL на время нативного вызова, а winmm не потокобезопасен: PTT.poll (main) и опрос
    диалога переназначения (поток pystray, каждые 40 мс) попадали в DLL одновременно и роняли процесс
    heap corruption 0xc0000374 внутри winmm при USB-шторме. Лочим всё перечисление целиком."""
    out = {}
    for i in ids:
        caps = _JOYCAPSW()
        ji = _JOYINFOEX()
        ji.dwSize, ji.dwFlags = ctypes.sizeof(ji), 0x80        # JOY_RETURNBUTTONS
        try:
            with _WINMM_LOCK:
                if mm.joyGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) != 0:
                    continue
                if mm.joyGetPosEx(i, ctypes.byref(ji)) != 0:
                    continue
        except Exception:
            continue                                  # winmm отказал — устройство пропускаем, эфир не падает
        out[i] = (_oem_name(caps.wMid, caps.wPid) or f"{caps.wMid:04X}:{caps.wPid:04X}", ji.dwButtons)
    return out


class PTT:
    """Push-to-talk = a wheel button, a keyboard key (1.27) or a mouse button (1.28). Read straight from Windows
    (winmm joyGetPosEx for wheel buttons 0-31, pynput listeners for keyboard/mouse): ~1.5 % of a core. pygame/SDL
    opened all 5 controllers with its own thread and cost 7-20 % (measured 2026-11-03) - it stays only as a fallback
    (button >= 32, winmm can't see the device, or "backend": "pygame" in config ptt). Survives the wheel
    reconnecting (Pit House re-plugs the R5 base when a game starts). 1.28: the tray «переназначить кнопку» applies
    the new button right away - want_rebind is picked up by poll(), in the one thread that touches pynput/SDL."""
    RESCAN_S = 2.0

    def __init__(self, cfg):
        self.down, self.t_down, self.presses = False, 0.0, []
        self.was_playing, self.cut = False, None
        self.ears = None         # set in main(): microphone + speech recognition
        self.on_rebind = None    # set in main(): called after rebind() (the mic may need to wake up)
        self.device = cfg.get("device")
        # your own key-up / key-release sounds ("ptt_sounds" in config.json)
        s = cfg.get("ptt_sounds") or {}
        self.snd = {}
        for edge, kind in (("press", s.get("press")), ("release", s.get("release"))):
            f = snd(FX / f"ptt_{edge}_{kind}.wav") if kind else None
            if f and f.exists():
                data, sr = sf.read(f, dtype="float32")
                self.snd[edge] = (data * float(s.get("volume", 0.5)) * float(cfg.get("volume", 0.8)), sr)
        self.want_rebind = None
        self._start_backend(cfg.get("ptt") or {})

    def _start_backend(self, c):
        """keyboard / mouse / winmm / pygame, in this order; re-runnable at any moment (tray «переназначить кнопку»)."""
        self.dev, self.btn = str(c.get("device", "")).lower(), c.get("button")
        self.ok = False
        self.backend = None
        self.jid, self.js = None, {}
        self._next_scan, self._names, self._last_cfg = 0.0, None, -1e9
        self.listener, self.mm, self.pg = None, None, None
        self.kb_down = False
        if self.btn is None:
            return
        if self.dev in ("keyboard", "mouse") and isinstance(self.btn, str):
            # 1.27: keyboard PTT for players without a wheel; 1.28: any mouse button too
            try:
                from pynput import keyboard, mouse
                src = keyboard if self.dev == "keyboard" else mouse
                def on_press(key):
                    try:
                        if _input_name(key) == self.btn and not self.kb_down:
                            self.kb_down = True
                            self._press()
                    except Exception:
                        pass
                def on_release(key):
                    try:
                        if _input_name(key) == self.btn and self.kb_down:
                            self.kb_down = False
                            self._release()
                    except Exception:
                        pass
                self.listener = src.Listener(on_press=on_press, on_release=on_release)
                self.listener.start()
                self.backend, self.ok = self.dev, True
                log(f"тангента: {self.dev} «{self.btn}»")
                return
            except Exception as e:
                log(f"тангента через pynput не вышла ({e!r})")
        if not isinstance(self.btn, int) or self.btn < 0:
            log(f"тангента: непонятная кнопка {self.btn!r} для устройства «{self.dev}»")
            return
        if self.btn < 32 and c.get("backend", "winmm") == "winmm":
            try:
                self.mm = ctypes.WinDLL("winmm")
                self.ji = _JOYINFOEX()
                self.ji.dwSize, self.ji.dwFlags = ctypes.sizeof(self.ji), 0x80        # JOY_RETURNBUTTONS
                self.backend, self.ok = "winmm", True
                self._scan_winmm()
                return
            except Exception as e:
                log(f"тангента через winmm не вышла ({e!r}) — пробую pygame")
        try:
            import pygame
            self.pg = pygame
            pygame.init()
            pygame.joystick.init()
            self._rescan()
            self.backend, self.ok = "pygame", True
        except Exception as e:
            log(f"тангента не работает: {e!r}")

    def rebind(self, c):
        """1.28: switch the button at once (tray «переназначить кнопку рации»): same object, new backend, no restart."""
        if self.down:
            self._release()
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass
        if self.pg:
            try:
                self.pg.quit()        # closes its joysticks; _start_backend inits pygame again if still needed
            except Exception:
                pass
        self.down = False
        self._start_backend(c)
        log(f"тангента: новая кнопка применена ({c.get('device')}, {c.get('button')})")
        if self.on_rebind:
            try:
                self.on_rebind()
            except Exception as e:
                log(f"тангента: после переназначения {e!r}")

    def describe(self):
        """The current button, human-readable — tray menu line and the rebind dialog («Кнопка рации: …»)."""
        if not self.ok or self.btn is None:
            return "не найдена"
        if self.dev == "keyboard":
            return f"клавиша {self.btn}"
        if self.dev == "mouse":
            return f"мышь: {self.btn}"
        return f"{self.dev}, кнопка {self.btn}"

    CFG_CHANGED_S = 15.0     # joyConfigChanged not more often than this

    def _scan_winmm(self):
        # winmm caches the device list: joyConfigChanged re-reads it after a replug. 2026-11-05: the radio died
        # with heap corruption 0xc0000374 INSIDE this call (crash.log 10:46, also 2026-11-04 16:45) right after all
        # USB devices dropped for a second — it was called every 2 s while re-enumerating. Now: rarely, not at once.
        now = time.monotonic()
        try:
            with _WINMM_LOCK:
                if now - self._last_cfg >= self.CFG_CHANGED_S:
                    self._last_cfg = now
                    self.mm.joyConfigChanged(0)
                devs = _winmm_buttons(self.mm)
        except Exception:
            devs = {}
        found = None
        for i, (name, _) in devs.items():
            if self.jid is None and self.dev and self.dev in name.lower():
                try:
                    with _WINMM_LOCK:
                        ok = self.mm.joyGetPosEx(i, ctypes.byref(self.ji)) == 0
                except Exception:
                    ok = False
                if ok:
                    self.jid, found = i, name
        names = [n for n, _ in devs.values()]
        if names != self._names:
            self._names = names
            log(f"тангента: {'найдена на ' + found if found else 'устройство не найдено'} "
                f"(кнопка {self.btn}, winmm); устройства: {', '.join(names)}")
        self._next_scan = time.monotonic() + self.RESCAN_S

    def _rescan(self):
        self.js = {}
        for i in range(self.pg.joystick.get_count()):
            j = self.pg.joystick.Joystick(i)
            self.js[j.get_instance_id()] = j
        names = [j.get_name() for j in self.js.values()]
        if names == self._names:
            return
        self._names = names
        found = [n for n in names if self.dev in n.lower()]
        log(f"тангента: {'найдена на ' + found[0] if found else 'устройство не найдено'} "
            f"(кнопка {self.btn}, pygame); устройства: {', '.join(names)}")

    def _sound(self, edge):
        if edge in self.snd:
            try:
                sd.play(*self.snd[edge], device=self.device)   # non-blocking, nothing else plays now
            except Exception as e:
                log(f"звук тангенты: {e!r}")

    def _press(self):
        self.down, self.t_down = True, time.monotonic()
        self.was_playing, self.cut = PLAYER.playing, PLAYER.speaker
        if PLAYER.playing:
            sd.stop()        # you can't hear the channel while you transmit
        self._sound("press")
        if self.ears:
            self.ears.start()

    def _release(self):
        self.down = False
        job = self.ears.stop() if self.ears else None
        self.presses.append((time.monotonic() - self.t_down, self.was_playing, self.cut, job))
        self._sound("release")

    def poll(self):
        if self.want_rebind is not None:      # 1.28: tray «переназначить кнопку» — applied here so pynput/SDL
            c, self.want_rebind = self.want_rebind, None      # calls stay in the one thread that polls
            self.rebind(c)
        if not self.ok:
            return
        try:
            if self.backend in ("keyboard", "mouse"):
                return                        # the pynput listener presses/releases on its own thread
            if self.backend == "winmm":
                if self.jid is None:
                    if time.monotonic() >= self._next_scan:
                        self._scan_winmm()
                    if self.jid is None:
                        return
                try:
                    with _WINMM_LOCK:
                        err = self.mm.joyGetPosEx(self.jid, ctypes.byref(self.ji))
                except Exception:
                    err = -1
                if err != 0:                                    # unplugged / re-plugged
                    self.jid = None
                    self._next_scan = time.monotonic() + 3.0     # let USB settle before asking winmm again
                    if self.down:
                        self._release()
                    return
                pressed = bool(self.ji.dwButtons >> self.btn & 1)
                if pressed and not self.down:
                    self._press()
                elif not pressed and self.down:
                    self._release()
                return
            for e in self.pg.event.get():
                if e.type in (self.pg.JOYDEVICEADDED, self.pg.JOYDEVICEREMOVED):
                    self._rescan()
                elif e.type in (self.pg.JOYBUTTONDOWN, self.pg.JOYBUTTONUP) and e.button == self.btn:
                    j = self.js.get(e.instance_id)
                    if not j or self.dev not in j.get_name().lower():
                        continue
                    if e.type == self.pg.JOYBUTTONDOWN and not self.down:
                        self._press()
                    elif e.type == self.pg.JOYBUTTONUP and self.down:
                        self._release()
        except Exception as e:
            log(f"тангента: {e!r}")


# ---------------------------------------------------------------- deck
# deck items: "<actor>/NN" (single phrase) or "scene/<id>" (several transmissions in a row)
def all_phrases():
    singles = [f"{p.parent.name}/{p.stem}" for p in snd_glob(AUDIO, "*/*.wav")]
    scenes = [f"scene/{d.name}" for d in SCENES.glob("*") if (d / "scene.json").exists()
              and all(variant_of(snd(f)) is not None for f in snd_glob(d, "[0-9][0-9].wav"))]
    return sorted(singles + scenes)


def load_roles():
    """{actor: {"greet": {"actor/NN"}, "signoff": {...}}} from the phrases file."""
    roles = {}
    try:
        data = json.loads(PHRASES_JSON.read_text(encoding="utf-8"))
        for key, a in data["actors"].items():
            roles[key] = {r: {f"{key}/{n:02d}" for n in a.get(r, [])} for r in ("greet", "signoff")}
    except (OSError, ValueError, KeyError):
        pass
    return roles


_JSON_CACHE = {}


def _json(path):
    """Parsed JSON file, re-read only when the file changed (the deck asks for the same files many times)."""
    try:
        mt = path.stat().st_mtime_ns
    except OSError:
        return None
    hit = _JSON_CACHE.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    _JSON_CACHE[path] = (mt, data)
    return data


def actors_of(item):
    """Speakers of a deck item in order."""
    if item.startswith("scene/"):
        return list((_json(SCENES / item[6:] / "scene.json") or {}).get("actors", []))
    return [item.split("/")[0]]


import collections  # noqa: E402

RECENT = collections.deque(maxlen=20)   # reaction files heard lately: one driver must not repeat himself
FOREIGN = {p.name for p in (ROOT / "audio" / "reactions" / "foreign").glob("*") if p.is_dir()}
FOREIGN_LAST = [None, -1e9, 0]   # (language, monotonic end of his last line, replies so far) of the passing foreigner
FOREIGN_HEARS_S = 20          # small talk right after him is for him
FOREIGN_MAX_REPLIES = 2       # 07.11 Kirill: 8 «не понял, брат» in a row — after two he drives on
FOREIGN_SMALLTALK = (None, "greet", "how_are_you", "praise", "thanks", "bye", "joke", "mock", "rude", "bot")
FOREIGN_WORD_S = 600          # «амиго», «хеллоу»… reach him for 10 min (he is still somewhere on the channel)
_FOREIGN_WORDS = re.compile(
    r"\b(амиго|амигос|хеллоу?|хелло|хэллоу?|хай|бонжур|бонжюр|мерси|гутен|гутн|данке|данкешон|чао|грацие?|грация|"
    r"сеньор|синьор|мучачо|ола|хола|буэнос|камрад|ахой|добры день|дзень добры|сава|бонжорно|буонджорно|ауфидерзейн|"
    r"hello|hi|amigo|bonjour|merci|guten|danke|ciao|grazie|hola|ahoj)\b", re.I)


def foreign_word(text):
    return bool(_FOREIGN_WORDS.search((text or "").lower().replace("ё", "е")))
BUH_KIND = {"speeding": "speeding", "speeding_camera": "speeding", "red_signal": "red_signal", "crash": "crash",
            "no_lights": "no_lights", "avoid_sleeping": "avoid_sleeping", "wrong_way": "wrong_way"}
COUNTRY_LANG = {"germany": "de", "austria": "de", "switzerland": "de", "poland": "pl", "france": "fr",
                "belgium": "fr", "luxembourg": "fr", "spain": "es", "italy": "it", "netherlands": "nl",
                "czech": "cs", "slovakia": "cs"}
COUNTRY_RU = {"germany": "Германия", "austria": "Австрия", "switzerland": "Швейцария", "poland": "Польша",
              "france": "Франция", "belgium": "Бельгия", "luxembourg": "Люксембург", "spain": "Испания",
              "italy": "Италия", "netherlands": "Нидерланды", "czech": "Чехия", "slovakia": "Словакия"}


try:                                       # secrets (2026-11-06, tainik.py): the kinds are known only from the tainik
    import tainik as _tainik
    SECRET_KINDS, _tainik_dir = set(), _tainik.dirname
except Exception:
    _tainik, SECRET_KINDS, _tainik_dir = None, set(), (lambda k: k)
SECRETS = {"intents": [], "texts": {}}


def secret_texts():
    """Overlay subtitles for secret lines in builds: reactions/x/<faceless>/NN -> text."""
    out = {}
    for k, ls in (SECRETS.get("texts") or {}).items():
        for i, t in enumerate(ls, 1):
            out[f"reactions/x/{_tainik_dir(k)}/{i:02d}"] = t
    return out


def fresh_first(cands):
    """From (actor, wav) candidates keep the ones not heard lately (if any are left)."""
    new = [c for c in cands if str(c[1]) not in RECENT]
    return new or cands


def heard(wav):
    RECENT.append(str(wav))


_POOL_FILES = {}


def reaction_pool(group, kind):
    """[(actor, wav path)] for audio/reactions/<group>/<kind>. Secrets (tainik.py) live in a faceless folder in builds."""
    d = REACT / group / kind
    if group == "intent" and kind in SECRET_KINDS and not d.exists():
        d = REACT / "x" / _tainik_dir(kind)
    idx = _json(d / "index.json")
    if not idx or "actors" not in idx:
        return []
    key = (d, _JSON_CACHE[d / "index.json"][0])      # rebuilt when index.json changes
    if key not in _POOL_FILES:
        _POOL_FILES[key] = [(a, variant_of(snd(d / f"{i:02d}.wav"))) for i, a in enumerate(idx["actors"], 1)
                            if snd(d / f"{i:02d}.wav").exists() and variant_of(snd(d / f"{i:02d}.wav")) is not None]
    return list(_POOL_FILES[key])


class Deck:
    """No-repeat shuffle deck + on-air logic for one driving session:
    - an actor speaks only after his greeting (if the greeting is still in the deck);
    - no second greeting while he is on air; sign-off only after he spoke;
    - after a sign-off he is off air for OFFLINE_S (then may greet again);
    - the same voice never opens a transmission right after it closed the previous one."""

    def __init__(self):
        self.st = {"left": [], "last": None}
        if STATE_FILE.exists():
            try:
                self.st.update(json.loads(STATE_FILE.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
        self.roles = load_roles()
        try:
            acts = json.loads(PHRASES_JSON.read_text(encoding="utf-8"))["actors"]
            self.weights = {k: float(a.get("weight", 1.0)) for k, a in acts.items()}
        except (OSError, ValueError, KeyError):
            self.weights = {}
        self.on_air = set()      # greeted / spoke this session
        self.spoken = {}         # actor -> transmissions this session (for balancing)
        self.allowed = None      # actors within radio range (living highway); None = everybody
        self.allowed_far = set() # beyond range but within 2x: may answer in a scene, barely heard
        self.prefer = set()      # just came into range: let them talk first
        self.off_until = {}      # actor -> monotonic time
        self.signed_off = {}     # actor -> monotonic time of his sign-off
        self.grace = None        # an actor who may still answer although he signed off (a «пока» to his «пока»)

    def _save(self):
        try:
            STATE_FILE.write_text(json.dumps(self.st, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:
            log(f"не сохранил колоду: {e}")

    def offline(self, actor):
        if actor == self.grace:
            return False
        return self.off_until.get(actor, 0) > time.monotonic()

    def _ok(self, item, left, last_voice, strict):
        acts = actors_of(item)
        if not acts:
            return False
        if self.allowed is not None:
            if item.startswith("scene/"):
                # a conversation starts with somebody near you; the other side may be far (barely heard)
                if acts[0] not in self.allowed or not set(acts) <= (self.allowed | self.allowed_far):
                    return False
            elif not set(acts) <= self.allowed:
                return False                               # out of radio range
        if any(self.offline(a) for a in acts):
            return False                                   # someone in it signed off recently
        if strict and acts[0] == last_voice:
            return False
        for a in set(acts):
            r = self.roles.get(a, {"greet": set(), "signoff": set()})
            if item in r["greet"]:
                if a in self.on_air:
                    return False                           # already on air: no second hello
            elif item in r["signoff"]:
                if a not in self.on_air:
                    return False                           # bye from someone we never heard
            elif (a not in self.on_air and strict and r["greet"] & left
                  and not item.startswith("scene/")):
                return False                               # should say hello first (not needed in a talk)
        return True

    def draw(self):
        have = set(all_phrases())
        if VITYOK_WEDDING_DONE[0]:
            # 1.33 свадебная арка Витьки закрыта: паничные предсвадебные реплики уходят из эфира
            have = {p for p in have
                    if not (p.startswith("vitek/") and p.split("/")[1].isdigit()
                            and int(p.split("/")[1]) in VITEK_PANIC)}
        left = [p for p in self.st["left"] if p in have]
        # phrases added since the deck was shuffled (new actor, new scene): mix them in now
        seen = set(self.st.get("history", [])) | set(left)
        for p in sorted(have - seen):
            left.insert(random.randint(0, len(left)), p)
        if not left:
            left = list(have)
            random.shuffle(left)
            log(f"колода перемешана: {len(left)} шт.")
        last_voice = (actors_of(self.st["last"]) or [None])[-1] if self.st["last"] else None
        left_set = set(left)                               # _ok() checks greetings against it per item
        # balance the channel: among allowed items take the one whose speaker has talked least this session
        # (divided by his "weight" from the phrases file), ties -> deck order (keeps it random)
        cands = [p for p in left if self._ok(p, left_set, last_voice, True)]
        fresh = [p for p in cands if set(actors_of(p)) & self.prefer]
        if fresh:
            cands = fresh                                  # who just came into range speaks first
        elif self.allowed and len(self.allowed | self.allowed_far) >= 2 and random.random() < 0.6:
            scenes = [p for p in cands if p.startswith("scene/")]
            if scenes:
                cands = scenes                             # two of them nearby: let them talk to each other
        if cands and BONDS:
            # friendship & mood: a stranger doesn't say his lines that call you by name; a line that fits the
            # speaker's mood today comes a little earlier, one against it a little later
            cands = [p for p in cands if p.startswith("scene/") or not (
                BONDS.level(actors_of(p)[0]) == 0 and BONDS.calls_by_name(p))] or cands
            # personal lines ("lv" in the phrases file) — only from that friendship level; scenes exempt
            cands = [p for p in cands if p.startswith("scene/") or BONDS.lv_ok(actors_of(p)[0], p)]
        if cands:
            pos = {p: i for i, p in enumerate(left)}

            def mood_k(p):
                if not BONDS or p.startswith("scene/"):
                    return 0.0
                w = BONDS.weight(actors_of(p)[0], p)
                return -0.4 if w > 1 else 0.4 if w < 1 else 0.0
            pick = min(cands, key=lambda p: ((self.spoken.get(actors_of(p)[0], 0)
                                              + (8 if time.monotonic() < QUIET_UNTIL.get(actors_of(p)[0], 0) else 0))
                                             / self.weights.get(actors_of(p)[0], 1.0)
                                             + mood_k(p), pos[p]))
        else:
            pick = next((p for p in left if self._ok(p, left_set, last_voice, False)), None)
        hist = [h for h in self.st.get("history", []) if h in have]
        if pick is None:
            # everything left in the deck is blocked right now (bye-phrases of absent actors,
            # scenes with someone off air): take an allowed item heard longest ago instead
            order = sorted(have, key=lambda p: hist.index(p) if p in hist else -1)
            if BONDS:
                order = [p for p in order if p.startswith("scene/") or BONDS.lv_ok(actors_of(p)[0], p)]
            pick = (next((p for p in order if self._ok(p, left_set, last_voice, True)), None)
                    or next((p for p in order if self._ok(p, left_set, last_voice, False)), None))
            if pick is None:
                return None
        if pick in left:
            left.remove(pick)
        hist = [h for h in hist if h != pick] + [pick]
        self.st["left"], self.st["last"], self.st["history"] = left, pick, hist
        self._save()
        acts = actors_of(pick)
        self.on_air.update(acts)
        self.prefer -= set(acts)
        for a in acts:
            self.spoken[a] = self.spoken.get(a, 0) + 1
        for a in set(acts):
            if pick in self.roles.get(a, {}).get("signoff", set()):
                self.on_air.discard(a)
                self.off_until[a] = time.monotonic() + OFFLINE_S
                self.signed_off[a] = time.monotonic()
        return pick

    def is_greeting(self, item):
        a = item.split("/")[0]
        return item in self.roles.get(a, {}).get("greet", set())

    def choose(self, pool, prefer=None, exclude=(), avoid=None):
        """Pick (actor, wav) from a reaction pool: not off air, not excluded, not the same file as
        last time (if there is another); prefer the given actor, then actors on air, then anyone."""
        ok = [(a, f) for a, f in pool if not self.offline(a) and a not in exclude
              and (self.allowed is None or a in self.allowed)]
        if len(ok) > 1 and avoid:
            ok = [x for x in ok if x[1] != avoid] or ok
        if not ok:
            return None
        ok = bond_filter(ok)
        for cand in ([x for x in ok if x[0] == prefer], [x for x in ok if x[0] in self.on_air], ok):
            if cand:
                pick = mood_pick(fresh_first(cand))
                heard(pick[1])
                return pick
        return None


# ---------------------------------------------------------------- friendship & mood (bonds.py, 2026-11-06)
BONDS = None
FEMALE = {"petrovna", "lastochka", "lisa", "sova", "vera", "soroka"}
PERSONAL_KINDS = ("family", "salary", "health")     # на lv0–1 эфир уходит в уклончивые (reactions/bond/evade)
BOND_UP = []          # (время озвучить, поставлено, актёр, новый уровень) — переходы дружбы вслух
MARK_Q = []           # (actor, mood) — маркеры настроения вслух (смена настроения, 2026-11-09)
QUIET_UNTIL = {}      # actor -> monotonic: «успокойся» (да) — 10–15 мин тише и реже (1.33)
LAST_OFFENDED = {}    # actor -> monotonic: кто обиделся — извинение маршрутизируется ему (1.33)
DLC_PLAYED = set()    # арка Iceland: раз за сессию (окно до 2026-12-08)
VITYOK_WEDDING_DONE = [False]   # арка Витьки закрыта → паничные singles спрятаны, тянет в calm
VITYOK_QUEST_STATE = ROOT / "quest_state.json"      # прогресс сквозной арки (ступень 0..7)

# паничные предсвадебные singles Витьки — прячутся из колоды после закрытия арки (drop-эффект в коде)
VITEK_PANIC = {1, 2, 6, 7, 9, 12, 13, 14, 15, 16, 18, 24}

_RELATIONS = [None]


def relations():
    """Граф знакомств из phrases/canon_relations_2026-11-08.md (map/actor_relations.json): 'Л' лично, 'Э' заочно."""
    if _RELATIONS[0] is None:
        try:
            _RELATIONS[0] = json.loads((ROOT / "map" / "actor_relations.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _RELATIONS[0] = {}
    return _RELATIONS[0]


def quest_state():
    try:
        return json.loads(VITYOK_QUEST_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def quest_save(st):
    try:
        VITYOK_QUEST_STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def bond_filter(cands):
    """A stranger (friendship level 0) doesn't call you by name: drop his named lines if he has others.
    A line marked "lv" in the phrases file (personal topics) needs that friendship level — strictly."""
    if not BONDS:
        return cands
    keep = [x for x in cands if not (BONDS.level(x[0]) == 0 and BONDS.calls_by_name(_rel(x[1])))]
    if not keep:
        keep = cands               # old behaviour: a stranger with only named lines still talks
    return [x for x in keep if BONDS.lv_ok(x[0], _rel(x[1]))]


def mood_pick(cands):
    """Random pick weighted by each speaker's mood today (lines whose emotion tags fit it come up more)."""
    if not BONDS or len(cands) < 2:
        return random.choice(cands)
    return random.choices(cands, weights=[BONDS.weight(a, _rel(f)) for a, f in cands])[0]


def mood_nudge(actor, d, why):
    """Cheer a driver up (+) or spoil his mood (-); a change shows on the stream overlay and,
    1.33, queues a spoken mood marker (reactions/mood_mark/<mood>) — the player HEARS the mood."""
    if not BONDS:
        return
    ch = BONDS.nudge(actor, d, why)
    if ch:
        MARK_Q.append((actor, ch[1]))
    if not ch or not OVERLAY:
        return
    import bonds as _b
    before, after = ch
    try:
        nm = (_json(PHRASES_JSON) or {})["actors"][actor]["name"].split(" (")[0]
    except (KeyError, TypeError):
        nm = actor
    she = actor in FEMALE
    up = _b.Bonds.ORDER.index(after) > _b.Bonds.ORDER.index(before)
    word = ("повеселела" if she else "повеселел") if up else ("помрачнела" if she else "помрачнел")
    OVERLAY.bond(f"{nm} {word} {_b.MOODS[after]['emoji']}")


def bond_add(actor, n, why):
    """Friendship points; a level change is announced in the log and on the stream overlay."""
    if not BONDS:
        return
    ch = BONDS.add(actor, n, why)
    if not ch:
        return
    old, new = ch
    nm = actor
    try:
        nm = (_json(PHRASES_JSON) or {})["actors"][actor]["name"]
    except (KeyError, TypeError):
        pass
    nm = nm.split(" (")[0]
    she = actor in FEMALE
    if new > old:
        msg = f"{nm}: " + {1: "теперь вы знакомы ♥", 2: "теперь вы приятели ♥♥", 3: "теперь вы друзья ♥♥♥"}[new]
    else:
        msg = (f"{nm} {'обиделась' if she else 'обиделся'}: " +
               {0: "вы снова незнакомы", 1: "теперь вы просто знакомые", 2: "теперь вы просто приятели"}[new])
    log(f"ДРУЖБА: {msg}")
    if OVERLAY:
        OVERLAY.bond(msg)
    if new > old and actor not in ("buh",) and not actor.startswith("driver."):
        # переход вслух: актёр сам прокомментирует смену уровня, один переход за раз, с задержкой
        # 1.33 (Игорь): обиженный не «радуется» переходу — апгрейд во время свежей обиды молчит
        if time.monotonic() - LAST_OFFENDED.get(actor, -1e9) > 600:
            BOND_UP.append((time.monotonic() + random.uniform(8.0, 20.0), time.monotonic(), actor, new))
        else:
            log(f"  дружба: {actor} обижен — переход вслух отложен")


# ---------------------------------------------------------------- audio
# «Помехи» (2026-11-06, Kirill: the noise got in his way): how much static the radio adds on top of the voices -
# hiss and drop-outs at the edge of range, empty PTT clicks, the crackle when somebody comes into range.
# 1.0 = as it was. The light background baked into the recordings stays.
STATIC = {
    "full": {"name": "Сильные", "k": 1.0},
    "mid":  {"name": "Средние", "k": 0.5},
    "low":  {"name": "Слабые", "k": 0.2},
    "off":  {"name": "Без помех", "k": 0.0},
}
STATIC_NOW = {"k": 0.5}


def degrade(x, sr, d):
    """Signal by distance: d = distance / radio range. Near: as recorded. Towards the edge: more hiss,
    weaker voice, short drop-outs ("пропадаешь"). Scaled by the «Помехи» setting."""
    f = STATIC_NOW["k"]
    if d is None or d < 0.55 or f <= 0:
        return x
    k = min(2.0, (d - 0.55) / 0.45)              # 1 = edge of range, up to 2 = the far side of a talk
    y = x * max(0.3, 1.0 - 0.35 * k * f)
    noise = np.random.standard_normal(len(x)).astype(np.float32)
    noise = np.convolve(noise, np.ones(6, np.float32) / 6, mode="same")      # take the fizz off
    y = y + noise * (0.012 + 0.05 * k) * f
    for _ in range(int(k * 3 * f + random.random() * f)):
        n = int(random.uniform(0.08, 0.22) * sr)
        s = random.randint(0, max(0, len(y) - n))
        y[s:s + n] *= 0.15
    return np.clip(y, -1, 1).astype(np.float32)


class Player:
    """Plays files one at a time (never two at once). Stops when the game pauses or you press PTT."""

    def __init__(self):
        self.cfg, self.game, self.ptt = None, None, None
        self.world = None        # living highway: distance of the speaker -> signal quality
        self.spoke = set()       # actors who talked during their current encounter (for the "пропадаю" line)
        self.playing = False
        self.speaker = None      # actor currently on air (for "don't interrupt")
        self.last_speaker, self.last_t = None, 0.0
        self.voices = 0          # transmissions with a voice so far (the silence guard watches it)
        self.said = {}           # actor -> (wav, n): his last line on air, for "повтори"
        self.said_n = 0          # every new line gets its number (repeats are counted per line)
        self.last_said = None    # actor who started a line last

    def idle(self, sec):
        """Wait, keep reading the wheel. False if the game stopped 'driving' meanwhile."""
        t0 = time.monotonic()
        while time.monotonic() - t0 < sec:
            if self.ptt:
                self.ptt.poll()
            time.sleep(0.02)
            if self.game and self.game.state(self.cfg["require_engine_on"]) != "driving":
                return False
        return True

    def file(self, path, actor=None, replay=False):
        """'ok' | 'paused' | 'ptt' (you keyed up over it) | 'error'
        replay=True: he repeats an old line ("повтори") - it is not remembered as a new one."""
        if self.ptt and self.ptt.down:
            return "ptt"
        vp = variant_of(path)
        if vp is None:                       # calls the player by a name we don't have in this variant
            return "error"
        path = vp
        try:
            data, sr = sf.read(path, dtype="float32")
            if self.world and actor:
                data = degrade(data, sr, self.world.distance(actor))
            if not actor and Path(path).name.startswith(("kerchunk_", "enter_")):
                if STATIC_NOW["k"] <= 0:                 # «Помехи: без помех» - no clicks / crackles at all
                    return "ok"
                data = data * STATIC_NOW["k"] ** 0.5     # half the static = a bit quieter clicks, not silent
            vol = 0.0 if TRAY_STATE.get("muted") else float(self.cfg["volume"])     # «Тишина в эфире» (tray)
            sd.play(data * vol, sr, device=self.cfg["device"])
            if OVERLAY:                       # stream overlay: subtitles of what is said (overlay.py)
                OVERLAY.said(_rel(path), actor, len(data) / sr)
        except Exception as e:  # missing file, busy/unplugged device: skip, keep the radio alive
            log(f"не смог проиграть {Path(path).name}: {e}")
            return "error"
        self.playing, self.speaker = True, actor
        if actor and not replay:
            self.said_n += 1
            self.said[actor] = (path, self.said_n)    # even if you cut him off: "повтори" gets it whole
            self.last_said = actor
        try:
            t0, dur = time.monotonic(), len(data) / sr
            while time.monotonic() - t0 < dur + 0.1:
                if self.ptt:
                    self.ptt.poll()
                    if self.ptt.down:            # poll() already stopped the channel and beeped
                        return "ptt"
                time.sleep(0.02)
                if self.game and self.game.state(self.cfg["require_engine_on"]) != "driving":
                    sd.stop()
                    return "paused"
            if actor:
                self.spoke.add(actor)
            if actor or Path(path).name in ("_foreign.wav", "_murmur.wav") or "buh" in str(path):
                self.voices += 1
            return "ok"
        finally:
            self.playing = False
            if actor:
                self.last_speaker, self.last_t = actor, time.monotonic()
            self.speaker = None

    def item(self, name):
        if name.startswith("scene/"):
            d = SCENES / name.split("/", 1)[1]
            meta = json.loads((d / "scene.json").read_text(encoding="utf-8"))
            for i, (actor, pause) in enumerate(zip(meta["actors"], meta["pauses"]), 1):
                if i > 1 and not self.idle(pause):
                    return "paused"
                if self.ptt and self.ptt.down:
                    return "ptt"
                r = self.file(snd(d / f"{i:02d}.wav"), actor)
                if r in ("paused", "ptt"):
                    return r
            return "ok"
        return self.file(snd(AUDIO / f"{name}.wav"), name.split("/")[0])


PLAYER = Player()


# ---------------------------------------------------------------- the player's voice (local, no network)
class Ears:
    """Microphone + local speech recognition (faster-whisper on CPU).
    The mic stream stays open; while PTT is held we keep the audio (+0.3 s before the press)."""
    HALLUCINATIONS = ("субтитр", "продолжение следует", "спасибо за просмотр", "редактор субтитров", "подпишись")
    # a hint of the channel's words: without it whisper hears «кто в эфире» as «кто вы, Хире/Сири»
    PROMPT = ("Рация, канал дальнобойщиков. Кто в эфире? Повтори. Приём. Железяка. Михалыч, Стас, Янек, Ласточка, Борода, "
              "Сорока, Студент, Профессор, Петровна, Тень, Витёк, Сова, Палыч, Кардан, Лиса, Самарканд, Ковбой, Кинолог.")

    def __init__(self, cfg):
        import collections
        import queue
        import threading
        self.ok, self.model, self.recording = False, None, False
        self.buf, self.pre = [], collections.deque(maxlen=8)     # ~0.4 s of 50 ms blocks before the press
        self.jobs, self.results = queue.Queue(), {}
        self.stream, self.dev_name, self.sr = None, "", 48000
        self.last_info = "ещё не нажимали"      # shown in the tray menu: what the radio heard last time
        self.on_silent = None                    # callback: pressed, but the microphone gave silence
        c = cfg.get("mic") or {}
        if not c.get("enabled", True):
            self.dev_name = "выключен в настройках"
            return
        if not self.open(c.get("device", "")):
            return
        self.ok = True
        self.want_model = threading.Event()
        threading.Thread(target=self._worker, args=(c.get("model", "small"),), daemon=True).start()

    def open(self, want):
        """(Re)open the microphone: by name from config / tray menu, else mic.pick (skips virtual ones)."""
        import mic
        dev, name, why = mic.pick(sd, want)
        if dev is None:
            log(f"микрофон не найден ({why}) — тангента работает без понимания речи")
            self.dev_name = "не найден"
            return False
        old = self.stream
        self.stream = None
        if old is not None:
            try:
                old.stop()
                old.close()
            except Exception:
                pass
        sr = int(sd.query_devices(dev)["default_samplerate"])
        try:
            # 50 ms blocks: 20 callbacks a second instead of 100 (0.8 % of a core instead of 2.2 %)
            st = sd.InputStream(device=dev, channels=1, samplerate=sr, blocksize=sr // 20,
                                dtype="float32", callback=self._cb)
            st.start()
        except Exception as e:
            log(f"микрофон «{name}» не открылся: {e!r}")
            self.dev_name = f"{name} — не открылся"
            return False
        self.sr, self.stream, self.dev_name = sr, st, name
        self.pre.clear()
        log(f"микрофон: {name} ({sr} Гц) — {why}")
        blocked = mic.privacy_blocked()
        if blocked:
            log(f"ВНИМАНИЕ: {blocked}")
        return True

    def _cb(self, indata, frames, t, status):
        block = indata[:, 0].copy()
        if self.recording:
            self.buf.append(block)
        else:
            self.pre.append(block)

    def start(self):
        if self.ok:
            self.buf = list(self.pre)
            self.recording = True
            self.want_model.set()        # the model loads (~1.7 s) while you speak

    def stop(self):
        """-> job id (or None). Recognition runs in the background thread."""
        if not self.ok or not self.recording:
            return None
        self.recording = False
        audio = np.concatenate(self.buf) if self.buf else np.zeros(1, np.float32)
        job = time.monotonic()
        self.jobs.put((job, audio))
        return job

    IDLE_UNLOAD_S = 240      # the model holds ~2.2 GB of commit: keep it only while you talk

    def _worker(self, model_name):
        import queue
        local = ROOT / "models" / f"whisper-{model_name}"      # shipped with the installer: no download
        if (local / "model.bin").exists():
            model_name = str(local)
        try:
            from faster_whisper import WhisperModel
            from scipy.signal import resample_poly
            WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=4)   # check it loads at all
            log(f"распознавание речи готово (whisper {model_name}, грузится на нажатие тангенты)")
        except Exception as e:
            log(f"распознавание речи не загрузилось: {e!r}")
            self.ok = False
            return
        last_use = time.monotonic()
        while True:
            if self.want_model.is_set():
                if self.model is None:
                    self.model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=4)
                last_use = time.monotonic()
            self.want_model.clear()
            try:
                job, audio = self.jobs.get(timeout=0.1)
            except queue.Empty:
                if self.model is not None and not self.recording and time.monotonic() - last_use > self.IDLE_UNLOAD_S:
                    self.model = None            # frees the memory; next press loads it again
                continue
            if self.model is None:
                self.model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=4)
            last_use = time.monotonic()
            text = ""
            try:
                sf.write(ROOT / "last_ptt.wav", audio, self.sr)
                peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
                rms = float(np.sqrt(np.mean(np.square(audio)))) if len(audio) else 0.0
                db = 20 * np.log10(peak + 1e-9)
                log(f"  микрофон: пик {db:.0f} дБ, средний {20 * np.log10(rms + 1e-9):.0f} дБ")
                if peak <= 0.002:
                    # a LIVE mic breathes even in a quiet room (peak -60 dB, rms -85: range ~25 dB); a dead or
                    # wrong device is a flat line (range a couple of dB). Only the flat one «молчит» (Данила 08.11)
                    if db - 20 * np.log10(rms + 1e-9) < 10:
                        self.last_info = f"тишина ({db:.0f} дБ) — микрофон молчит"
                        log(f"  микрофон «{self.dev_name}» молчит — выберите другой в меню значка (Микрофон)")
                        if self.on_silent and len(audio) >= 0.8 * self.sr:   # a short tap is silent anyway (Kirill 06.11)
                            self.on_silent(self.dev_name)
                    else:
                        self.last_info = f"тишина ({db:.0f} дБ) — микрофон живой, говорите громче/ближе"
                if peak > 0.002:                            # the fifine is quiet (~-45 dB peaks): normalise
                    y = resample_poly(audio / peak * 0.9, 16000, self.sr).astype(np.float32)
                    segs, _ = self.model.transcribe(y, language="ru", beam_size=5, vad_filter=True,
                                                    initial_prompt=self.PROMPT)
                    text = " ".join(s.text for s in segs).strip()
                    if any(h in text.lower() for h in self.HALLUCINATIONS):
                        text = ""
                    self.last_info = (f"«{text[:40]}»" if text else "звук есть, слов не разобрал") + f" ({db:.0f} дБ)"
            except Exception as e:
                log(f"распознавание: {e!r}")
            self.results[job] = text


class Operator:
    """Reacts to the player's push-to-talk: recognises what was said (Ears + intents.py) and lets the right
    person answer with a pre-voiced line. Without a microphone it falls back to press length and timing."""
    CLICK_S = 0.6            # shorter press = just a click of the key
    REGREET_S = 30 * 60      # after this long without talking, people greet you again
    STT_WAIT_S = 9.0         # give up waiting for recognition after this (6 s ran out twice 2026-11-05: game + OBS)

    def __init__(self, deck, ears=None):
        self.deck, self.ears = deck, ears
        self.on_air = False
        self.last_talk = -1e9
        self.repeat_until = 0.0      # someone asked "повтори" -> next press gets an answer
        self.pending = None          # (time, group, kind, prefer, addressee)
        self.waiting = None          # (job, release time, interrupted, prefer)
        self.last_file = None
        self.rollcalled = {}         # actor -> time until which he ignores another "кто в эфире?"
        self.repeats = {}            # line number (Player.said) -> times repeated; 2 max, then silence
        self.asked = {}              # (actor, intent) -> time: the same question twice -> «я ж уже говорил»
        self.last_topic = {}         # 1.33: actor -> intent последней темы (смена темы сбрасывает «уже говорил»)
    REPEAT_MAX = 2

    def press(self, dur, interrupted, cut_speaker, job=None):
        now = time.monotonic()
        prefer = cut_speaker or (PLAYER.last_speaker if now - PLAYER.last_t < 120 else None)
        if dur < self.CLICK_S:
            kind = "click" if random.random() < 0.3 else None
            log(f"тангента {dur:.1f} с -> {kind or 'тишина'}")
            self.pending = (now + random.uniform(1.2, 3.2), "player", kind, prefer, None) if kind else None
            return
        self.stale = now - self.last_talk > self.REGREET_S   # long silence -> they greet you again
        self.last_talk = now
        if job is not None:                              # wait for the words
            self.waiting = (job, now, interrupted, prefer)
            self.pending = None
            return
        self._decide("", interrupted, prefer, now, heard=False)

    def poll_ears(self):
        if not self.waiting:
            return
        job, t_rel, interrupted, prefer = self.waiting
        if job in self.ears.results:
            self.waiting = None
            self._decide(self.ears.results.pop(job), interrupted, prefer, t_rel, heard=True)
        elif time.monotonic() - t_rel > self.STT_WAIT_S:
            self.waiting = None
            log("распознавание не успело — отвечаю как без микрофона")
            self._decide("", interrupted, prefer, t_rel, heard=False)

    def _decide(self, text, interrupted, prefer, t_rel, heard):
        import intents
        now = time.monotonic()
        self.heard_text = text
        self.knows_target = intents.knows_target(text) if intent == "knows" else None
        if intent == "knows" and self.knows_target == who:
            who = None            # «ты знаешь Бороду?» — вопрос ПРО него, отвечают другие
        intent, who = intents.understand(text) if text else (None, None)
        # 2026-11-07 (user): a passing foreigner. Your words right after him (and no Russian driver spoke since),
        # or «амиго / хеллоу / бонжур…» within 10 min -> HE answers in his language, laughing («не понял, брат,
        # но хорошей дороги»). Foreign words with no foreigner around -> nobody of ours answers them.
        if heard and text and not who and intent not in ("who", "repeat"):
            fl, ft, fn = FOREIGN_LAST
            fw = foreign_word(text)
            # only small talk goes to him; a real question («где заправиться?», «кто в эфире?») is for our drivers
            right_after = t_rel - ft < FOREIGN_HEARS_S and PLAYER.last_t < ft and intent in FOREIGN_SMALLTALK
            if fl and fn < FOREIGN_MAX_REPLIES and (right_after or (fw and t_rel - ft < FOREIGN_WORD_S)):
                if OVERLAY:
                    OVERLAY.you(text, time.time() - (time.monotonic() - t_rel))
                log(f"тангента: «{text}» -> проезжему иностранцу ({fl})")
                self.pending = (max(now, t_rel + random.uniform(1.0, 2.2)), "foreign_reply", fl, None, None)
                return
            if fw:
                if OVERLAY:
                    OVERLAY.you(text, time.time() - (time.monotonic() - t_rel))
                log(f"тангента: «{text}» -> иностранное слово, иностранца рядом нет — наши молчат")
                self.pending = None
                return
        self.support = intent == "support"
        if self.support and not reaction_pool("intent", "support"):
            intent = "praise"            # no own lines for support yet: they answer as to praise («спасибо, сынок»)
        group = "player"
        about = None
        if who and self.deck.allowed is not None and who not in (self.deck.allowed | self.deck.allowed_far):
            # a name of somebody NOT in range: a question ABOUT him ("Сороку никто не видел?"), not to him -
            # those in range answer; with no recorded line on that, "не знаю / не видел"
            about, who = who, None
        reply = False
        if (not who and not about and heard and PLAYER.last_speaker and t_rel - PLAYER.last_t < 25
                and intent not in ("who", "repeat") and not (intent or "").startswith("graf_")):
            # 2026-11-06 (user): a driver has just finished, you answer right away without a name -> you are
            # talking to HIM (before, 40% of the time somebody else answered). Only if he is still in range.
            a = PLAYER.last_speaker
            if not self.deck.offline(a) and (self.deck.allowed is None or a in self.deck.allowed):
                who, reply = a, True
        question = intents.is_question(text) if text else False
        if intent == "repeat":
            group, kind = "special", "repeat"             # he says his last line again (or keeps quiet)
        elif interrupted and not intent and random.random() < 0.7:     # a clear question is answered anyway
            kind = "interrupt"
        elif heard and not text:
            kind = "not_heard" if random.random() < 0.7 else None      # pressed, but said nothing clear
        elif intent == "who":
            group, kind = "special", "who"                # roll call: everybody in range answers once
        elif intent in ("dist", "eta", "meet") or intent in SECRET_KINDS:
            group, kind = "intent", intent                # «живые ответы»: picked by distance / route / friendship
        elif intent == "knows":
            group, kind = "intent", "knows"               # «ты знаешь <X>?» — по графу canon_relations (1.33)
        elif intent == "calm_down":
            group, kind = "intent", "calm_down"           # «успокойся» — да/нет по настроению, с последствием
        elif intent == "sorry":
            group, kind = "intent", "sorry"               # извинение — обидевшемуся, не случайному адресату
        elif intent and intent.startswith("graf_") and reaction_pool("graf", intent[5:]):
            group, kind = "graf", intent[5:]              # the dog: only Vera answers (who = vera)
        elif intent and intent != "greet" and reaction_pool("intent", intent):
            group, kind = "intent", intent                # a clear question gets a real answer, even first
        elif intent == "greet" or not self.on_air or getattr(self, "stale", False):
            kind = "greet"
        elif now < self.repeat_until:
            kind = "ack"
        elif heard and not intent:
            # words heard but nothing we know. A question (or about someone not here) -> "не знаю / не видел"
            # or "не понял"; a statement / warning from you -> "принял"
            r = random.random()
            if about:
                kind = "dunno"
            elif question:
                kind = "dunno" if r < 0.65 else "not_heard"
            else:
                kind = "ack" if r < 0.8 else "not_heard"
        elif who:
            kind = "ack"
        else:
            r = random.random()
            kind = "ack" if r < 0.7 else "not_heard" if r < 0.9 else None
        if group == "intent" and who and kind not in ("thanks", "bye", "radio_check", "help", "repeat", "praise", "rude",
                                                       "mock", "bot", "support"):
            # step 2 of «вариативность» (2026-11-05): asked him the same within 10 min -> he notices
            # 2026-11-08: «как дела» и «как настроение» — один интент how_are_you, но разные вопросы:
            # ключ повтора считаем по формулировке, иначе «как настроение» после «как дела» = ложный повтор
            ask_kind = "how_are_you:mood" if kind == "how_are_you" and "настро" in text else kind
            # 1.33 (Игорь): новая тема у того же адресата сбрасывает «уже рассказывал» —
            # повторный вопрос считается повтором только ВНУТРИ одной темы
            if self.last_topic.get(who) not in (None, ask_kind):
                for k_ in [k for k in self.asked if k[0] == who]:
                    del self.asked[k_]
            self.last_topic[who] = ask_kind
            last = self.asked.get((who, ask_kind))
            self.asked[(who, ask_kind)] = now
            if last and now - last < 600 and random.random() < 0.7 and any(x[0] == who for x in reaction_pool("player", "already")):
                group, kind = "player", "already"
        if who:
            prefer = who
        if OVERLAY and heard:
            OVERLAY.you(text, time.time() - (time.monotonic() - t_rel))
        log(f"тангента: «{text}» -> {intent or '?'}{' для ' + who if who else ''}{' (ответ ему)' if reply else ''}"
            f"{' про ' + about if about else ''}"
            f"{' (вопрос)' if question else ''} => {group}/{kind or 'тишина'}"
            if heard else f"тангента{' (перебил)' if interrupted else ''} -> {kind or 'тишина'}")
        delay = random.uniform(0.8, 2.2) if heard else random.uniform(1.2, 3.2)
        self.pending = (max(now, t_rel + delay), group, kind, prefer, who) if kind else None
        if intent == "bye":
            self.on_air = False                          # you left the channel: next time they greet you again

    def due(self):
        return self.pending and time.monotonic() >= self.pending[0]

    def _lane_answer(self, who, prefer):
        """«Куда едешь?» -> his own city on the way he is going (world.goal). True if somebody answered.
        Asked by name: only he (near, or just out of range through the noise); else somebody in range."""
        w = getattr(self, "world", None)
        if not w or self.deck.allowed is None:
            return False
        here = [a for a in self.deck.allowed if not self.deck.offline(a)]
        far = [a for a in (self.deck.allowed_far or ()) if not self.deck.offline(a)]
        if who:
            order = [who] if who in here or who in far else []
        else:
            order = ([prefer] if prefer in here else []) + random.sample(here, len(here))
        for a in order:
            g = w.goal(a)
            pool = [x for x in reaction_pool("lane", g) if x[0] == a] if g else []
            if pool:
                actor, wav = pool[0]
                heard(wav)
                log(f"ответ: куда едет — {actor} на {g}")
                if PLAYER.file(wav, actor) == "ok":
                    bond_add(actor, 2 if who == actor else 1, "куда едет")
                    self.deck.on_air.add(actor)
                    self.on_air = True
                    self._maybe_cross(actor, "intent")
                return True
            # 1.33 Исландия: нет своего города-направления — исландские маршруты («хрен выговоришь»)
            isl = line_of("intent", "route", a) if random.random() < 0.6 else None
            if isl:
                log(f"ответ: куда едет — {a} (исландский маршрут)")
                if PLAYER.file(isl[1], a) == "ok":
                    bond_add(a, 2 if who == a else 1, "куда едет")
                    self.deck.on_air.add(a)
                    self.on_air = True
                return True
        return False

    def _honest(self, kind, who):
        """Police / weather questions: an answer the speaker can actually know. -> (actor, wav) or None."""
        w = getattr(self, "world", None)
        if not w or self.deck.allowed is None:
            return None
        here = [a for a in self.deck.allowed if not self.deck.offline(a)]
        if kind == "police":
            # only somebody who comes from where you're going can tell; the one you called first
            knowers = [a for a in here if w.knowledge(a) is not None]
            order = ([who] if who in knowers else []) + random.sample(knowers, len(knowers))
            for a in order:
                k = w.knowledge(a)
                pick = line_of("world", "police_yes" if k in ("camera", "police") else "police_no", a)
                if pick:
                    log(f"  {a} знает дорогу впереди: {k}")
                    return pick
            return None
        if kind == "road":
            # like police: only somebody coming from your way ahead knows the road there
            knowers = [a for a in here if w.knowledge(a) is not None]
            order = ([who] if who in knowers else []) + random.sample(knowers, len(knowers))
            for a in order:
                k = w.knowledge(a)
                pick = line_of("world", "police_yes" if k in ("camera", "police") else "clear", a)
                if pick:
                    log(f"  {a} знает дорогу впереди: {k}")
                    return pick
            return None
        if kind == "weather":
            wk = weather_kind(getattr(self, "game", None), w)
            pool = [x for x in reaction_pool("weather", wk) if x[0] in here]
            mine = [x for x in pool if x[0] == who]
            if not pool and who:
                # nobody near has a word on it: the one you called by name answers from further out,
                # barely heard (without a name nobody far answers - 2026-11-06)
                far = [a for a in self.deck.allowed_far if a == who and not self.deck.offline(a)]
                pool = [x for x in reaction_pool("weather", wk) if x[0] in far]
                if pool:
                    log("  про погоду отвечает дальний")
            if not pool:
                return None
            pick = random.choice(fresh_first(mine or pool))
            heard(pick[1])
            return pick
        return None

    def rollcall(self):
        """"Кто в эфире?" - everybody in range answers with his handle, one after another; whoever answered
        stays quiet on the same question for 2-3 minutes."""
        now = time.monotonic()
        here = list(self.deck.allowed) if self.deck.allowed is not None else list(self.deck.on_air)
        random.shuffle(here)
        done, cut = 0, None
        for a in here:
            if self.rollcalled.get(a, 0) > now or self.deck.offline(a):
                continue
            pick = line_of("world", "rollcall", a) or line_of("player", "greet", a)
            if not pick:
                continue
            if done and not PLAYER.idle(random.uniform(0.6, 1.5)):
                break
            r = PLAYER.file(pick[1], a)
            if r != "ok":
                cut = r
                break
            self.rollcalled[a] = time.monotonic() + random.uniform(120, 180)
            self.deck.on_air.add(a)
            bond_add(a, 1, "перекличка")
            done += 1
        if cut in ("ptt", "paused"):
            # 07.11 Kirill's log said «никого в зоне», but he had just keyed up again over the first answer
            log(f"перекличка прервана ({'ты нажал тангенту' if cut == 'ptt' else 'пауза'}), ответили {done}")
            return
        if not done:
            # 2026-11-06, Kirill: «Кто в эфире?» is how he says hello — 15 times in a row into dead air.
            # Somebody near who already answered says a short «тут я»; nobody near -> the channel just hisses.
            near = [a for a in here if not self.deck.offline(a)]
            random.shuffle(near)
            for a in near:
                pick = line_of("intent", "radio_check", a)
                if pick and PLAYER.file(pick[1], a) == "ok":
                    self.rollcalled[a] = time.monotonic() + random.uniform(120, 180)
                    self.deck.on_air.add(a)
                    self.on_air = True
                    log(f"перекличка: все уже отвечали — {a} коротко: тут я")
                    return
            fx = snd_glob(FX, "kerchunk_*.wav")
            if fx:
                PLAYER.file(random.choice(fx))
        log(f"перекличка: ответили {done}" + ("" if done else " (никого в зоне — в эфире только шипение)"))
        if not done and self.deck.allowed is not None and not self.deck.allowed:
            hint("nobody", "Рядом сейчас никого нет, поэтому никто не ответил. Водители-персонажи появятся по дороге.")
        if done:
            self.on_air = True

    def repeat(self, who):
        """"Повтори": the one you named (else whoever spoke last) says his last line again, word for word.
        The same line is repeated twice at most; the third "повтори" gets silence. Out of range = silence."""
        a = who or PLAYER.last_said
        if not a or a not in PLAYER.said:
            log(f"повтори: {'у ' + a + ' ' if a else ''}нечего повторять")
            return
        if self.deck.offline(a) or (self.deck.allowed is not None
                                    and a not in (self.deck.allowed | self.deck.allowed_far)):
            log(f"повтори: {a} уже вне связи — тишина")
            return
        wav, n = PLAYER.said[a]
        done = self.repeats.get(n, 0)
        if done >= self.REPEAT_MAX:
            log(f"повтори: {a} уже повторял {done} раза — молчит")
            return
        cur = {m for _, m in PLAYER.said.values()}
        self.repeats = {k: v for k, v in self.repeats.items() if k in cur}   # lines nobody can repeat now
        self.repeats[n] = done + 1
        log(f"повтори: {a} повторяет ({done + 1}-й раз) {Path(wav).name}")
        if PLAYER.file(wav, a, replay=True) == "ok":
            self.deck.on_air.add(a)
            self.on_air = True

    def _live(self, kind, who, prefer):
        """«Где ты?» / «сколько ещё ехать?» / «встретимся?» — the answer is chosen by the game: his real distance,
        what is left of his route, your friendship (2026-11-06). True if somebody answered."""
        w = getattr(self, "world", None)
        here = ([a for a in self.deck.allowed if not self.deck.offline(a)] if self.deck.allowed is not None
                else list(self.deck.on_air))
        far = [a for a in (self.deck.allowed_far or ()) if not self.deck.offline(a)]
        if who:
            order = [who] if who in here or who in far else []
        else:
            order = ([prefer] if prefer in here else []) + random.sample(here, len(here))
        for a in order:
            if kind == "dist":
                dd = w.distance(a) if w else None
                v = "dist_near" if dd is not None and dd < 0.6 else "dist_far"
            elif kind == "eta":
                km = w.remaining_km(a) if w else None
                v = "eta_soon" if km is not None and km < 30 else "eta_long"
            else:
                v = "meet_yes" if BONDS and BONDS.level(a) >= 2 else "meet_no"
            pick = line_of("intent", v, a)
            if not pick:
                continue
            log(f"ответ: {kind} -> {v} ({a})")
            if PLAYER.file(pick[1], a) == "ok":
                self.deck.on_air.add(a)
                self.on_air = True
                bond_add(a, 2 if who == a else 1, kind)
                if v == "meet_yes":
                    mood_nudge(a, 1, "позвали встретиться")
            return True
        return False

    def _knows_answer(self, who, prefer):
        """«ты знаешь <X>?» — отвечает по графу canon_relations (1.33): Л/Э → реплика про знакомого,
        «—» или цель неясна → честное «не знаю такого». Кто отвечает: названный, иначе кто в зоне."""
        target = getattr(self, "knows_target", None)
        here = [a for a in (self.deck.allowed or ()) if not self.deck.offline(a)]
        far = [a for a in (self.deck.allowed_far or ()) if not self.deck.offline(a)]
        order = ([who] if who in here or who in far else []) + \
                ([prefer] if prefer in here else []) + random.sample(here, len(here))
        rel = relations()
        for a in order:
            edge = (rel.get(a, {}) or {}).get(target) if target else None
            pool = (reaction_pool("knows", f"{a}__{target}") if edge
                    else reaction_pool("knows", f"{a}__knows_none"))
            if edge and not pool:
                pool = reaction_pool("knows", f"{a}__knows_none")   # реплики под пару ещё нет — честное «не знаю»
            if not pool:
                continue
            pick = self.deck.choose(pool, prefer=a)
            if not pick:
                continue
            actor, wav = pick
            what = "лично" if edge == "Л" else ("заочно" if edge == "Э" else "не знакомы")
            log(f"ответ: knows {target or '?'} ({actor}: {what})")
            if PLAYER.file(wav, actor) == "ok":
                self.deck.on_air.add(actor)
                self.on_air = True
                bond_add(actor, 2 if who == actor else 1, "knows")
            return
        log(f"на knows/{target} ответить некому")

    def _calm_down_answer(self, who, prefer):
        """«успокойся» — да/нет по внутреннему настроению; «да» успокаивает по-настоящему:
        настроение вверх и 10–15 минут тише (инцидент: Витёк соглашался и сразу снова бешеный)."""
        here = [a for a in (self.deck.allowed or ()) if not self.deck.offline(a)]
        far = [a for a in (self.deck.allowed_far or ()) if not self.deck.offline(a)]
        order = ([who] if who in here or who in far else []) + \
                ([prefer] if prefer in here else []) + random.sample(here, len(here)) if here else []
        for a in order:
            mood = BONDS.mood(a) if BONDS else "calm"
            p_no = {"grumpy": 0.45, "tired": 0.1, "calm": 0.15, "cheerful": 0.05}.get(mood, 0.2)
            say_yes = random.random() >= p_no
            pool = reaction_pool("calm_down", "yes" if say_yes else "no")
            pick = self.deck.choose([x for x in pool if x[0] == a] or pool, prefer=a)
            if not pick:
                continue
            actor, wav = pick
            log(f"ответ: calm_down -> {'да' if say_yes else 'нет'} ({actor}, настроение {mood})")
            if PLAYER.file(wav, actor) == "ok":
                self.deck.on_air.add(actor)
                self.on_air = True
                if say_yes:
                    mood_nudge(actor, 2, "успокоился")
                    QUIET_UNTIL[actor] = time.monotonic() + random.uniform(600, 900)
                    bond_add(actor, 1, "успокоился")
            return
        log("на «успокойся» ответить некому")

    def _sorry_answer(self, who, prefer):
        """Извинение маршрутизируется тому, кто обиделся в последние 10 минут (инцидент 09.11:
        извинение ушло Бороде, а обиделся Профессор). Снимает обиду, возвращает в эфир."""
        now = time.monotonic()
        offended = [a for a, t in LAST_OFFENDED.items() if now - t < 600]
        order = ([who] if who in offended else []) + [a for a in offended if a != who]
        if not order:
            order = ([who] if who else []) + ([prefer] if prefer else [])
        for a in order:
            pool = reaction_pool("intent", "sorry") or reaction_pool("player", "ack")
            pick = self.deck.choose([x for x in pool if x[0] == a] or pool, prefer=a)
            if not pick:
                continue
            actor, wav = pick
            log(f"ответ: извинение -> {actor}")
            if PLAYER.file(wav, actor) == "ok":
                self.deck.on_air.add(actor)
                self.on_air = True
                if actor in LAST_OFFENDED:
                    self.deck.off_until[actor] = 0.0        # обида снята, возвращается в эфир
                    bond_add(actor, 5, "извинение")
                    del LAST_OFFENDED[actor]
            return
        log("извинение: ответить некому")

    def all_answer(self, who, kind):
        """A secret (tainik.py): everybody in range answers, one after another (2026-11-06)."""
        here = ([a for a in self.deck.allowed if not self.deck.offline(a)] if self.deck.allowed is not None
                else list(self.deck.on_air))
        random.shuffle(here)
        if who in here:
            here.remove(who)
            here.insert(0, who)
        done = 0
        for a in here:
            pick = line_of("intent", kind, a)
            if not pick:
                continue
            if done and not PLAYER.idle(random.uniform(0.6, 1.4)):
                break
            if PLAYER.file(pick[1], a) != "ok":
                break
            self.deck.on_air.add(a)
            bond_add(a, 2, "секрет")
            mood_nudge(a, 1, "секрет")
            done += 1
        log(f"секрет: ответили {done}")
        if done:
            self.on_air = True

    def foreign_reply(self, lang):
        """The passing foreigner answers you in his language (reactions/foreign_reply/<lang>), a bit far and noisy."""
        pool = reaction_pool("foreign_reply", lang)
        if not pool:
            log(f"иностранцу ({lang}) ответить нечем — реплики не озвучены")
            return
        actor, wav = random.choice(fresh_first(pool))
        heard(wav)
        try:
            x, sr = sf.read(wav, dtype="float32")
            tmp = ROOT / "_foreign.wav"
            sf.write(tmp, degrade(x, sr, random.uniform(0.5, 0.9)), sr)
        except Exception as e:
            log(f"иностранец не ответил: {e!r}")
            return
        log(f"ответ: проезжий иностранец ({lang}) — не понял, но хорошей дороги")
        if OVERLAY:
            OVERLAY.said(_rel(wav), actor)      # subtitle = Russian translation ("ru" in the phrases)
        PLAYER.file(tmp)
        FOREIGN_LAST[1] = time.monotonic()      # one more word to him is still his...
        FOREIGN_LAST[2] += 1                    # ...but after FOREIGN_MAX_REPLIES he is gone
        if FOREIGN_LAST[2] >= FOREIGN_MAX_REPLIES:
            log(f"проезжий иностранец ({lang}) уехал дальше")

    def answer(self):
        _, group, kind, prefer, who = self.pending
        self.pending = None
        if group == "foreign_reply":
            return self.foreign_reply(kind)
        if group == "intent" and kind in SECRET_KINDS:
            return self.all_answer(who, kind)
        if group == "intent" and kind in ("dist", "eta", "meet"):
            if self._live(kind, who, prefer):
                return
            group, kind = "player", "dunno"
        if kind == "who":
            return self.rollcall()
        if kind == "repeat":
            return self.repeat(who)
        if group == "intent" and kind == "truck":
            here = self.deck.allowed if self.deck.allowed is not None else None
            pool = [x for x in reaction_pool("intent", "truck") if here is None or x[0] in here]
            if who:
                pool = [x for x in pool if x[0] == who]   # asked by name: only he answers (or nobody)
            if not pool:
                log(f"про машину ответить некому{' (' + who + ' ещё не умеет)' if who else ''}")
                return
            actor, wav = random.choice(fresh_first(pool))
            heard(wav)
            log(f"ответ: про машину ({actor})")
            if PLAYER.file(wav, actor) == "ok":
                bond_add(actor, 2 if who == actor else 1, "про машину")
                self.deck.on_air.add(actor)
                self.on_air = True
            return
        if group == "intent" and kind == "where" and self._lane_answer(who, prefer):
            return
        if group == "intent" and kind in ("police", "weather", "road"):
            pick = self._honest(kind, who)
            if pick:
                actor, wav = pick
                log(f"ответ: {kind} по делу ({actor})")
                if PLAYER.file(wav, actor) == "ok":
                    bond_add(actor, 2 if who == actor else 1, kind)
                    self.deck.on_air.add(actor)
                    self.on_air = True
                    self._maybe_cross(actor, group)
                return
        # 1.33 (Игорь): перебил в эфире — если реплик interrupt нет, отвечают обычным «принял», а не тишиной
        if kind == "interrupt" and not reaction_pool("player", "interrupt"):
            kind = "ack"
        if group == "intent" and kind == "knows":
            return self._knows_answer(who, prefer)
        if group == "intent" and kind == "calm_down":
            return self._calm_down_answer(who, prefer)
        if group == "intent" and kind == "sorry":
            return self._sorry_answer(who, prefer)
        if group == "intent" and kind in ("police", "road") and reaction_pool("intent", kind + "_unknown"):
            kind += "_unknown"       # nobody near could have seen it: an honest «не видел, я в ту же сторону»
        if not who and kind != "interrupt" and random.random() > 0.6:
            prefer = None                # not always the same person answering
        pool = reaction_pool(group, kind)
        question = group == "intent" and kind not in ("thanks", "bye", "praise", "rude", "mock", "bot", "support") and kind not in SECRET_KINDS
        if group == "intent" and kind in PERSONAL_KINDS and BONDS and who:
            # личная тема по имени: у адресата есть реплика, но дружбы не хватает (lv) -> он отвечает
            # своей уклончивой (reactions/bond/evade, размечены lv0–1), а не общим «не знаю»
            own = [x for x in pool if x[0] == who]
            if own and not any(BONDS.lv_ok(who, _rel(f)) for _, f in own):
                ev = [x for x in reaction_pool("bond", "evade") if x[0] == who]
                if ev:
                    log(f"  {who}: дружбы мало для личного — отвечает уклончиво")
                    pool = ev
        # 1.33 холодный старт: незнакомец (lv0) на первой встрече отвечает на вопрос встречным
        # вопросом «а ты кто?» — вместо готового ответа
        if question and BONDS and who and random.random() < 0.5:
            w = getattr(self, "world", None)
            met_n = (w.met.get(who, {}) if w else {}).get("count", 0)
            if BONDS.level(who) == 0 and not met_n and reaction_pool("who_asks", who):
                pick = self.deck.choose(reaction_pool("who_asks", who))
                if pick:
                    log(f"  {who}: незнакомец — спрашивает, кто спрашивает")
                    if PLAYER.file(pick[1], pick[0]) == "ok":
                        self.deck.on_air.add(pick[0])
                        self.on_air = True
                    return
        # 1.33 слышимое настроение: «как дела» иногда честно отражает реальное настроение
        if group == "intent" and kind == "how_are_you" and BONDS and random.random() < 0.35:
            acts = [a for a, _ in pool]
            if acts:
                a = who if who in acts else (prefer if prefer in acts else random.choice(acts))
                mk = line_of("mood_mark", BONDS.mood(a), a)
                if mk:
                    log(f"ответ: как дела — честно, настроение {BONDS.mood(a)} ({a})")
                    if PLAYER.file(mk[1], a) == "ok":
                        self.deck.on_air.add(a)
                        self.on_air = True
                        bond_add(a, 1, "how_are_you")
                        return
        if who and who not in {a for a, _ in pool}:
            # called by name but he has no line on this topic: "не знаю, не слышал" (a question),
            # "принял" / hello otherwise; whatever he has
            # never "принял" to a question (user 2026-11-04: Ласточка answered «Поняла тебя» to «как дела?»)
            if kind == "greet":
                alts = ["greet"]
            elif question or kind == "dunno":
                alts = ["dunno", "not_heard"] + (["greet"] if kind == "how_are_you" else [])
            else:
                alts = ["ack"]
            for alt_kind in alts:
                alt = [x for x in reaction_pool("player", alt_kind) if x[0] == who]
                if alt and not self.deck.offline(who):
                    pool = alt
                    break
            else:
                if question or kind == "dunno":
                    # asked by name, and he has nothing that fits: he keeps quiet (others don't answer for him)
                    log(f"у {who} нет ответа на {group}/{kind} — молчит")
                    return
        mine = (lambda lst: [x for x in lst if x[0] == who]) if who else (lambda lst: lst)
        if who:
            # asked BY NAME: only he answers (user 2026-11-04: «Борода, как дела?» was answered by Ласточка
            # because Борода had just left the range) - near, or through the noise if he's just out; else silence
            pool = mine(pool) or pool
        # 2026-11-05 (Zhenya): Самарканд said «всё, на ночёвку», the player said «давай, пока» 10 s later -> silence.
        # Somebody who has just signed off still answers a goodbye / thanks addressed to him.
        if who and kind in ("bye", "thanks") and time.monotonic() - self.deck.signed_off.get(who, -1e9) < 180:
            self.deck.grace = who
        try:
            pick = self.deck.choose(pool, prefer=prefer, avoid=self.last_file)
        finally:
            self.deck.grace = None
        if not pick and (question or kind == "dunno"):
            # nobody near has a recorded answer: somebody says he doesn't know / didn't get it
            if group == "intent" and kind in PERSONAL_KINDS and BONDS:
                # личная тема без адресата: пока никто не приятель, ближний отвечает уклончиво (свои lv0–1)
                here = {a for a in (self.deck.allowed or ()) if not self.deck.offline(a)}
                pick = self.deck.choose([x for x in reaction_pool("bond", "evade") if x[0] in here],
                                        prefer=prefer)
                if pick:
                    log(f"  на {kind} отвечают уклончиво ({pick[0]})")
            for alt_kind in ("dunno", "not_heard"):
                if pick:
                    break
                pick = self.deck.choose(mine(reaction_pool("player", alt_kind)), prefer=who or prefer)
                if pick:
                    log(f"  на {group}/{kind} ответа нет — {alt_kind}")
        if not pick and who and self.deck.allowed is not None and who in self.deck.allowed_far:
            # called BY NAME and he is just out of range: he answers through the noise. Without a name nobody
            # far answers (2026-11-06, Kirill: «ты ненастоящий» was answered by Petrovna who had driven off)
            near, self.deck.allowed = self.deck.allowed, set(self.deck.allowed_far)
            try:
                pick = (self.deck.choose(pool, prefer=prefer)
                        or (self.deck.choose(mine(reaction_pool("player", "dunno"))) if question or kind == "dunno" else None)
                        or (None if question or kind == "dunno" else self.deck.choose(mine(reaction_pool("player", "ack")))))
            finally:
                self.deck.allowed = near
            if pick:
                log(f"  отвечает дальний: {pick[0]}")
        if not pick and who:
            log(f"{who} " + ("ушёл из эфира (попрощался)" if self.deck.offline(who) else "вне зоны рации — не слышит")
                + ", молчит (за него никто не отвечает)")
            return
        if not pick:
            log(f"ответить некому: {group}/{kind} (у тех, кто в зоне, нет такой реплики)")
            if self.deck.allowed is not None and not self.deck.allowed and not self.deck.allowed_far:
                hint("nobody", "Рядом сейчас никого нет, поэтому никто не ответил. Водители-персонажи появятся по дороге.")
            return
        actor, wav = pick
        own = personal(group, kind, actor)
        if own:
            actor, wav = own
            log(f"  личная реплика ({BUILD_NAME})")
        if (question or kind == "dunno") and wav == self.last_file:
            log(f"{actor}: тот же ответ второй раз подряд — молчит")
            return
        self.last_file = wav
        log(f"ответ: {group}/{kind} ({actor})")
        if PLAYER.file(wav, actor) == "ok":
            self.deck.on_air.add(actor)
            if kind != "bye":
                self.on_air = True           # the channel knows you're here now
            if kind == "not_heard":
                self.repeat_until = time.monotonic() + 45
            if kind in ("rude", "mock"):
                # 2026-11-06 (user, after Kirill's log): an insulted driver answers back once and then leaves
                # the air for ~10 minutes - he is still on the road nearby, he just doesn't talk to you.
                # Friendship & mood: a grumpy one sulks longer, a cheerful one / a friend gets over it sooner.
                # 2026-11-09 (инцидент: Профессор обиделся на мусор STT): «мягкая грубость» — если в
                # распознанной фразе нет твёрдых маркеров оскорбления (могло распознаться с искажением),
                # штраф мягче и из эфира не уходит: сомнительное срабатывание не роняет дружбу на -25.
                said = getattr(self, "heard_text", "").lower()
                hard = any(w in said for w in ("иди", "пошел", "пошёл", "пошла", "нах", "бля", "жоп",
                                               "заткнись", "отвали", "отстань", "дурак", "дура", "дебил",
                                               "идиот", "козел", "козёл", "урод", "тупой", "тупая",
                                               "мудак", "чмо", "лох", "придур", "задолбал", "хрен тебе"))
                fresh_up = any(q[2] == actor for q in BOND_UP)   # 1.33 (Игорь): апгрейд и обида не в одну секунду
                if (kind == "rude" and not hard) or fresh_up:
                    log(f"  грубость без твёрдых маркеров в распознанном тексте — мягкий режим"
                        if kind == "rude" and not hard else
                        f"  {actor} только что стал ближе — обида смягчена")
                    bond_add(actor, -5, "грубость (мягкая)")
                    mood_nudge(actor, -1, "грубость (мягкая)")
                    LAST_OFFENDED[actor] = time.monotonic()
                    return
                sulk = random.uniform(540, 720) * (0.6 if kind == "mock" else 1.0)   # humiliation: shorter sulk
                if BONDS:
                    sulk = BONDS.sulk_s(actor, sulk)
                self.deck.off_until[actor] = time.monotonic() + sulk
                self.deck.on_air.discard(actor)
                LAST_OFFENDED[actor] = time.monotonic()
                log(f"  {actor} обиделся — молчит {sulk / 60:.0f} мин")
                bond_add(actor, -25 if kind == "rude" else -15, "грубость" if kind == "rude" else "унижение")
                mood_nudge(actor, -2 if kind == "rude" else -1, "грубость" if kind == "rude" else "унижение")
                return
            if group in ("intent", "player", "graf") and kind not in ("not_heard", "interrupt", "click", "already"):
                bond_add(actor, 3 if kind in ("thanks", "praise") else 2 if who == actor else 1, kind)
            if group == "intent" and kind in ("thanks", "praise", "joke", "song", "support"):
                sup = getattr(self, "support", False)
                low = BONDS and BONDS.mood(actor) in ("tired", "grumpy")
                mood_nudge(actor, 2 if sup and low else 1, "поддержка" if sup else kind)
            self._maybe_cross(actor, group)

    CROSS_P = 0.15

    def _maybe_cross(self, actor, group):
        """Step 2 of «вариативность»: now and then a third driver near you chips in on what <actor> said
        (reactions/cross/<actor>, lines by his relations). Never after a cross itself, never on «ack» noise."""
        if group in ("cross", "player", "special") or random.random() > self.CROSS_P or self.deck.allowed is None:
            return
        here = {a for a in self.deck.allowed if a != actor and not self.deck.offline(a)}
        pool = [x for x in reaction_pool("cross", actor) if x[0] in here]
        if not pool:
            return
        b = random.choice(pool)[0]
        log(f"  вклинивается: {b} (на {actor})")
        self.pending = (time.monotonic() + random.uniform(1.0, 2.5), "cross", actor, b, b)


PERSONAL_P = 0.5


def personal(group, kind, actor):
    """A line of this build's own (reactions/only_<variant>/<group>__<kind>) for this actor, half of the time:
    e.g. Ласточка flirting with Кирилл only in his build (2026-11-05). None in the user's radio and in neutral."""
    if not BUILD_NAME or random.random() > PERSONAL_P:
        return None
    pool = [x for x in reaction_pool(f"only_{BUILD_NAME}", f"{group}__{kind}") if x[0] == actor]
    if not pool:
        return None
    pick = random.choice(fresh_first(pool))
    heard(pick[1])
    return pick


def line_of(group, kind, actor):
    """(actor, wav) of this actor in reactions/<group>/<kind>, or None."""
    own = personal(group, kind, actor)
    if own:
        return own
    pool = [x for x in reaction_pool(group, kind) if x[0] == actor]
    if not pool:
        return None
    pool = bond_filter(pool)
    if not pool:
        return None               # only personal lines ("lv") and the friendship isn't there yet
    pick = mood_pick(fresh_first(pool))
    heard(pick[1])
    return pick


def weather_kind(game, world):
    """rain = your wipers are on (the drivers in range are in your area); else dry day / dry night."""
    if game and game.wipers():
        return "rain"
    return "dry_night" if world and world.is_night(world.game_min) else "dry_day"


def play_murmur(world):
    """Far-away chatter at the edge of hearing (near a big city, nobody in range): a scrap of somebody's
    transmission, drowned in static."""
    cands = [p for p in snd_glob(AUDIO, "*/*.wav") if p.parent.name not in world.inside]
    if not cands:
        return
    x, sr = sf.read(random.choice(cands), dtype="float32")
    n = int(random.uniform(1.5, 3.5) * sr)
    s = random.randint(0, max(0, len(x) - n))
    y = x[s:s + n].copy()
    f = min(len(y) // 4, int(0.15 * sr))
    if f > 0:
        y[:f] *= np.linspace(0, 1, f)
        y[-f:] *= np.linspace(1, 0, f)
    y = degrade(y, sr, 1.45) * 0.45
    tmp = ROOT / "_murmur.wav"
    sf.write(tmp, y, sr)
    PLAYER.file(tmp)


ASK_P = 0.35                  # chance that a turn on air is «driver asks the channel, another answers»
ASK_ANSWER = {"road": ("intent", "road"), "food": ("intent", "food"), "joke": ("intent", "joke"),
              "how": ("intent", "how_are_you")}


def air_ask(deck):
    """Drivers talk to each other (2026-11-06, stream chat: «не хватает, чтобы они друг с другом говорили»):
    one near you asks the channel (reactions/ask/<topic>), another near you answers with his own line on that
    topic — any pair can talk this way, not only the pairs that have scenes. True if it was played."""
    here = [a for a in (deck.allowed or ()) if not deck.offline(a)]
    if len(here) < 2:
        return False
    random.shuffle(here)
    for a in here:
        topics = list(ASK_ANSWER)
        random.shuffle(topics)
        for t in topics:
            q = line_of("ask", t, a)
            if not q:
                continue
            others = [b for b in here if b != a]
            g, k = ASK_ANSWER[t]
            pool = [x for x in reaction_pool(g, k) if x[0] in others
                    and not (BONDS and BONDS.calls_by_name(_rel(x[1])))]     # not «Железяка» to another driver
            if not pool:
                continue
            ans = mood_pick(fresh_first(pool))
            heard(ans[1])
            log(f"эфир: {a} спрашивает канал ({t}) -> отвечает {ans[0]}")
            if PLAYER.file(q[1], a) != "ok":
                return True
            if PLAYER.idle(random.uniform(0.7, 1.6)):
                PLAYER.file(ans[1], ans[0])
            deck.on_air.update((a, ans[0]))
            return True
    return False


def greet_reply(deck, cfg, greeter):
    """Someone on the channel answers an actor's hello."""
    if random.random() > cfg.get("greet_reply_chance", 0.85):
        return
    pick = deck.choose(reaction_pool("greet_reply", greeter), exclude=(greeter,))
    if not pick or not PLAYER.idle(random.uniform(0.8, 2.0)):
        return
    actor, wav = pick
    log(f"  отвечает: {actor}")
    if PLAYER.file(wav, actor) == "ok":
        deck.on_air.add(actor)


QUIT_REQ = {"why": None}      # set by «Выход» in the tray, by `CB-Radio.exe --quit` or by a second launch
# «Эфир» levels (2026-11-05: Kirill's idea, the user chose 4 levels, one menu item). «Обычно» = how it was.
AIR = {
    "calm":   {"name": "Спокойно", "meet_every_s": 900, "spawn_after_quiet_s": 360, "gap": (240, 480),
               "max_inside": 2, "cooldown_factor": 1.5, "companion_chance": 0.20},
    "normal": {"name": "Обычно", "meet_every_s": 480, "spawn_after_quiet_s": 150, "gap": (120, 300),
               "max_inside": 3, "cooldown_factor": 1.0, "companion_chance": 0.25},
    "busy":   {"name": "Оживлённо", "meet_every_s": 240, "spawn_after_quiet_s": 90, "gap": (90, 180),
               "max_inside": 3, "cooldown_factor": 0.5, "companion_chance": 0.30},   # 5 = «балаган» (user)
    "rush":   {"name": "Час пик", "meet_every_s": 120, "spawn_after_quiet_s": 60, "gap": (60, 120),
               "max_inside": 4, "cooldown_factor": 0.25, "companion_chance": 0.35},
}


def apply_air(cfg, world, level):
    p = AIR.get(level) or AIR["normal"]
    cfg["air"] = level if level in AIR else "normal"
    cfg["gap_min_s"], cfg["gap_max_s"] = p["gap"]
    if world:
        world.set_air(p)
    return p


MEET_REQ = {"keys": []}      # TEST (a queue): `meet [actor]` over the lock socket -> world.summon (a driver right next to you)


def _send_quit(port):
    """Ask the running radio to shut down (over its lock socket). True if it answered."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3) as c:
            c.sendall(b"quit")
            return c.recv(16) == b"ok"
    except OSError:
        return False


def single_instance(port, quit_only=False, takeover=False):
    """Hold the lock port for the process lifetime and listen there for «quit» (2026-11-05: the user could only
    close a windowless radio through Task Manager). A second launch offers to switch the running one off."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    bound = False
    for _ in range(40 if takeover else 1):    # 1.13: «перезапустить с правами администратора» — the old one is leaving
        try:
            s.bind(("127.0.0.1", port))
            bound = True
            break
        except OSError:
            if takeover:
                time.sleep(0.5)
    if not bound:
        windowless = sys.stdout is None
        if quit_only:
            ok = _send_quit(port)
            if not ok and windowless:
                ctypes.windll.user32.MessageBoxW(None, "Не получилось выключить «Канал 15». Закройте его через "
                                                       "диспетчер задач (CB-Radio.exe).", "Канал 15", 0x30)
            sys.exit(0)
        print("CB-рация уже запущена в другом окне.")
        if windowless:                        # no console (pythonw / windowed exe): ask in a box
            if ctypes.windll.user32.MessageBoxW(
                    None, "«Канал 15» уже работает (значок рации возле часов).\n\nВыключить его?", "Канал 15",
                    0x04 | 0x20 | 0x40000) == 6:          # Yes/No, question, topmost; 6 = Yes
                _send_quit(port)
        else:
            time.sleep(3)
        sys.exit(0)
    if quit_only:                             # nothing to switch off
        s.close()
        if sys.stdout is None:
            ctypes.windll.user32.MessageBoxW(None, "«Канал 15» сейчас не запущен.", "Канал 15", 0x40)
        sys.exit(0)
    s.listen(2)

    def serve():
        while True:
            try:
                c, _ = s.accept()
                with c:
                    c.settimeout(3)
                    msg = c.recv(64).strip()
                    if msg.startswith(b"meet"):
                        MEET_REQ["keys"].append(msg[4:].strip().decode("ascii", "ignore") or "*")
                        c.sendall(b"ok")
                    elif msg == b"quit":
                        QUIT_REQ["why"] = "по команде выключения"
                        c.sendall(b"ok")
                        threading.Timer(4.0, os._exit, (0,)).start()   # main loop may be busy playing a scene
            except OSError:
                time.sleep(1)
    import threading
    threading.Thread(target=serve, daemon=True).start()
    return s


def ptt_test():
    import pygame
    pygame.init()
    pygame.joystick.init()
    js = {}
    print("Нажимай кнопки на руле, Ctrl+C - выход.")
    while True:
        for e in pygame.event.get():
            if e.type == pygame.JOYDEVICEADDED:
                j = pygame.joystick.Joystick(e.device_index)
                js[j.get_instance_id()] = j
                print("устройство:", j.get_name())
            elif e.type == pygame.JOYBUTTONDOWN:
                name = js[e.instance_id].get_name() if e.instance_id in js else "?"
                line = f"{name}: кнопка {e.button} (в controls.sii ETS2 это joy.b{e.button + 1})"
                print(line, flush=True)
                log("ptt-test " + line)
        time.sleep(0.01)


def selftest():
    """Build check (2026-11-04, exe): everything loads, one line is decoded, speech recognition works.
    Plays nothing, opens no device, takes no lock -> safe next to a running radio."""
    import intents
    import world as world_mod
    ph = all_phrases()
    print("фраз в колоде:", len(ph), "| приветствий игроку:", len(reaction_pool("player", "greet")))
    first = next(iter(snd_glob(AUDIO, "*/*.wav")), None)
    x, sr = sf.read(first, dtype="float32")
    print("звук читается:", first.name, sr, f"{len(x) / sr:.1f} с")
    acts = json.loads(PHRASES_JSON.read_text(encoding="utf-8"))["actors"]
    w = world_mod.World(load_cfg(), acts)
    print("мир:", len(w.cities), "городов,", len(w.drivers), "водителей")
    try:
        import company
        print("сохранения игры:", company.savegame.SAVES)
    except Exception as e:
        print("компания:", repr(e))
    print("распознавание:", intents.understand("Михалыч, как дела?"))
    from faster_whisper import WhisperModel
    local = ROOT / "models" / "whisper-small"
    m = WhisperModel(str(local) if (local / "model.bin").exists() else "small", device="cpu", compute_type="int8")
    from scipy.signal import resample_poly
    y = resample_poly(x, 1, 3).astype(np.float32) if sr == 48000 else x
    print("whisper:", " ".join(s.text for s in m.transcribe(y, language="ru")[0]).strip())
    print("SELFTEST OK")


TRAY_STATE = {}
OVERLAY = None                # overlay module once the stream overlay is running (cfg "overlay")
TRAY_MOD = None
BOT_URL = "https://t.me/kanal15_publisher_bot"


REPORT_URL = "https://storage.yandexcloud.net/kanal15-reports/in/"     # receive-only: anyone may put, nobody may read
NL = chr(10)
REPORT_WARN = NL.join([
    "Отправить журнал разработчикам «Канала 15»?",
    "",
    "Журнал помогает нам находить ошибки и понимать, что добавить в рацию. Его увидит только разработчик, "
    "через 30 дней он удаляется сам.",
    "",
    "В журнале есть:",
    "• ваши фразы в рацию — текстом (голос не отправляется);",
    "• события игры: города, штрафы, доставки;",
    "• настройки рации: микрофон, руль, версия Windows, путь к папке рации "
    "(в нём может быть имя пользователя Windows).",
    "Сохранения игры и файлы с компьютера не отправляются.",
    "",
    "Да — отправить журнал",
    "Нет — отправить без ваших фраз",
    "Отмена — ничего не отправлять"])


def _msgbox(text, title, flags):
    try:
        return ctypes.windll.user32.MessageBoxW(None, text, title, flags | 0x40000)    # MB_TOPMOST
    except Exception:
        return 0


def send_report():
    """«Отправить журнал разработчикам…» (2026-11-06, user): a warning first (speech transcripts are in the log),
    then one click — the archive goes to the receive-only bucket. No keys in the radio: an anonymous PUT.
    Without internet: the old way — the archive in a folder + the bot chat."""
    import secrets
    import urllib.request
    # 2026-11-06 (user): the player chooses — the whole log, the log without his own phrases, or nothing.
    # The radio never offers this by itself (not even after a crash): only this menu item.
    ans = _msgbox(REPORT_WARN, "Канал 15 — отправить журнал", 0x3 | 0x40)              # MB_YESNOCANCEL|ICONINFO
    if ans not in (6, 7):                                                               # IDYES / IDNO
        log("журнал: игрок не стал отправлять")
        return None
    z = make_report(show=False, hide_speech=ans == 7)
    rid = f"{datetime.now():%Y%m%d-%H%M%S}_{BUILD_NAME or VARIANT or 'public'}_{secrets.token_hex(3)}"
    try:
        rk = _report_key()
        if not rk:
            raise RuntimeError("нет ключа отправки")
        _s3_put_signed("kanal15-reports", f"in/{rid}.zip", z.read_bytes(), rk[0], rk[1])
    except Exception as e:
        log(f"журнал не отправился: {e!r} — показываю архив и чат с ботом")
        _msgbox(NL.join(["Не получилось отправить журнал (нет интернета?).", "",
                         "Архив сейчас откроется в папке — можно перетащить его в чат с ботом @kanal15_publisher_bot."]),
                "Канал 15", 0x30)
        _show_report(z)
        return z
    num = rid.split("_")[-1]
    log(f"журнал отправлен разработчикам: {rid}")
    _msgbox(NL.join(["Журнал отправлен. Спасибо!", "", f"Номер отчёта: {num}", "",
                     "Если хотите рассказать, что случилось или что хочется в рации, напишите боту "
                     "@kanal15_publisher_bot и укажите этот номер."]), "Канал 15", 0x40)
    return z


def _report_key():
    """The upload-only key (service account kanal15-reporter: may only PUT into kanal15-reports/in/, can't read,
    list or delete). In a build it sits in the tainik (phrases/x.dat), at the developer's — report_key.txt."""
    rk = (SECRETS or {}).get("rk")
    if rk:
        return rk
    try:
        ls = [x.strip() for x in (ROOT / "report_key.txt").read_text(encoding="utf-8-sig").splitlines() if x.strip()]
        return ls[:2] if len(ls) >= 2 else None
    except OSError:
        return None


def _s3_put_signed(bucket, key, data, kid, secret, ctype="application/zip"):
    """PUT one object to Yandex Object Storage, AWS Signature V4, standard library only."""
    import datetime as _dt
    import hashlib
    import hmac
    import urllib.parse
    import urllib.request
    host, region = "storage.yandexcloud.net", "ru-central1"
    now = _dt.datetime.now(_dt.timezone.utc)
    amz, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    ph = hashlib.sha256(data).hexdigest()
    hdr = {"host": host, "x-amz-content-sha256": ph, "x-amz-date": amz, "content-type": ctype}
    uri = "/" + bucket + "/" + urllib.parse.quote(key, safe="/~")
    signed = ";".join(sorted(hdr))
    canon = NL.join(["PUT", uri, "", "".join(f"{k}:{hdr[k]}{NL}" for k in sorted(hdr)), signed, ph])
    scope = f"{day}/{region}/s3/aws4_request"
    sts = NL.join(["AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(canon.encode()).hexdigest()])
    k = hmac.new(("AWS4" + secret).encode(), day.encode(), hashlib.sha256).digest()
    for part in (region, "s3", "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    sig = hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()
    hdr["authorization"] = f"AWS4-HMAC-SHA256 Credential={kid}/{scope}, SignedHeaders={signed}, Signature={sig}"
    req = urllib.request.Request(f"https://{host}{uri}", data=data, method="PUT",
                                 headers={k2: v for k2, v in hdr.items() if k2 != "host"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def _show_report(z):
    import subprocess
    subprocess.Popen(["explorer", f"/select,{z}"])
    os.startfile(BOT_URL)


def _hide_speech(data):
    """The log without the player's own words: in «тангента: «…»» lines the phrase is replaced, what the radio
    understood (intent, who answered) stays."""
    import re as _re
    out = []
    for ln in data.decode("utf-8", "replace").splitlines():
        if "тангента" in ln and "«" in ln:
            ln = _re.sub(r"«[^»]*»", "«(скрыто)»", ln)
        out.append(ln)
    return NL.join(out).encode("utf-8")


def make_report(show=True, hide_speech=False):
    """«Сообщить о проблеме» (2026-11-05): журналы и версия в один zip, показать его в папке и открыть чат
    с ботом. Ничего не отправляется само: человек сам перетаскивает файл в чат."""
    import platform
    import subprocess
    import zipfile
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    z = out / f"Kanal15-report-{datetime.now():%Y%m%d-%H%M%S}.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ("cb_radio.log", "crash.log", "update/update.log", "update/applied.json", "version.json",
                     "config.json", "install.json"):
            p = ROOT / name
            if p.exists():
                data = p.read_bytes()
                if name == "cb_radio.log":
                    data = b"\n".join(data.splitlines()[-4000:])     # the last few hours are enough
                    if hide_speech:
                        data = _hide_speech(data)
                zf.writestr(name, data)
        zf.writestr("about.json", json.dumps({"version": VERSION, "date": VERSION_DATE, "build": BUILD_NAME,
                                              "speech_hidden": bool(hide_speech),
                                              "windows": platform.platform(), "created": datetime.now().isoformat()},
                                             ensure_ascii=False, indent=1))
    log(f"отчёт о проблеме собран: {z}")
    if show:
        _show_report(z)
    return z
_HINTED = set()


def hint(kind, text):
    """A Windows notification from the tray icon, once per session per kind (it does not take focus from the
    game). For «I press the key and nobody answers» (2026-11-05, Kirill): the reason is said, not guessed."""
    log(f"подсказка: {text}")
    if kind in _HINTED or not TRAY_MOD:
        return
    _HINTED.add(kind)
    TRAY_MOD.notify(text)


try:
    _V = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    VERSION, VERSION_DATE = _V["version"], _V["date"]
except Exception:
    VERSION, VERSION_DATE = "?", ""


def main(argv):
    global TRAY_STATE, OVERLAY
    try:                                      # native crashes (audio / whisper / joystick DLLs) -> crash.log
        import faulthandler
        faulthandler.enable(open(ROOT / "crash.log", "a", encoding="utf-8"), all_threads=True)
    except Exception:
        pass
    cfg = load_cfg()
    load_variant(cfg)
    if VARIANT:
        log(f"вариант обращений: {VARIANT} ({len(HANDLE_LINES)} реплик с именем)")
    PLAYER.cfg = cfg
    if "--devices" in argv:
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] > 0:
                print(i, d["name"])
        return
    if "--ptt-test" in argv:
        return ptt_test()
    if "--selftest" in argv:
        return selftest()
    if not all_phrases():
        sys.exit(f"нет фраз в {AUDIO} — сначала tools\\gen_eleven.py level3")
    if "--listen" in argv:
        # --listen [actor ...]: only items of these actors (scenes where they speak too)
        who = [a for a in argv if not a.startswith("--")]
        for p in all_phrases():
            if who and not set(who) & set(actors_of(p)):
                continue
            print(p)
            PLAYER.item(p)
            time.sleep(0.6)
        return
    deck = Deck()
    if "--now" in argv:
        p = deck.draw()
        log(f"эфир: {p}")
        if p:
            PLAYER.item(p)
        return

    _lock = single_instance(cfg["lock_port"], quit_only="--quit" in argv, takeover="--takeover" in argv)  # noqa: F841 (held for the process lifetime)
    ov = cfg.get("overlay") or {}
    ov_port = int(ov.get("port", 47823))

    def overlay_set(on):
        """Stream overlay for OBS (browser source, localhost only). OFF by default; tray toggles it, choice saved."""
        global OVERLAY
        try:
            import overlay as overlay_mod
            if on:
                # subtitle journal for shorts (subs/<date>.jsonl): only the author's radio run from source,
                # never in players' builds (config "subs_journal" overrides)
                jr = ROOT / "subs" if cfg.get("subs_journal", not BUILD_NAME and not getattr(sys, "frozen", False)) else None
                OVERLAY = overlay_mod if overlay_mod.start(ov_port, PHRASES_JSON, BUILD_NAME or VARIANT, log, jr) else None
            if OVERLAY:
                OVERLAY.add_texts(secret_texts())
            else:
                OVERLAY = None
                overlay_mod.stop()
                log("оверлей для стрима: выключен")
        except Exception as e:
            OVERLAY = None
            log(f"оверлей для стрима не запустился: {e!r}")
        try:                                  # remember the choice (other settings untouched)
            cur = json.loads(CFG_FILE.read_text(encoding="utf-8-sig")) if CFG_FILE.exists() else {}
            cur["overlay"] = {"enabled": bool(OVERLAY), "port": ov_port}
            CFG_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    if ov.get("enabled", False):
        overlay_set(True)
    tray = None
    if "--console" not in argv:               # the radio's icon by the clock instead of a console window
        try:
            import tray as tray_mod
            names = {k: a.get("name", k) for k, a in json.loads(PHRASES_JSON.read_text(encoding="utf-8"))["actors"].items()}
            if tray_mod.start(cfg, CFG_FILE, LOG_FILE, ROOT, names, VERSION):
                tray, TRAY_STATE = tray_mod, tray_mod.STATE
                globals()["TRAY_MOD"] = tray_mod
                log("значок в трее: включён")
            else:
                log("значок в трее не запустился: нет pystray")
        except Exception as e:
            log(f"значок в трее не запустился: {e!r}")
        if not tray and sys.stdout is None:   # windowless and no icon: at least tell how to switch it off
            ctypes.windll.user32.MessageBoxW(
                None, "Значок рации возле часов не появился, но эфир работает.\n\nВыключить «Канал 15»: ярлык "
                      "«Выключить Канал 15» в меню «Пуск» или ещё раз ярлык «Канал 15».", "Канал 15", 0x40 | 0x40000)
    game = Game()
    PLAYER.game = game
    import gamecheck
    GSEEN = {"next": 0.0, "since": None, "diag": None, "dir": None}
    if tray:
        def plugin_install():
            src = ROOT / "installer" / "plugins" / gamecheck.PLUGIN
            if not GSEEN["dir"]:
                ok, text = False, "Сначала запустите игру — рация найдёт её папку."
            elif not src.exists():
                ok, text = False, "Файла плагина нет в папке рации. Запустите установщик ещё раз."
            else:
                ok, text = gamecheck.fix(src, src.parent / "vc", GSEEN["dir"])
                if ok:
                    GSEEN.update(since=None, diag=None)      # look again after the game restart
            log(f"плагин из меню: {text}")
            tray.notify(text)
        tray.HOOKS.update(plugin_needed=lambda: gamecheck.needs_fix(GSEEN["dir"]), plugin_install=plugin_install)

        # 1.27: rebind PTT from the tray menu (for players without a wheel who missed the installer step)
        # 1.28: any device, any moment — mouse buttons too, and the new button works at once (no radio restart)
        def ptt_rebind():
            import tkinter as tk
            from tkinter import ttk
            root = tk.Tk()
            root.title("Переназначить кнопку рации")
            root.geometry("400x240")
            root.resizable(False, False)
            tk.Label(root, text="Нажмите нужную кнопку на руле, геймпаде,\nклавиатуре или мыши.", font=("Segoe UI", 10)).pack(pady=15)
            status = tk.Label(root, text=f"Сейчас: {ptt.describe()}\nЖду нажатия…", font=("Segoe UI", 11, "bold"), fg="#333")
            status.pack(pady=10)
            result = {"ptt": None, "base": {}, "listeners": [], "stopped": False}

            def cleanup():
                result["stopped"] = True
                for li in result["listeners"]:
                    try:
                        li.stop()
                    except Exception:
                        pass
                root.destroy()

            def got(value, text):
                result["ptt"] = value
                for li in result["listeners"]:        # enough: later presses must not overwrite the result
                    try:
                        li.stop()
                    except Exception:
                        pass
                status.config(text=f"✔ {text}", fg="#2e7d32")
                root.after(1200, root.destroy)        # let the user see what got assigned

            btn_frame = tk.Frame(root)
            btn_frame.pack(pady=15)
            ttk.Button(btn_frame, text="Отмена", command=cleanup).pack()

            def poll_buttons():
                if result["ptt"] or result["stopped"] or not root.winfo_exists():
                    return
                try:
                    now = _winmm_buttons(mm, result["base"])
                except Exception:
                    now = {}
                for j, (name, b) in now.items():
                    pressed = b & ~result["base"].get(j, (name, 0))[1]
                    if pressed:
                        num = (pressed & -pressed).bit_length() - 1
                        got((name, num), f"{name}, кнопка {num}")
                        return
                root.after(40, poll_buttons)

            def kb_release(key):
                if result["ptt"] or result["stopped"]:
                    return
                try:
                    got(("keyboard", _input_name(key)), f"клавиша {_input_name(key)}")
                except Exception as e:
                    log(f"ошибка обработки клавиши: {e!r}")

            def ms_click(x, y, button, pressed):
                if not pressed or result["ptt"] or result["stopped"]:
                    return
                try:
                    if root.winfo_containing(x, y) is not None:
                        return            # a click on this very dialog (e.g. «Отмена») must not become the button
                    got(("mouse", _input_name(button)), f"мышь: {_input_name(button)}")
                except Exception as e:
                    log(f"ошибка обработки мыши: {e!r}")

            try:
                mm = ctypes.WinDLL("winmm")
                with _WINMM_LOCK:
                    mm.joyConfigChanged(0)
                result["base"] = _winmm_buttons(mm)
                log(f"переназначение кнопки: найдено устройств {len(result['base'])}")
            except Exception as e:
                mm = None
                log(f"переназначение кнопки: ошибка опроса джойстиков {e!r}")

            try:
                from pynput import keyboard, mouse
                for li in (keyboard.Listener(on_press=lambda k: None, on_release=kb_release),
                           mouse.Listener(on_click=ms_click)):
                    li.start()
                    result["listeners"].append(li)
                log("переназначение кнопки: слушатели клавиатуры и мыши запущены")
            except Exception as e:
                log(f"переназначение кнопки: pynput не работает {e!r}")

            poll_buttons()
            root.mainloop()

            if result["ptt"]:
                try:
                    cfg["ptt"] = {"device": result["ptt"][0], "button": result["ptt"][1]}
                    CFG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
                    log(f"кнопка рации переназначена: {result['ptt']}")
                    ptt.want_rebind = cfg["ptt"]        # applied by the very next poll() — restart not needed
                    tray.notify(f"Кнопка рации: {result['ptt'][0]}, {result['ptt'][1]}.\nЖмите её в эфире — перезапуск не нужен.")
                except Exception as e:
                    log(f"кнопка рации: не удалось сохранить {e!r}")
                    tray.notify(f"Не удалось сохранить настройку ({e})")
        tray.HOOKS["ptt_rebind"] = ptt_rebind
        tray.HOOKS["ptt_now"] = lambda: ptt.describe()        # меню значка: строка «Кнопка рации: …»

        # 1.13: the game runs as administrator (many repacks mark it so) -> Windows keeps the radio away
        def admin_fix():
            ok, text = gamecheck.clear_admin_flags()
            log(f"снять «от администратора» из меню: {text}")
            if ok:
                GSEEN.update(since=None, diag=None)
            tray.notify(text)

        def admin_restart():
            if getattr(sys, "frozen", False):
                exe, params = sys.executable, "--takeover"
            else:
                exe, params = sys.executable, f'"{Path(__file__).resolve()}" --takeover'
            ok, why = gamecheck.run_as_admin(exe, params, wait=False)
            log(f"перезапуск рации с правами администратора: {ok} {why or ''}")
            if ok:
                QUIT_REQ["why"] = "для перезапуска с правами администратора"
            else:
                tray.notify("Рация не перезапущена: Windows не дала прав администратора." if why == "cancelled"
                            else f"Рация не перезапущена ({why}).")

        def admin_state():
            if GSEEN["diag"] != "admin":
                return None
            return "flag" if gamecheck.admin_flags() else ("restart" if not gamecheck.is_admin() else None)
        tray.HOOKS.update(admin_state=admin_state, admin_fix=admin_fix, admin_restart=admin_restart)
    ptt = PTT(cfg)
    PLAYER.ptt = ptt            # poll() сам смотрит self.ok — так переназначение из меню (1.28) оживляет тангенту сразу
    op = None                   # Operator ниже; ensure_ears() дергается из главного цикла, к тому моменту op уже есть
    ears = [Ears(cfg) if ptt.ok else None]
    ptt.ears = ears[0] if ears[0] and ears[0].ok else None

    def on_silent(name):
        import mic
        hint("mic_silent", mic.privacy_blocked() or f"Рация не слышит микрофон «{name}» (полная тишина). "
             "Правый клик по значку рации → Микрофон → выберите другой.")

    def register_mic_hooks():
        if not tray:
            return
        import mic as mic_mod

        def mic_set(name):
            if ears[0].open(name):
                if not ears[0].ok:            # no microphone at start: the recogniser starts now
                    import threading
                    ears[0].ok = True
                    ears[0].want_model = threading.Event()
                    threading.Thread(target=ears[0]._worker, args=((cfg.get("mic") or {}).get("model", "small"),),
                                     daemon=True).start()
                ptt.ears = ears[0]
                op.ears = ears[0]
                cfg.setdefault("mic", {})["device"] = name
                try:
                    cur = json.loads(CFG_FILE.read_text(encoding="utf-8-sig"))
                    cur.setdefault("mic", {})["device"] = name
                    CFG_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=4), encoding="utf-8")
                except (OSError, ValueError) as e:
                    log(f"настройки не сохранились: {e!r}")
                ears[0].last_info = "микрофон сменён — нажмите тангенту и скажите что-нибудь"
        tray.HOOKS.update(mics=lambda: [n for _, n in mic_mod.inputs(sd)], mic_now=lambda: ears[0].dev_name,
                          mic_info=lambda: ears[0].last_info, mic_set=mic_set)

    def ensure_ears():
        """1.28: меню «переназначить кнопку» может дать рации кнопку, которой не было на старте, — микрофон просыпается."""
        if ears[0] is None and ptt.ok:
            ears[0] = Ears(cfg)
            ears[0].on_silent = on_silent
            ptt.ears = ears[0] if ears[0].ok else None
            if op is not None:
                op.ears = ears[0]
            register_mic_hooks()
            log(f"микрофон подключён к тангенте: {ears[0].dev_name}")

    ptt.on_rebind = ensure_ears
    if ears[0]:
        ears[0].on_silent = on_silent
        register_mic_hooks()
    elif tray:
        tray.HOOKS.update(mic_now=lambda: "кнопка рации не найдена — запустите установщик ещё раз")
    op = Operator(deck, ptt.ears)
    world = None
    if (cfg.get("world") or {}).get("enabled", True):
        try:
            import world as world_mod
            acts = json.loads(PHRASES_JSON.read_text(encoding="utf-8"))["actors"]
            world = world_mod.World(cfg, acts)
            if world.ok:
                PLAYER.world = world
                deck.allowed = set()
                try:                                     # your company + the freight market, from your save
                    import company as company_mod
                    world.company = company_mod.Company(log=log)
                except Exception as e:
                    log(f"компания: не подключилась ({e!r})")
                log(f"живая трасса: {len(world.cities)} городов, {len(world.drivers)} водителей в рейсах, "
                    f"радиус рации {world.range / 1000:.1f} км")
            else:
                world = None
                log("живая трасса выключена: нет map/cities_full.json — все говорят как раньше")
        except Exception as e:
            world = None
            log(f"живая трасса не запустилась: {e!r}")
    global BONDS, SECRETS
    if _tainik:
        try:
            import intents as _intents
            SECRETS = _tainik.load(ROOT / "phrases")
            SECRET_KINDS.update(_tainik.kinds(SECRETS))
            _intents.add_secrets(SECRETS.get("intents"))
            if OVERLAY:
                OVERLAY.add_texts(secret_texts())
        except Exception as e:
            log(f"секреты: {e!r}")
    try:                                      # 2026-11-06: friendship & mood (bonds.py)
        import bonds as bonds_mod
        BONDS = bonds_mod.Bonds(ROOT / "bonds.json", PHRASES_JSON, log)
        if world:
            BONDS.seed(world.met)
            BONDS.set_world(world.game_min, world.is_night(world.game_min), False)
        lv = [BONDS.level(k) for k in BONDS.st]
        log(f"дружба: водителей {len(lv)} — знакомых {lv.count(1)}, приятелей {lv.count(2)}, друзей {lv.count(3)}")
    except Exception as e:
        BONDS = None
        log(f"дружба не подключилась: {e!r}")
    upd = None
    try:                                      # 2026-11-05: quiet background updates (updater.py, launcher.py)
        import updater as updater_mod
        upd = updater_mod.Updater(ROOT, cfg, VERSION, log=log, notify=(tray.notify if tray else None))
        upd.start()
        if tray:
            def upd_check():
                import threading

                def run():
                    tray.notify("Обновления: " + upd.check())
                threading.Thread(target=run, daemon=True).start()

            def upd_auto():
                upd.auto = not upd.auto
                try:
                    cur = json.loads(CFG_FILE.read_text(encoding="utf-8-sig"))
                    cur.setdefault("update", {})["auto"] = upd.auto
                    CFG_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=4), encoding="utf-8")
                except (OSError, ValueError):
                    pass
            tray.HOOKS.update(report=send_report)
            tray.HOOKS.update(upd_status=lambda: upd.status, upd_check=upd_check, upd_auto=upd_auto,
                              upd_auto_on=lambda: upd.auto, upd_enabled=lambda: upd.enabled,
                              changelog=lambda: os.startfile(str(ROOT / "CHANGELOG.md")))
    except Exception as e:
        log(f"обновления не подключились: {e!r}")
    log(f"папка рации: {ROOT}")               # диагностика: две копии программы в логе неотличимы иначе (Данила 08.11)
    try:
        _ap = json.loads((ROOT / "update" / "applied.json").read_text(encoding="utf-8"))
        log(f"обновления: применена версия {_ap.get('version')} (ok={_ap.get('ok')}, стартов "
            f"{_ap.get('starts', 0)})")
    except (OSError, ValueError):
        pass
    upd_ok_at = time.monotonic() + 20         # healthy for 20 s -> keep the update the launcher just applied
    air = apply_air(cfg, world, cfg.get("air", "normal"))
    log(f"эфир: {air['name']}")
    STATIC_NOW["k"] = STATIC.get(cfg.get("static", "mid"), STATIC["mid"])["k"]
    log(f"помехи: {STATIC.get(cfg.get('static', 'mid'), STATIC['mid'])['name']}")
    if tray:
        def air_set(level):
            p = apply_air(cfg, world, level)
            try:
                cur = json.loads(CFG_FILE.read_text(encoding="utf-8-sig"))
                cur["air"] = cfg["air"]
                CFG_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=4), encoding="utf-8")
            except (OSError, ValueError) as e:
                log(f"настройки не сохранились: {e!r}")
            log(f"эфир: {p['name']} (из меню значка)")
        tray.HOOKS.update(overlay_on=lambda: bool(OVERLAY), overlay_toggle=lambda: overlay_set(not OVERLAY),
                          overlay_url=lambda: f"http://127.0.0.1:{ov_port}/")
        tray.HOOKS.update(air_levels=lambda: [(k, v["name"]) for k, v in AIR.items()],
                          air_now=lambda: cfg.get("air", "normal"), air_set=air_set)

        def static_set(level):
            level = level if level in STATIC else "mid"
            cfg["static"] = level
            STATIC_NOW["k"] = STATIC[level]["k"]
            try:
                cur = json.loads(CFG_FILE.read_text(encoding="utf-8-sig"))
                cur["static"] = level
                CFG_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=4), encoding="utf-8")
            except (OSError, ValueError) as e:
                log(f"настройки не сохранились: {e!r}")
            log(f"помехи: {STATIC[level]['name']} (из меню значка)")
        tray.HOOKS.update(static_levels=lambda: [(k, v["name"]) for k, v in STATIC.items()],
                          static_now=lambda: cfg.get("static", "mid"), static_set=static_set)
    w_acc, w_saved = 0.0, time.monotonic()
    job_t = 0.0
    hired_seen = set()          # your hired drivers already noticed near you (once per session each)
    hq, last_hired = [], -1e9   # hired drivers to put on air: (due, id, "loaded"|"empty", noticed)
    deliv_pending, last_deliv = [], -1e9     # their deliveries -> the accountant's report (not more than 1 per 25 min)
    op.world, op.game = world, game
    fines = Fines()
    wq = []                                  # (group, kind, actor, created) lines of the living highway
    murmur_acc, next_murmur = 0.0, random.uniform(60, 150)
    foreign_acc, next_foreign = 0.0, random.uniform(180, 420)
    buh_q, fines_day = [], {}                # accountant's voice messages after your fines
    log(f"Канал 15 v{VERSION} ({VERSION_DATE}) запущен: {len(all_phrases())} шт., пауза {cfg['gap_min_s']}-{cfg['gap_max_s']} с. Жду игру...")
    driving_s = 0.0
    next_at = random.uniform(*cfg["first_after_s"])
    max_silence = float(cfg.get("max_silence_s", 240))   # user 2026-11-04: «главное чтобы не было тихого эфира»
    quiet_drive, seen_voices = 0.0, 0
    kgap = cfg.get("kerchunk_gap_s") or []
    fx = snd_glob(FX, "kerchunk_*.wav")
    next_k = random.uniform(*kgap) if kgap and fx else None
    prev = None
    last = time.monotonic()
    while True:
        try:
            ptt.poll()
            time.sleep(0.05)
            ptt.poll()
            now = time.monotonic()
            dt, last = now - last, now
            st = game.state(cfg["require_engine_on"])
            if now >= GSEEN.get("ev_next", 0.0):         # 1.26: the fines plugin goes into the game quietly, no prompts
                GSEEN["ev_next"] = now + 60
                try:
                    gx_ = gamecheck.game_process()
                    gd_ = gamecheck.game_dir(gx_) if gx_ else None
                    if gd_:
                        GSEEN["dir"] = gd_
                        tried_ = GSEEN.setdefault("ev_tried", set())
                        if str(gd_) not in tried_:           # one attempt per game folder per run
                            tried_.add(str(gd_))
                            _done, _txt = gamecheck.quiet_events_install(ROOT / "installer" / "plugins", gd_)
                            if _txt:
                                log(f"плагин штрафов: {_txt}")
                except Exception as e:
                    log(f"плагин штрафов: {e!r}")
            if st == "no_game":                  # «жду игру» while the game IS running -> say why (gamecheck.py)
                if now >= GSEEN["next"]:
                    GSEEN["next"] = now + 5
                    try:
                        gexe = gamecheck.game_process()
                    except Exception:
                        gexe = None
                    if gexe is None:
                        GSEEN.update(since=None, diag=None)
                    else:
                        GSEEN["since"] = GSEEN["since"] or now
                        GSEEN["dir"] = gamecheck.game_dir(gexe) or GSEEN["dir"]
                        if game._p or gamecheck.mapping_error() == 0:
                            # telemetry is there: main menu / loading / SDK dialog — not a problem
                            if tray and GSEEN["diag"] != "menu":
                                tray.set_state(st, "игра в меню или загружается")
                            GSEEN["diag"] = "menu"
                        elif GSEEN["diag"] == "menu":
                            GSEEN["diag"] = None
                        # 60 s: at start the game waits for OK in its SDK dialog, the plugin loads only after it
                        if now - GSEEN["since"] > 60 and not GSEEN["diag"]:
                            code, text = gamecheck.diagnose(GSEEN["dir"])
                            GSEEN["diag"] = code
                            if code == "menu":
                                continue
                            log(f"игра запущена ({gexe or 'путь скрыт'}), но телеметрии нет: {code}")
                            try:
                                log(f"  подробности: {gamecheck.details()}")
                            except Exception as e:
                                log(f"  подробности не собрались: {e!r}")
                            if tray:
                                tray.set_state(st, {"admin": "игра от администратора — не видна",
                                                    "no_plugin": "в игре нет плагина",
                                                    "not_loaded": "игра не загрузила плагин",
                                                    "no_vc": "плагину не хватает Visual C++",
                                                    "load_error": "ошибка загрузки плагина",
                                                    "blocked": "Windows не пускает к данным игры"}.get(code, "игра не видна"))
                            hint("game_diag", text)
            elif GSEEN["diag"]:
                GSEEN.update(since=None, diag=None)
            if st != prev:
                log({"no_game": "игры нет", "paused": "пауза/меню", "engine_off": "мотор выключен",
                     "driving": "едем"}[st])
                prev = st
                if tray:
                    tray.set_state(st, {"no_game": "игра в меню или загружается" if GSEEN["diag"] == "menu" or game._p
                                        else "жду игру", "paused": "пауза", "engine_off": "мотор выключен",
                                        "driving": "едем"}[st])
            if upd_ok_at and time.monotonic() > upd_ok_at:
                upd_ok_at = 0
                if upd:
                    upd.mark_ok()
            if TRAY_STATE.get("quit") or QUIT_REQ["why"]:
                log("выход " + (QUIT_REQ["why"] or "из меню значка"))
                try:
                    if world:
                        world.save()
                finally:
                    if tray:
                        tray.stop()
                    os._exit(0)                  # PTT / ears threads must not keep a windowless process alive
            if tray:
                tray.set_state(st, inside=sorted(world.inside) if world else [])
            if BONDS and world:
                BONDS.set_world(world.game_min, world.is_night(world.game_min), game.wipers())
            if OVERLAY and world:
                ins = [k for k in world.inside if not deck.offline(k)]   # offended / signed off: gone from the list
                OVERLAY.inside(ins, {k: BONDS.chip(k) for k in ins} if BONDS else None)
            if MEET_REQ["keys"] and world and world.px is not None:
                want = MEET_REQ["keys"].pop(0)
                k = world.summon(None if want == "*" else want)
                log(f"проверка: позван в зону {k or '(никто: не на смене или нет позиции)'}")
            # the living highway moves on while the game runs
            if world and st in ("driving", "engine_off"):
                w_acc += dt
                if w_acc >= 1.0:
                    p_ = game.pos()
                    if p_:
                        if time.monotonic() >= job_t:          # your job: where the navigator takes you
                            job_t = time.monotonic() + 10
                            if world.set_job(fines.dest() or None):
                                if world.dest:
                                    world._update_path(0)
                                    km = (world.path_ahead()[-1][0] / 1000) if world.ppath else 0
                                    log(f"заказ: в {world.cities[world.dest][0]}, путь по нашей карте "
                                        f"{len(world.ppath)} городов (~{km:.0f} км мира)")
                                else:
                                    log("заказа нет: свободная езда")
                        if world.company:
                            world.company.poll()
                            if world.company.cities and not getattr(world, "restricted", False):
                                n0 = len(world.cities)
                                if world.restrict_to(world.company.cities):
                                    log(f"карта игрока: {len(world.cities)} городов из {n0} (нет части DLC)")
                            for k, h, dist in world.hired_near(w_acc):
                                if k not in hired_seen:
                                    hired_seen.add(k)
                                    log(f"твой водитель рядом ({dist / 1000:.1f} км): {k} из гаража {h['hometown']}, "
                                        f"{h['src']} -> {h['dst']}, груз {h['cargo'] or 'порожняк'}")
                                    now_ = time.monotonic()
                                    hq.append((now_ + random.uniform(5, 25), k, "loaded" if h.get("cargo") else "empty",
                                               now_))
                            # deliveries of your hired drivers -> a voice message from the accountant
                            if world.company.deliveries:
                                deliv_pending += world.company.deliveries
                                world.company.deliveries.clear()
                            if deliv_pending and time.monotonic() - last_deliv > 1500:
                                big = max(int(x.get("revenue") or 0) for x in deliv_pending) >= 100000
                                kind = "delivery_big" if big else ("delivery_many" if len(deliv_pending) > 1 else "delivery")
                                if reaction_pool("buh", kind):
                                    buh_q.append((time.monotonic() + random.uniform(60, 180), kind))
                                    # 1.33 (Игорь): одинаковые голосовые подряд не копятся — дедуп по kind
                                    seen_k, ded = set(), []
                                    for q in sorted(buh_q, key=lambda q: q[0]):
                                        if q[1] not in seen_k:
                                            seen_k.add(q[1]); ded.append(q)
                                    buh_q[:] = ded
                                    buh_q.sort(key=lambda q: q[0])
                                log(f"доставки твоих водителей: {len(deliv_pending)} -> бухгалтерия: {kind}")
                                deliv_pending, last_deliv = [], time.monotonic()
                        ev = world.update(p_[0], p_[1], w_acc, p_[2])
                        if ev:
                            log(f"трасса: {ev[0]} едет {ev[1]}, встреча у {ev[2]}")
                        if world.teleport_event:
                            world.teleport_event = False
                            log(f"телепорт: скачок на другой конец карты; зона очищена, "
                                f"{len(world.teleport_witness)} водителей остались на старом месте")
                        for k in world.entered:
                            place = world.place_of(k)
                            log(f"в зоне рации: {k}" + (f" (у {place[0]})" if place else ""))
                            deck.prefer.add(k)
                            next_at = min(next_at, driving_s + random.uniform(8, 30))
                        # somebody came into range: a short crackle on the channel - you can call him now
                        cues = snd_glob(FX, "enter_*.wav")
                        if (world.entered and cues and cfg.get("enter_cue", True) and st == "driving"
                                and not ptt.down and not op.pending and not op.waiting):
                            PLAYER.file(random.choice(cues))
                        for k in world.entered:
                            now_ = time.monotonic()
                            lv = BONDS.level(k) if BONDS else 1
                            if world.met_before(k):
                                bond_add(k, 1, "встреча на трассе")
                            if world.met_before(k) and line_of("world", "meet_again", k):
                                wq.append(("world", "meet_again", k, now_))     # "опять пересеклись!"
                                deck.on_air.add(k)
                                deck.prefer.discard(k)
                            kn = world.knowledge(k)                          # he comes from where you go
                            if kn in ("camera", "police") and line_of("world", "warn_" + kn, k):
                                wq.append(("world", "warn_" + kn, k, now_))
                            # он видел, как ты исчез с трассы (телепорт): реплика «куда ты пропал?».
                            # Только знакомый (lv1+) — на личный тон незнакомца не пускаем; witness живёт
                            # до встречи на lv1+. Пул reactions/teleport/<actor> — реплики Летописца.
                            elif (k in world.teleport_witness
                                  and (not BONDS or BONDS.level(k) >= 1)
                                  and line_of("teleport", k)):
                                wq.append(("teleport", k, k, now_))
                            # friends come on air by themselves more often (road ahead, weather); strangers less
                            elif (kn == "clear" and random.random() < (0.15, 0.3, 0.5, 0.75)[lv]
                                  and line_of("world", "clear", k)):
                                wq.append(("world", "clear", k, now_))
                            if random.random() < (0.15, 0.3, 0.45, 0.6)[lv]:
                                wk = weather_kind(game, world)
                                if line_of("weather", wk, k):
                                    wq.append(("weather", wk, k, now_))
                            # 1.33 холодный старт: незнакомец выходит в эфир как незнакомец —
                            # first_air вместо личного приветствия (lv0, первая встреча)
                            if (BONDS and BONDS.level(k) == 0 and not world.met.get(k, {}).get("count")
                                    and reaction_pool("first_air", k)):
                                pick = line_of("first_air", k)
                                if pick:
                                    log(f"эфир: {k} — first_air (холодный старт)")
                                    PLAYER.file(pick[1], k)
                                    deck.on_air.add(k)
                                    next_at = max(next_at, driving_s + random.uniform(15, 30))
                                    continue
                            # 1.33 Исландия (DLC 10.11): первые недели — реакции на новое DLC,
                            # раз за сессию на водителя (окно до 2026-12-08, потом выключить вручную)
                            if (time.time() < 1765152000 and k not in DLC_PLAYED
                                    and random.random() < 0.3 and line_of("world", "dlc_iceland", k)):
                                DLC_PLAYED.add(k)
                                wq.append(("world", "dlc_iceland", k, now_))
                            # 1.33 арка Витьки: ступени свадьбы по встречам, не чаще одной за сессию
                            if k == "vitek" and reaction_pool("quest", "vityok_wedding"):
                                st_q = quest_state().get("vityok_wedding", 0)
                                if st_q < 8:
                                    quest_save({"vityok_wedding": st_q + 1})
                                    if st_q + 1 >= 8:
                                        VITYOK_WEDDING_DONE[0] = True
                                        log("арка Витьки закрыта: свадьба состоялась, паничные реплики уходят из эфира")
                                    wq.append(("quest", "vityok_wedding", k, now_, st_q))
                                elif (VITYOK_WEDDING_DONE[0] and BONDS and BONDS.mood(k) == "calm"
                                      and random.random() < 0.3 and line_of("calm_vityok", "calm")):
                                    # после свадьбы спокойный Витёк выходит в эфир чаще
                                    wq.append(("calm_vityok", "calm", k, now_))
                        for k in world.left:
                            log(f"ушёл из зоны: {k}")
                            deck.on_air.discard(k)          # next time he comes he says hello again
                            deck.prefer.discard(k)
                            # he talked in this meeting: "…пропадаешь…" through the noise as he goes
                            pk = line_of("world", "leave", k)
                            if (k in PLAYER.spoke and pk and random.random() < 0.8 and st == "driving"
                                    and not ptt.down and not op.pending and not op.waiting):
                                log(f"  {k} пропадает")
                                PLAYER.file(pk[1], k)
                            PLAYER.spoke.discard(k)
                        deck.allowed = set(world.inside)
                        deck.allowed_far = set(world.far())
                        # your fines: cameras go onto the "people's map", police posts for a while
                        off = fines.poll()
                        if off:
                            h = world.add_fine(off, p_[0], p_[1])
                            log(f"штраф: {off} -> на карту: {h['kind']}")
                            # the accountant finds out and records a voice message
                            day = int(p_[2] // 1440)
                            fines_day[day] = fines_day.get(day, 0) + 1
                            kind = BUH_KIND.get(off, "generic")
                            if fines_day[day] >= 3 and random.random() < 0.7:
                                kind = "escalation"
                            buh_q.append((time.monotonic() + random.uniform(40, 150), kind))
                            seen_k, ded = set(), []
                            for q in sorted(buh_q, key=lambda q: q[0]):
                                if q[1] not in seen_k:
                                    seen_k.add(q[1]); ded.append(q)
                            buh_q[:] = ded
                    w_acc = 0.0
                if time.monotonic() - w_saved > 60:
                    world.save()
                    w_saved = time.monotonic()
            # your own transmissions: answered while driving or parked with the game running
            while ptt.presses:
                dur, interrupted, cut, job = ptt.presses.pop(0)
                if st in ("driving", "engine_off"):
                    op.press(dur, interrupted, cut, job)
                elif st == "no_game":
                    hint("no_game", "Рация не видит игру, поэтому не отвечает. Если игра запущена — через минуту "
                                    "рация подскажет причину (она же в меню значка).")
                else:
                    log("тангента на паузе — не отвечаю")
            if ptt.down:
                op.pending = None            # nobody talks over you
                op.waiting = None
                continue
            if op.waiting:
                op.poll_ears()               # your words are being recognised
                continue
            if op.due():
                if st == "driving":
                    op.answer()
                elif st == "engine_off":
                    PLAYER.game = None       # parked with engine off: still answer you
                    op.answer()
                    PLAYER.game = game
                else:
                    op.pending = None        # paused / no game: the answer is lost
                next_at = max(next_at, driving_s + 40)   # no chatter right on top of the answer
                continue
            # the accountant's voice message (phone, not CB): plays while the game runs, after the delay
            # переходы дружбы вслух (2026-11-08): уровень вырос — актёр говорит свою фразу перехода (bond/upN)
            if BOND_UP and st in ("driving", "engine_off") and not op.pending:
                now_ = time.monotonic()
                BOND_UP[:] = [q for q in BOND_UP if now_ - q[1] < 900]
                if world is not None:
                    BOND_UP[:] = [q for q in BOND_UP if q[2] in world.inside]
                i_ = next((i for i, q in enumerate(BOND_UP) if q[0] <= now_), None)
                if i_ is not None:
                    _, _, a_, lv_ = BOND_UP.pop(i_)
                    pick = line_of("bond", f"up{lv_}", a_)
                    if pick:
                        log(f"эфир: {a_} — переход дружбы (up{lv_})")
                        PLAYER.file(pick[1], a_)
                        deck.on_air.add(a_)
                        next_at = max(next_at, driving_s + random.uniform(15, 30))
                    continue
            # 1.33 маркеры настроения вслух: смена настроения слышна (reactions/mood_mark/<mood>)
            if MARK_Q and st in ("driving", "engine_off") and not op.pending:
                a_, mood_ = MARK_Q.pop(0)
                mk = line_of("mood_mark", mood_, a_) if BONDS else None
                if mk and (world is None or a_ in world.inside):
                    log(f"эфир: маркер настроения {mood_} ({a_})")
                    PLAYER.file(mk[1], a_)
                    deck.on_air.add(a_)
                    next_at = max(next_at, driving_s + random.uniform(12, 25))
                    continue
            # 1.33 мемы: редкая болтовня (низкий эффективный вес 0.3–0.4, заменяемый пул)
            if (random.random() < 0.05 and st == "driving" and not op.pending
                    and world and world.inside):
                mk = None
                for _ in range(3):
                    a_ = random.choice(sorted(world.inside))
                    mk = line_of("memes", a_)
                    if mk:
                        break
                if mk:
                    log(f"эфир: мем ({mk[0]})")
                    PLAYER.file(mk[1], mk[0])
                    deck.on_air.add(mk[0])
                    next_at = max(next_at, driving_s + random.uniform(20, 40))
                    continue
            if buh_q and st in ("driving", "engine_off") and not op.pending and time.monotonic() >= buh_q[0][0]:
                _, kind = buh_q.pop(0)
                pool = reaction_pool("buh", kind) or reaction_pool("buh", "generic")
                if pool:
                    actor, wav = random.choice(fresh_first(pool))
                    heard(wav)
                    log(f"голосовое от бухгалтерии: {kind}")
                    ping = snd(FX / "phone_ping.wav")
                    if ping.exists():
                        PLAYER.file(ping)
                        PLAYER.idle(0.6)
                    PLAYER.file(wav)
                    next_at = max(next_at, driving_s + 30)
                continue
            if st != "driving" or op.pending:
                continue
            driving_s += dt
            # your hired driver passing by: one line, his own voice (tied to his id), not more than 1 per 8 min
            if hq:
                now_ = time.monotonic()
                hq = [q for q in hq if now_ - q[3] < 300]
                if hq and now_ >= hq[0][0] and now_ - last_hired > 480:
                    _, k_, kind_, _ = hq.pop(0)
                    voices = sorted({a for a, _ in reaction_pool("hired", kind_)})
                    if voices:
                        a_ = voices[int(hashlib.md5(k_.encode()).hexdigest(), 16) % len(voices)]
                        pick = line_of("hired", kind_, a_)
                        if pick:
                            log(f"эфир: твой водитель {k_} ({a_}, {kind_})")
                            PLAYER.file(pick[1], a_)
                            last_hired = now_
                            next_at = max(next_at, driving_s + random.uniform(20, 40))
                            continue
            # living highway lines first: "опять пересеклись", warnings, weather (after his hello)
            if wq:
                now_ = time.monotonic()
                wq = [q for q in wq if now_ - q[3] < 180 and world and q[2] in world.inside]
                ready = next((q for q in wq if q[1] in ("meet_again", "teleport", "vityok_wedding", "dlc_iceland",
                                                       "calm_vityok") or q[2] in deck.on_air), None)
                if ready and driving_s > 4:
                    wq.remove(ready)
                    g_, k_, a_, _ = ready[:4]
                    if g_ == "quest":
                        # свадебная арка: ступени строго по порядку (5-й элемент — индекс ступени)
                        pool = reaction_pool("quest", k_)
                        idx = min(ready[4] if len(ready) > 4 else 0, len(pool) - 1)
                        pick = pool[idx] if pool else None
                    else:
                        pick = line_of(g_, k_, a_)
                    if pick:
                        log(f"эфир: {g_}/{k_} ({a_})")
                        PLAYER.file(pick[1], a_)
                        deck.spoken[a_] = deck.spoken.get(a_, 0) + 1
                        if world and g_ == "teleport":
                            world.teleport_witness.pop(a_, None)     # отыграли «ты исчез с трассы»
                    next_at = max(next_at, driving_s + random.uniform(20, 45))
                    continue
            # silence guard: driving and nothing with a voice for max_silence -> pull somebody in
            if PLAYER.voices != seen_voices:
                seen_voices, quiet_drive = PLAYER.voices, 0.0
            quiet_drive += dt
            if quiet_drive > max_silence:
                quiet_drive = max_silence - 75                   # look again in 75 s
                if world and world.inside:
                    log("сторож тишины: в зоне есть люди — пусть говорят")
                    next_at = min(next_at, driving_s)
                else:
                    log("сторож тишины: никого рядом — зову встречного, пока эфир иностранцу")
                    if world:
                        world.quiet = world.quiet_s + 1          # a meeting on the next world step
                    foreign_acc = next_foreign                   # and something on air right now
            # a foreign driver passing by: one line in the language of the country you drive in
            if world and FOREIGN:
                foreign_acc += dt
                if foreign_acc >= next_foreign:
                    foreign_acc, next_foreign = 0.0, random.uniform(240, 600)
                    country = world.cities[world.roads.nearest(world.px, world.pz)][1] if world.px is not None else ""
                    lang = COUNTRY_LANG.get(country)
                    if not lang or random.random() < 0.3:          # an international truck from elsewhere
                        lang = random.choice(sorted(FOREIGN))
                    pool = reaction_pool("foreign", lang)
                    if pool:
                        actor, wav = random.choice(fresh_first(pool))
                        heard(wav)
                        x, sr = sf.read(wav, dtype="float32")
                        tmp = ROOT / "_foreign.wav"
                        sf.write(tmp, degrade(x, sr, random.uniform(0.6, 1.2)), sr)
                        log(f"эфир: проезжий иностранец ({lang}, вы в стране {COUNTRY_RU.get(country, country or 'неизвестной')})")
                        if OVERLAY:
                            OVERLAY.foreign({"de": "по-немецки", "pl": "по-польски", "fr": "по-французски",
                                             "es": "по-испански", "it": "по-итальянски", "nl": "по-голландски",
                                             "cs": "по-чешски"}.get(lang, "не по-нашему"))
                        PLAYER.file(tmp)
                        FOREIGN_LAST[:] = [lang, time.monotonic(), 0]
                        next_at = max(next_at, driving_s + 15)
                        continue
            # far-away chatter near a big city when nobody is in range
            if world and not world.inside:
                murmur_acc += dt
                if murmur_acc >= next_murmur and world.near_big_city():
                    play_murmur(world)
                    murmur_acc, next_murmur = 0.0, random.uniform(90, 200)
            if driving_s >= next_at:
                # 2026-11-06: two or more near you — now and then one asks the channel, another answers
                if random.random() < ASK_P and air_ask(deck):
                    driving_s = 0.0
                    next_at = random.uniform(cfg["gap_min_s"], cfg["gap_max_s"])
                    if next_k is not None:
                        next_k = random.uniform(*kgap)
                    continue
                p = deck.draw()
                if not p:                                # nobody in range (or nothing allowed): try later
                    next_at = driving_s + 20
                    continue
                log(f"эфир: {p}")
                r = PLAYER.item(p)
                if r == "paused":
                    log("  прервано (пауза)")
                elif r == "ok" and deck.is_greeting(p):
                    greet_reply(deck, cfg, p.split("/")[0])
                driving_s = 0.0
                next_at = random.uniform(cfg["gap_min_s"], cfg["gap_max_s"])
                if next_k is not None:  # timers count driving seconds since the last phrase
                    next_k = random.uniform(*kgap)
            elif next_k is not None and driving_s >= next_k and next_at - driving_s > 20:
                PLAYER.file(random.choice(fx))
                next_k = driving_s + random.uniform(*kgap)
        except Exception as e:  # never let one bad moment kill the radio
            log(f"ошибка: {e!r}")
            time.sleep(1)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        pass
    except Exception:                         # windowless exe: a startup error must not vanish silently
        import traceback
        tb = traceback.format_exc()
        try:
            with open(ROOT / "crash.log", "a", encoding="utf-8") as f:
                f.write(f"\n{datetime.now():%Y-%m-%d %H:%M:%S}\n{tb}")
        except OSError:
            pass
        if sys.stdout is None:
            ctypes.windll.user32.MessageBoxW(None, "«Канал 15» не запустился:\n\n" + tb.strip().splitlines()[-1] +
                                             f"\n\nПодробности: {ROOT / 'crash.log'}", "Канал 15", 0x10 | 0x40000)
        else:
            raise
