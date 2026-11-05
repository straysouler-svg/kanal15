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
import socket  # noqa: E402
import struct  # noqa: E402
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


def log(msg):
    line = f"{datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


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
            h = _k.OpenFileMappingW(4, False, "Local\\SHSCSTelemetry")
            if not h:
                return None
            self._p = _k.MapViewOfFile(h, 4, 0, 0, 0)
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


class PTT:
    """Push-to-talk = one wheel button. Read straight from Windows (winmm joyGetPosEx, only that one device,
    buttons 0-31): ~1.5 % of a core. pygame/SDL opened all 5 controllers with its own thread and cost 7-20 %
    (measured 2026-11-03) - it stays only as a fallback (button >= 32, winmm can't see the device, or
    "backend": "pygame" in config ptt). Survives the wheel reconnecting (Pit House re-plugs the R5 base
    when a game starts)."""
    RESCAN_S = 2.0

    def __init__(self, cfg):
        c = cfg.get("ptt") or {}
        self.dev, self.btn = str(c.get("device", "")).lower(), c.get("button")
        self.down, self.t_down, self.presses = False, 0.0, []
        self.was_playing, self.cut = False, None
        self.ears = None         # set in main(): microphone + speech recognition
        self.js = {}
        self.ok = False
        self.backend, self.jid, self._next_scan, self._names = None, None, 0.0, None
        self._last_cfg = -1e9
        # your own key-up / key-release sounds ("ptt_sounds" in config.json)
        s = cfg.get("ptt_sounds") or {}
        self.snd = {}
        for edge, kind in (("press", s.get("press")), ("release", s.get("release"))):
            f = snd(FX / f"ptt_{edge}_{kind}.wav") if kind else None
            if f and f.exists():
                data, sr = sf.read(f, dtype="float32")
                self.snd[edge] = (data * float(s.get("volume", 0.5)) * float(cfg.get("volume", 0.8)), sr)
        self.device = cfg.get("device")
        if self.btn is None:
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

    CFG_CHANGED_S = 15.0     # joyConfigChanged not more often than this

    def _scan_winmm(self):
        # winmm caches the device list: joyConfigChanged re-reads it after a replug. 2026-11-05: the radio died
        # with heap corruption 0xc0000374 INSIDE this call (crash.log 10:46, also 2026-11-04 16:45) right after all
        # USB devices dropped for a second — it was called every 2 s while re-enumerating. Now: rarely, not at once.
        now = time.monotonic()
        if now - self._last_cfg >= self.CFG_CHANGED_S:
            self._last_cfg = now
            self.mm.joyConfigChanged(0)
        self.jid, names, found = None, [], None
        for i in range(16):
            caps = _JOYCAPSW()
            if self.mm.joyGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) != 0:
                continue
            name = _oem_name(caps.wMid, caps.wPid) or f"{caps.wMid:04X}:{caps.wPid:04X}"
            names.append(name)
            if self.jid is None and self.dev and self.dev in name.lower() \
                    and self.mm.joyGetPosEx(i, ctypes.byref(self.ji)) == 0:
                self.jid, found = i, name
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
        if not self.ok:
            return
        try:
            if self.backend == "winmm":
                if self.jid is None:
                    if time.monotonic() >= self._next_scan:
                        self._scan_winmm()
                    if self.jid is None:
                        return
                if self.mm.joyGetPosEx(self.jid, ctypes.byref(self.ji)) != 0:   # unplugged / re-plugged
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
BUH_KIND = {"speeding": "speeding", "speeding_camera": "speeding", "red_signal": "red_signal", "crash": "crash",
            "no_lights": "no_lights", "avoid_sleeping": "avoid_sleeping", "wrong_way": "wrong_way"}
COUNTRY_LANG = {"germany": "de", "austria": "de", "switzerland": "de", "poland": "pl", "france": "fr",
                "belgium": "fr", "luxembourg": "fr", "spain": "es", "italy": "it", "netherlands": "nl",
                "czech": "cs", "slovakia": "cs"}


