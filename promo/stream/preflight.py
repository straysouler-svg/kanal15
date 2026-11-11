"""Предстрим-проверка «Канала 15» (2026-11-10): одна команда перед «Начать трансляцию».
Причина появления: стрим 10.11 ушёл весь без голоса — AuxAudioDevice1 был muted в микшере OBS.
С 11.11 микрофон — сценовый («Микрофон (В пути)» / «Микрофон (Верт: В пути)»),
глобальный «Микр/доп» заглушён намеренно: голос звучит только в сценах дороги.
Проверяет: рацию, телеметрию, микрофон (в Windows, в рации, в OBS — сцены, мьют, живость id),
профиль/коллекцию OBS. Запуск: venv\\Scripts\\python.exe promo/stream/preflight.py
"""
import ctypes
import ctypes.wintypes as w
import json
import socket
import struct
import sys
import urllib.request
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OBS_DIR = Path.home() / "AppData" / "Roaming" / "obs-studio"
OK, BAD = "  OK ", "FAIL "

fails = []


def check(name, fn):
    try:
        msg, good = fn()
    except Exception as e:
        msg, good = f"ошибка проверки: {e}", False
    print((OK if good else BAD) + f"{name}: {msg}")
    if not good:
        fails.append(name)


def radio():
    for port in (47819, 47823):
        s = socket.create_connection(("127.0.0.1", port), timeout=2)
        s.close()
    st = json.load(urllib.request.urlopen("http://127.0.0.1:47823/state", timeout=3))
    return f"жива, оверлей отвечает (порт 47823, строк в ленте {len(st.get('lines', []))})", True


def telemetry():
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenFileMappingW.restype = ctypes.c_void_p
    k.MapViewOfFile.restype = ctypes.c_void_p
    k.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]
    h = k.OpenFileMappingW(4, False, r"Local\SimTelemetryETS2")
    if not h:
        return "игра/телеметрия не найдены — запусти ETS2", False
    p = k.MapViewOfFile(h, 4, 0, 0, 0)
    b = ctypes.string_at(p, 600)
    k.UnmapViewOfFile(ctypes.c_void_p(p))
    paused = struct.unpack_from("<I", b, 4)[0]
    x, y, z = struct.unpack_from("<3f", b, 40)
    return f"игра на связи ({'пауза' if paused else 'едем'}, позиция {x:.0f},{z:.0f})", True


def capture_devices():
    """guid -> (name, alive) всех устройств захвата Windows."""
    out = {}
    root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                          r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture")
    for i in range(winreg.QueryInfoKey(root)[0]):
        guid = winreg.EnumKey(root, i)
        try:
            props = winreg.OpenKey(root, guid + r"\Properties")
            vals = []
            j = 0
            while True:
                try:
                    _, v, t = winreg.EnumValue(props, j)
                    if isinstance(v, str) and v.strip():
                        vals.append(v)
                    j += 1
                except OSError:
                    break
            state = winreg.QueryValueEx(winreg.OpenKey(root, guid), "DeviceState")[0]
            out[guid.lower()] = (" ".join(vals), state == 1)
        except OSError:
            pass
    return out


def mic_windows():
    devs = capture_devices()
    alive = [(g, n) for g, (n, a) in devs.items() if a and "fifine" in n.lower()]
    if not alive:
        return "fifine не найден среди живых устройств захвата! (переткни USB)", False
    return f"fifine жив ({alive[0][0][:13]}...)", True


def mic_radio():
    cfg = json.loads((ROOT / "cb-radio" / "config.json").read_text(encoding="utf-8"))
    dev = (cfg.get("mic") or {}).get("device", "")
    enabled = (cfg.get("mic") or {}).get("enabled", False)
    if not enabled or not dev:
        return f"в рации микрофон не настроен (enabled={enabled}, device={dev!r})", False
    return f"в рации выбран «{dev}»", True


def obs():
    ui = (OBS_DIR / "user.ini").read_text(encoding="utf-8", errors="replace")
    prof = next((l.split("=", 1)[1] for l in ui.splitlines() if l.startswith("Profile=")), "?")
    coll = next((l.split("=", 1)[1] for l in ui.splitlines() if l.startswith("SceneCollectionFile=")), "?")
    if coll != "Канал_15.json":
        return f"активная коллекция «{coll}», а надо «Канал_15.json» (профиль «{prof}»)", False
    col = json.loads((OBS_DIR / "basic" / "scenes" / coll).read_text(encoding="utf-8"))
    devs = capture_devices()

    def dev_dead(m):
        did = (m.get("settings") or {}).get("device_id", "")
        guid = did.split(".")[-1].strip("{}").lower() if did else ""
        return guid and guid in devs and not devs[guid][1]

    problems = []
    # Глобальные каналы (Desktop/Aux): проверяем только живость устройства.
    # «Микр/доп» с 11.11 намеренно замьючен — микрофон перенесён в сцены (см. ниже).
    for k in col:
        if not k.startswith(("AuxAudio", "DesktopAudio")) or not isinstance(col[k], dict):
            continue
        m = col[k]
        if dev_dead(m):
            problems.append(f"{m.get('name', k)}: устройство мертво (переткнуто?)")
    # Сценовые микрофоны: должны стоять в сценах «В пути», быть живы и не замьючены —
    # именно так голос звучит только в дороге и не льётся на заставки.
    srcs = {s.get("name"): s for s in col.get("sources", [])}
    scenes = {s.get("name"): s for s in col.get("sources", [])
              if "items" in (s.get("settings") or {})}
    for scene_name, mic_name in (("В пути", "Микрофон (В пути)"),
                                 ("Верт: В пути", "Микрофон (Верт: В пути)")):
        sc = scenes.get(scene_name)
        names = [i.get("name") for i in (sc["settings"]["items"] if sc else [])]
        if mic_name not in names:
            problems.append(f"в сцене «{scene_name}» нет «{mic_name}»")
            continue
        m = srcs.get(mic_name) or {}
        if m.get("muted"):
            problems.append(f"{mic_name}: ЗАМЬЮЧЕН в микшере")
        if m.get("volume", 1.0) < 0.05:
            problems.append(f"{mic_name}: громкость ~0")
        if dev_dead(m):
            problems.append(f"{mic_name}: устройство мертво (переткнуто?)")
    if problems:
        return "; ".join(problems), False
    return (f"профиль «{prof}», коллекция «Канал 15», микрофон сценовый "
            f"(только «В пути»), аудиоканалы живы", True)


def obs_running():
    import subprocess
    out = subprocess.run(["tasklist", "/fi", "imagename eq obs64.exe"], capture_output=True, text=True).stdout
    if "obs64.exe" not in out:
        return "OBS не запущен", False
    return "OBS запущен", True


print("=== Предстрим-проверка «Канала 15» ===")
check("Рация", radio)
check("Телеметрия", telemetry)
check("Микрофон Windows", mic_windows)
check("Микрофон в рации", mic_radio)
check("OBS", obs_running)
check("OBS аудио/коллекция", obs)
print("=== " + ("ВСЁ ЧИСТО — можно в эфир (сцена «Скоро начнём», потом «В пути»)"
               if not fails else f"СТОП: исправь {len(fails)} пункт(а) выше") + " ===")
sys.exit(1 if fails else 0)