def fresh_first(cands):
    """From (actor, wav) candidates keep the ones not heard lately (if any are left)."""
    new = [c for c in cands if str(c[1]) not in RECENT]
    return new or cands


def heard(wav):
    RECENT.append(str(wav))


_POOL_FILES = {}


def reaction_pool(group, kind):
    """[(actor, wav path)] for audio/reactions/<group>/<kind>."""
    d = REACT / group / kind
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
        if cands:
            pos = {p: i for i, p in enumerate(left)}
            pick = min(cands, key=lambda p: (self.spoken.get(actors_of(p)[0], 0) / self.weights.get(actors_of(p)[0], 1.0),
                                             pos[p]))
        else:
            pick = next((p for p in left if self._ok(p, left_set, last_voice, False)), None)
        hist = [h for h in self.st.get("history", []) if h in have]
        if pick is None:
            # everything left in the deck is blocked right now (bye-phrases of absent actors,
            # scenes with someone off air): take an allowed item heard longest ago instead
            order = sorted(have, key=lambda p: hist.index(p) if p in hist else -1)
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
        for cand in ([x for x in ok if x[0] == prefer], [x for x in ok if x[0] in self.on_air], ok):
            if cand:
                pick = random.choice(fresh_first(cand))
                heard(pick[1])
                return pick
        return None


# ---------------------------------------------------------------- audio
def degrade(x, sr, d):
    """Signal by distance: d = distance / radio range. Near: as recorded. Towards the edge: more hiss,
    weaker voice, short drop-outs ("пропадаешь")."""
    if d is None or d < 0.55:
        return x
    k = min(2.0, (d - 0.55) / 0.45)              # 1 = edge of range, up to 2 = the far side of a talk
    y = x * max(0.3, 1.0 - 0.35 * k)
    noise = np.random.standard_normal(len(x)).astype(np.float32)
    noise = np.convolve(noise, np.ones(6, np.float32) / 6, mode="same")      # take the fizz off
    y = y + noise * (0.012 + 0.05 * k)
    for _ in range(int(k * 3 + random.random())):
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
            vol = 0.0 if TRAY_STATE.get("muted") else float(self.cfg["volume"])     # «Тишина в эфире» (tray)
            sd.play(data * vol, sr, device=self.cfg["device"])
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
                    self.last_info = f"тишина ({db:.0f} дБ) — микрофон молчит"
                    log(f"  микрофон «{self.dev_name}» молчит — выберите другой в меню значка (Микрофон)")
                    if self.on_silent:
                        self.on_silent(self.dev_name)
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
        intent, who = intents.understand(text) if text else (None, None)
        group = "player"
        about = None
        if who and self.deck.allowed is not None and who not in (self.deck.allowed | self.deck.allowed_far):
            # a name of somebody NOT in range: a question ABOUT him ("Сороку никто не видел?"), not to him -
            # those in range answer; with no recorded line on that, "не знаю / не видел"
            about, who = who, None
        question = intents.is_question(text) if text else False
        if intent == "repeat":
            group, kind = "special", "repeat"             # he says his last line again (or keeps quiet)
        elif interrupted and not intent and random.random() < 0.7:     # a clear question is answered anyway
            kind = "interrupt"
        elif heard and not text:
            kind = "not_heard" if random.random() < 0.7 else None      # pressed, but said nothing clear
        elif intent == "who":
            group, kind = "special", "who"                # roll call: everybody in range answers once
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
        if group == "intent" and who and kind not in ("thanks", "bye", "radio_check", "help", "repeat", "praise", "rude"):
            # step 2 of «вариативность» (2026-11-05): asked him the same within 10 min -> he notices
            last = self.asked.get((who, kind))
            self.asked[(who, kind)] = now
            if last and now - last < 600 and random.random() < 0.7 and any(x[0] == who for x in reaction_pool("player", "already")):
                group, kind = "player", "already"
        if who:
            prefer = who
        log(f"тангента: «{text}» -> {intent or '?'}{' для ' + who if who else ''}{' про ' + about if about else ''}"
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
                    self.deck.on_air.add(actor)
                    self.on_air = True
                    self._maybe_cross(actor, "intent")
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
            if not pool:
                # nobody near has a word on it (the ElevenLabs five have no weather lines until December):
                # somebody further out answers - same weather around, but you barely hear him
                far = [a for a in self.deck.allowed_far if not self.deck.offline(a)]
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
        done = 0
        for a in here:
            if self.rollcalled.get(a, 0) > now or self.deck.offline(a):
                continue
            pick = line_of("world", "rollcall", a) or line_of("player", "greet", a)
            if not pick:
                continue
            if done and not PLAYER.idle(random.uniform(0.6, 1.5)):
                break
            if PLAYER.file(pick[1], a) != "ok":
                break
            self.rollcalled[a] = time.monotonic() + random.uniform(120, 180)
            self.deck.on_air.add(a)
            done += 1
        log(f"перекличка: ответили {done}" + ("" if done else " (никого в зоне или все уже отвечали)"))
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

    def answer(self):
        _, group, kind, prefer, who = self.pending
        self.pending = None
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
                    self.deck.on_air.add(actor)
                    self.on_air = True
                    self._maybe_cross(actor, group)
                return
        if group == "intent" and kind in ("police", "road") and reaction_pool("intent", kind + "_unknown"):
            kind += "_unknown"       # nobody near could have seen it: an honest «не видел, я в ту же сторону»
        if not who and kind != "interrupt" and random.random() > 0.6:
            prefer = None                # not always the same person answering
        pool = reaction_pool(group, kind)
        question = group == "intent" and kind not in ("thanks", "bye", "praise", "rude")
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
            for alt_kind in ("dunno", "not_heard"):
                pick = self.deck.choose(mine(reaction_pool("player", alt_kind)), prefer=who or prefer)
                if pick:
                    log(f"  на {group}/{kind} ответа нет — {alt_kind}")
                    break
        if not pick and self.deck.allowed is not None and self.deck.allowed_far:
            # nobody near has a line: somebody further out answers through the noise - better than dead air
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
    pick = random.choice(fresh_first(pool))
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
TRAY_MOD = None
BOT_URL = "https://t.me/kanal15_publisher_bot"


def make_report():
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
                zf.writestr(name, data)
        zf.writestr("about.json", json.dumps({"version": VERSION, "date": VERSION_DATE, "build": BUILD_NAME,
                                              "windows": platform.platform(), "created": datetime.now().isoformat()},
                                             ensure_ascii=False, indent=1))
    log(f"отчёт о проблеме собран: {z}")
    subprocess.Popen(["explorer", f"/select,{z}"])
    os.startfile(BOT_URL)
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
    global TRAY_STATE
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
    PLAYER.ptt = ptt if ptt.ok else None
    ears = Ears(cfg) if ptt.ok else None
    ptt.ears = ears if ears and ears.ok else None
    if ears:
        def on_silent(name):
            import mic
            hint("mic_silent", mic.privacy_blocked() or f"Рация не слышит микрофон «{name}» (полная тишина). "
                 "Правый клик по значку рации → Микрофон → выберите другой.")
        ears.on_silent = on_silent
        if tray:
            import mic as mic_mod

            def mic_set(name):
                if ears.open(name):
                    if not ears.ok:            # no microphone at start: the recogniser starts now
                        import threading
                        ears.ok = True
                        ears.want_model = threading.Event()
                        threading.Thread(target=ears._worker, args=((cfg.get("mic") or {}).get("model", "small"),),
                                         daemon=True).start()
                    ptt.ears = ears
                    op.ears = ears
                    cfg.setdefault("mic", {})["device"] = name
                    try:
                        cur = json.loads(CFG_FILE.read_text(encoding="utf-8-sig"))
                        cur.setdefault("mic", {})["device"] = name
                        CFG_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=4), encoding="utf-8")
                    except (OSError, ValueError) as e:
                        log(f"настройки не сохранились: {e!r}")
                    ears.last_info = "микрофон сменён — нажмите тангенту и скажите что-нибудь"
            tray.HOOKS.update(mics=lambda: [n for _, n in mic_mod.inputs(sd)], mic_now=lambda: ears.dev_name,
                              mic_info=lambda: ears.last_info, mic_set=mic_set)
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
            tray.HOOKS.update(report=lambda: (make_report(), tray.notify(
                "Журналы рации собраны в архив и показаны в папке. Перетащи этот файл в чат с ботом и коротко "
                "напиши, что случилось.")))
            tray.HOOKS.update(upd_status=lambda: upd.status, upd_check=upd_check, upd_auto=upd_auto,
                              upd_auto_on=lambda: upd.auto, upd_enabled=lambda: upd.enabled,
                              changelog=lambda: os.startfile(str(ROOT / "CHANGELOG.md")))
    except Exception as e:
        log(f"обновления не подключились: {e!r}")
    upd_ok_at = time.monotonic() + 20         # healthy for 20 s -> keep the update the launcher just applied
    air = apply_air(cfg, world, cfg.get("air", "normal"))
    log(f"эфир: {air['name']}")
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
        tray.HOOKS.update(air_levels=lambda: [(k, v["name"]) for k, v in AIR.items()],
                          air_now=lambda: cfg.get("air", "normal"), air_set=air_set)
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
                                    buh_q.sort(key=lambda q: q[0])
                                log(f"доставки твоих водителей: {len(deliv_pending)} -> бухгалтерия: {kind}")
                                deliv_pending, last_deliv = [], time.monotonic()
                        ev = world.update(p_[0], p_[1], w_acc, p_[2])
                        if ev:
                            log(f"трасса: {ev[0]} едет {ev[1]}, встреча у {ev[2]}")
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
                            if world.met_before(k) and line_of("world", "meet_again", k):
                                wq.append(("world", "meet_again", k, now_))     # "опять пересеклись!"
                                deck.on_air.add(k)
                                deck.prefer.discard(k)
                            kn = world.knowledge(k)                          # he comes from where you go
                            if kn in ("camera", "police") and line_of("world", "warn_" + kn, k):
                                wq.append(("world", "warn_" + kn, k, now_))
                            elif kn == "clear" and random.random() < 0.35 and line_of("world", "clear", k):
                                wq.append(("world", "clear", k, now_))
                            if random.random() < 0.3:
                                wk = weather_kind(game, world)
                                if line_of("weather", wk, k):
                                    wq.append(("weather", wk, k, now_))
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
                ready = next((q for q in wq if q[1] == "meet_again" or q[2] in deck.on_air), None)
                if ready and driving_s > 4:
                    wq.remove(ready)
                    g_, k_, a_, _ = ready
                    pick = line_of(g_, k_, a_)
                    if pick:
                        log(f"эфир: {g_}/{k_} ({a_})")
                        PLAYER.file(pick[1], a_)
                        deck.spoken[a_] = deck.spoken.get(a_, 0) + 1
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
                        log(f"эфир: проезжий иностранец ({lang}, вы в стране {country})")
                        PLAYER.file(tmp)
                        next_at = max(next_at, driving_s + 15)
                        continue
            # far-away chatter near a big city when nobody is in range
            if world and not world.inside:
                murmur_acc += dt
                if murmur_acc >= next_murmur and world.near_big_city():
                    play_murmur(world)
                    murmur_acc, next_murmur = 0.0, random.uniform(90, 200)
            if driving_s >= next_at:
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
