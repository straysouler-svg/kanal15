"""Почему рация «ждёт игру», когда игра запущена (2026-11-05, у Кирилла: «жду игру», хотя игра идёт).

Рация видит игру только через плагин телеметрии (общая память Local\\SimTelemetryETS2). Если её нет, а процесс
игры есть, причина одна из трёх, и мы её называем, а не гадаем:
  - плагина нет в bin\\win_x64\\plugins (шаг установщика пропущен / игру не нашли) -> можно поставить из меню значка;
  - плагин лежит, но игра его не загрузила (при запуске игры в окне про SDK нажали «нет») -> перезапустить игру;
  - игра запущена от администратора: память есть, но обычной программе доступ закрыт (код 5).
Только ctypes: никаких консольных программ (окно поверх игры ставит её на паузу)."""
import ctypes
import shutil
from ctypes import wintypes
from pathlib import Path

PLUGIN = "ets2-telemetry.dll"          # Funbit; creates Local\\SimTelemetryETS2 (1.00-1.05 shipped the wrong one)
WRONG_PLUGIN = "ETS2SharedMemoryMapPlugin64.dll"   # makes SCSTelemetryShared — not what the radio reads
# 1.26 (07.11, Kirill: fines happened, the accountant stayed silent): Funbit has no gameplay events. Fines and the job
# come from RenCloud scs-sdk-plugin (MIT, v1.12.1) -> Local\SCSTelemetry. SimHub ships the same plugin renamed
# (Local\SHSCSTelemetry), so until now only SimHub owners got fines.
EVENTS_PLUGIN = "scs-telemetry.dll"
VC_EVENTS = ("msvcp140.dll", "vcruntime140.dll")      # Visual C++ 2015-2022 x64, what scs-telemetry.dll imports
GAME_EXE = "eurotrucks2.exe"
_k = ctypes.WinDLL("kernel32", use_last_error=True)
_k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_k.OpenProcess.restype = wintypes.HANDLE
_k.OpenFileMappingW.restype = wintypes.HANDLE
_k.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_k.GetCurrentProcess.restype = wintypes.HANDLE
_a = ctypes.WinDLL("advapi32", use_last_error=True)
_k.CloseHandle.argtypes = [wintypes.HANDLE]
_k.LocalFree.argtypes = [ctypes.c_void_p]
_a.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
_a.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                   ctypes.POINTER(wintypes.DWORD)]
LAST_PID = None          # pid of the game found by game_process()


class _PE(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


def game_process():
    """-> Path of the running eurotrucks2.exe, Path("") if running but its path is hidden, or None."""
    snap = _k.CreateToolhelp32Snapshot(2, 0)              # TH32CS_SNAPPROCESS
    if not snap or snap == wintypes.HANDLE(-1).value:
        return None
    try:
        e = _PE()
        e.dwSize = ctypes.sizeof(e)
        ok = _k.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            if e.szExeFile.lower() == GAME_EXE:
                global LAST_PID
                LAST_PID = e.th32ProcessID
                h = _k.OpenProcess(0x1000, False, e.th32ProcessID)    # PROCESS_QUERY_LIMITED_INFORMATION
                if not h:
                    return Path("")
                try:
                    buf = ctypes.create_unicode_buffer(1024)
                    n = wintypes.DWORD(1024)
                    if _k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                        return Path(buf.value)
                    return Path("")
                finally:
                    _k.CloseHandle(h)
            ok = _k.Process32NextW(snap, ctypes.byref(e))
    finally:
        _k.CloseHandle(snap)
    return None


def game_dir(exe):
    """...\\Euro Truck Simulator 2\\bin\\win_x64\\eurotrucks2.exe -> ...\\Euro Truck Simulator 2"""
    try:
        return exe.parents[2] if exe and exe.name else None
    except IndexError:
        return None


def plugin_path(gdir):
    return Path(gdir) / "bin" / "win_x64" / "plugins" / PLUGIN


def token_info(pid=None):
    """Who a process runs as: {elevated, integrity, session, user, appcontainer} (pid None = this radio).
    2026-11-05, Kirill: the game.log says the plugin is initialized, yet the radio can't open its memory —
    the two processes must live in different «rooms»; this says which."""
    out = {}
    h = _k.GetCurrentProcess() if pid is None else _k.OpenProcess(0x1000, False, pid)
    if not h:
        return {"error": ctypes.get_last_error()}
    tok = wintypes.HANDLE()
    try:
        if not _a.OpenProcessToken(h, 8, ctypes.byref(tok)):              # TOKEN_QUERY
            return {"error": ctypes.get_last_error()}
        buf = ctypes.create_string_buffer(512)
        n = wintypes.DWORD()

        def info(cls):          # DWORD classes want the exact size (TokenElevation: ERROR_BAD_LENGTH otherwise)
            return _a.GetTokenInformation(tok, cls, buf, 4 if cls in (12, 20, 29) else 512, ctypes.byref(n))
        if info(20):                                                      # TokenElevation
            out["elevated"] = bool(ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0])
        if info(12):                                                      # TokenSessionId
            out["session"] = ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0]
        if info(29):                                                      # TokenIsAppContainer
            out["appcontainer"] = bool(ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0])
        if info(25):                                                      # TokenIntegrityLevel
            sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
            cnt = _a.GetSidSubAuthorityCount
            cnt.restype = ctypes.POINTER(ctypes.c_ubyte)
            sub = _a.GetSidSubAuthority
            sub.restype = ctypes.POINTER(wintypes.DWORD)
            out["integrity"] = hex(sub(ctypes.c_void_p(sid), cnt(ctypes.c_void_p(sid))[0] - 1)[0])
        if info(1):                                                       # TokenUser
            sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
            ps = wintypes.LPWSTR()
            if _a.ConvertSidToStringSidW(ctypes.c_void_p(sid), ctypes.byref(ps)):
                out["user"] = ps.value
                _k.LocalFree(ps)
    finally:
        if tok:
            _k.CloseHandle(tok)
        if pid is not None:
            _k.CloseHandle(h)
    return out


def mapping_probe():
    """Error code for every name the plugin's memory could have: {name: 0 | win32 error}."""
    out = {}
    for name in (r"Local\SimTelemetryETS2", r"Global\SimTelemetryETS2", "SimTelemetryETS2"):
        h = _k.OpenFileMappingW(4, False, name)
        out[name] = 0 if h else ctypes.get_last_error()
        if h:
            _k.CloseHandle(h)
    return out


def mapping_error():
    """Win32 error of opening the telemetry memory: 0 ok, 2 there is none, 5 access denied (game runs as admin)."""
    h = _k.OpenFileMappingW(4, False, "Local\\SimTelemetryETS2")
    if h:
        _k.CloseHandle(h)
        return 0
    return ctypes.get_last_error()


VC_DLLS = ("msvcr110.dll",)     # what ets2-telemetry.dll imports (Visual C++ 2012 x64)
VC_URL = "https://www.microsoft.com/download/details.aspx?id=30679 (vcredist_x64.exe)"


def vc_missing(gdir=None, names=VC_DLLS):
    """Runtime DLLs a plugin needs that Windows cannot find (System32, or next to eurotrucks2.exe)."""
    import os
    sys32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    here = Path(gdir) / "bin" / "win_x64" if gdir else None
    return [d for d in names if not (sys32 / d).exists() and not (here and (here / d).exists())]


def events_path(gdir):
    return Path(gdir) / "bin" / "win_x64" / "plugins" / EVENTS_PLUGIN


def events_missing(gdir):
    """The fines plugin (or its Visual C++) is not in this game."""
    return bool(gdir) and (not events_path(gdir).exists() or bool(vc_missing(gdir, VC_EVENTS)))


def game_log_plugin():
    """What the game wrote about loading our plugin last time (Documents\\Euro Truck Simulator 2\\game.log.txt):
    -> 'ok' | 'not_tried' | the error line | None (no log)."""
    import os
    docs = Path(os.path.expanduser("~")) / "Documents"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            docs = Path(os.path.expandvars(winreg.QueryValueEx(k, "Personal")[0]))
    except OSError:
        pass
    f = docs / "Euro Truck Simulator 2" / "game.log.txt"
    try:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    start = max((i for i, s in enumerate(lines) if "'ets2-telemetry'" in s and "loading" in s), default=None)
    if start is None:
        return "not_tried"
    for s in lines[start + 1:start + 40]:
        if "Memory telemetry example initialized" in s or "SimTelemetryETS2" in s:
            return "ok"
        if "ERROR" in s and ("ets2-telemetry" in s or "plugin" in s.lower()) and "[sdk]" not in s:
            return s.split(" : ", 1)[-1].strip()[:200]
    return "ok"             # ets2-telemetry.dll says nothing when it loads fine


def diagnose(gdir):
    """-> (code, text for the player). code: menu | admin | no_plugin | no_vc | load_error | not_loaded | unknown."""
    err = mapping_error()
    if err == 0:
        # the plugin works: the game is just in its main menu / loading (game time stands still there).
        # 1.03 called this «игра не загрузила плагин» — Kirill's game.log showed the plugin initialized fine.
        return "menu", ""
    if err == 5:
        if admin_flags():
            return "admin", ("Игра запущена от имени администратора, и Windows не пускает к ней рацию. Правый клик "
                             "по значку рации → «Снять с игры запуск от администратора», потом перезапустите игру.")
        return "admin", ("Игра запущена от имени администратора, и Windows не пускает к ней рацию. Запустите игру "
                         "обычным способом или правый клик по значку рации → «Перезапустить рацию с правами "
                         "администратора».")
    if gdir and not plugin_path(gdir).exists():
        return "no_plugin", ("В игре нет плагина телеметрии, поэтому рация её не видит. Правый клик по значку "
                             "рации → «Исправить плагин телеметрии», потом перезапустите игру.")
    if gdir:
        vc = vc_missing(gdir)
        if vc:
            return "no_vc", ("Плагину телеметрии не хватает Microsoft Visual C++ 2012 (x64): нет "
                             + ", ".join(vc) + ". Правый клик по значку рации → «Исправить плагин телеметрии» "
                             "(или установите Visual C++ с сайта Microsoft), потом перезапустите игру.")
        gl = game_log_plugin()
        if gl == "ok":
            # the game says the plugin works, we can't see it: different «rooms» (antivirus sandbox, other user,
            # different rights). Details go to the log (cb_radio.py logs details()).
            return "blocked", ("Игра загрузила плагин, но Windows не пускает рацию к его данным (код "
                               f"{err}). Частая причина — антивирус запускает рацию в «песочнице»: добавьте "
                               "CB-Radio.exe в исключения антивируса. Или рация и игра запущены с разными правами.")
        if gl == "not_tried":
            return "not_loaded", ("Игра даже не пробовала загрузить плагин. Перезапустите игру и в окне про "
                                  "SDK-плагины при запуске нажмите OK.")
        if gl and gl not in ("ok", "loaded_silent"):
            return "load_error", f"Игра не смогла загрузить плагин телеметрии: {gl}"
        return "not_loaded", ("Плагин телеметрии на месте, но игра его не загрузила. Перезапустите игру и в окне "
                              "про SDK-плагины при запуске нажмите OK.")
    return "unknown", "Игра запущена, но рация её не видит. Запустите установщик ещё раз и поставьте плагин телеметрии."


def needs_fix(gdir):
    return bool(gdir) and (not plugin_path(gdir).exists() or bool(vc_missing(gdir)) or events_missing(gdir))


def plugin_current(src, gdir):
    """The plugin in the game is exactly ours (and its Visual C++ is there)."""
    t = plugin_path(gdir)
    ev = Path(src).parent / EVENTS_PLUGIN
    try:
        main = t.exists() and t.read_bytes() == Path(src).read_bytes() and not vc_missing(gdir)
        if not ev.exists():
            return main
        return (main and events_path(gdir).exists() and events_path(gdir).read_bytes() == ev.read_bytes()
                and not vc_missing(gdir, VC_EVENTS))
    except OSError:
        return False


def fix(src, vc_dir, gdir):
    """Plugin into the game + (if Windows lacks it) MSVCR110.dll next to eurotrucks2.exe — app-local,
    no admin rights; the installer carries it in installer\\plugins\\vc. -> (ok, text)."""
    # 1.13: a protected game folder (C:\Program Files — many non-Steam copies) gets ONE administrator prompt
    pairs, msgs = [], []
    t = plugin_path(gdir)
    try:
        stale = not t.exists() or t.read_bytes() != Path(src).read_bytes()
    except OSError:
        stale = True
    if stale:
        pairs.append((src, t))
        msgs.append("плагин поставлен")
    ev = Path(src).parent / EVENTS_PLUGIN                    # 1.26: the fines plugin goes along
    if ev.exists():
        te = events_path(gdir)
        try:
            ev_stale = not te.exists() or te.read_bytes() != ev.read_bytes()
        except OSError:
            ev_stale = True
        if ev_stale:
            pairs.append((ev, te))
            msgs.append("плагин штрафов поставлен")
    vc = vc_missing(gdir) + (vc_missing(gdir, VC_EVENTS) if ev.exists() else [])
    here = Path(gdir) / "bin" / "win_x64"
    for d in vc:
        s = next((f for f in Path(vc_dir).glob("*") if f.name.lower() == d), None) if vc_dir else None
        if not s:
            return False, f"Не хватает {d}, а взять его негде. Установите Visual C++ x64 с сайта Microsoft: {VC_URL}"
        pairs.append((s, here / d))
    if vc:
        msgs.append("библиотеки Visual C++ положены рядом с игрой")
    if not pairs:
        return True, "Плагин и библиотеки на месте. Перезапустите игру и в окне про SDK нажмите OK."
    ok, how = copy_files(pairs)
    if not ok:
        return False, how
    return True, ("Готово: " + ", ".join(msgs) + ". Перезапустите игру и в окне про SDK нажмите OK.")


def quiet_events_install(src_dir, gdir):
    """1.26: put the fines plugin (and its Visual C++ if Windows lacks it) into the game WITHOUT any prompt: a plain
    copy or nothing (no administrator window may ever pop up over the game). -> (done, text)."""
    ev = Path(src_dir) / EVENTS_PLUGIN
    if not gdir or not ev.exists() or not events_missing(gdir):
        return False, ""
    pairs = [] if events_path(gdir).exists() else [(ev, events_path(gdir))]
    for d in vc_missing(gdir, VC_EVENTS):
        s = next((f for f in (Path(src_dir) / "vc").glob("*") if f.name.lower() == d), None)
        if not s:
            return False, "нет " + d + " для плагина штрафов"
        pairs.append((s, Path(gdir) / "bin" / "win_x64" / d))
    try:
        for s, d in pairs:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
    except OSError as e:
        return False, "папка игры защищена (" + str(e.strerror or e) + "), нужен пункт меню значка «Исправить плагин телеметрии»"
    return True, "плагин штрафов поставлен в игру, заработает со следующего запуска игры"


def details():
    """One log line for the radio's log: how the radio and the game run, and what the memory names answer."""
    me, game = token_info(), (token_info(LAST_PID) if LAST_PID else {})
    return f"рация {me}; игра (pid {LAST_PID}) {game}; память {mapping_probe()}; журнал игры: {game_log_plugin()}"


def install_plugin(src, gdir):
    """Copy the plugin into the game. -> (ok, text). The game loads it on its next start."""
    t = plugin_path(gdir)
    ok, how = copy_files([(src, t)])
    if ok:
        return True, f"Плагин поставлен в {t.parent}. Перезапустите игру — рация её увидит."
    return False, how


# ================================================================ 1.13: любая копия игры, не только Steam
# 2026-11-05: многие играют не из Steam (отдельная версия, сборки-репаки). Рации всё равно, откуда игра: ей нужен
# только плагин в bin\win_x64\plugins. Ищем игру везде, где Windows о ней помнит; кладём плагин и туда, куда
# без прав администратора нельзя (C:\Program Files); снимаем «запускать от имени администратора», которое
# ставят многие сборки (из-за него Windows не пускает рацию к данным игры).
import os  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402

_EXE_RE = re.compile(r"([a-z]:\\[^|\"<>*?]*?\\bin\\win_x64\\" + re.escape(GAME_EXE) + ")", re.I)
LAYERS = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"


def is_game_dir(d):
    try:
        return (Path(d) / "bin" / "win_x64" / GAME_EXE).is_file()
    except (OSError, ValueError):
        return False


def _root_of(p):
    """A path in or under a game folder (exe, uninstaller, icon «…exe,0», folder) -> the game folder or None."""
    s = str(p or "").strip().strip('"')
    low = s.lower()
    if ".exe" in low:
        s = s[:low.index(".exe") + 4]
    if not s or ":" not in s:
        return None
    p = Path(s)
    for c in [p] + list(p.parents)[:4]:
        if is_game_dir(c):
            return c
    return None


def _reg_values(hive, path):
    import winreg
    out = []
    try:
        with winreg.OpenKey(hive, path) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumValue(k, i))
                except OSError:
                    break
                i += 1
    except OSError:
        pass
    return out


def _reg_subkeys(hive, path):
    import winreg
    out = []
    try:
        with winreg.OpenKey(hive, path) as k:
            i = 0
            while True:
                try:
                    out.append(winreg.EnumKey(k, i))
                except OSError:
                    break
                i += 1
    except OSError:
        pass
    return out


def _launched_exes():
    """Every eurotrucks2.exe Windows remembers starting (compatibility assistant, shell cache, compatibility
    flags, firewall rules) — the copies the player actually plays."""
    import winreg
    H, L = winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE
    places = [(H, r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store"),
              (H, r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"),
              (H, LAYERS), (L, LAYERS),
              (L, r"SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy\FirewallRules")]
    out = []
    for hive, path in places:
        for name, data, _ in _reg_values(hive, path):
            for s in (name, data if isinstance(data, str) else ""):
                m = _EXE_RE.search(s)
                if m:
                    out.append(m.group(1))
    return out


def _uninstall_entries():
    """Installed programs (Steam, the SCS standalone version, setup-based copies) named like the game."""
    import winreg
    out = []
    for hive, path in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                       (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                       (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall")):
        for sub in _reg_subkeys(hive, path):
            vals = {n: d for n, d, _ in _reg_values(hive, path + "\\" + sub)}
            name = str(vals.get("DisplayName", "")).lower()
            if "euro truck" in name or re.search(r"\bets\s?2\b", name) or sub.lower() == "steam app 227300":
                out += [str(vals.get(k, "")) for k in ("InstallLocation", "Inno Setup: App Path", "DisplayIcon",
                                                       "UninstallString")]
    return out


SCAN_SKIP = {"windows", "$recycle.bin", "system volume information", "programdata", "recovery", "perflogs",
             "$windows.~bt", "$windows.~ws", "$winreagent", "msocache", "config.msi", "windowsapps", "appdata",
             "intel", "amd", "nvidia", "drivers", "windows.old", "$sysreset", "onedrivetemp"}
SCAN_HINTS = ("truck", "ets", "евро", "трак", "грузов")


def _scan_drives(budget=4.0, depth=3):
    """Last resort: folders named like the game on every local disk, 3 levels deep, a few seconds at most."""
    t_end = time.monotonic() + budget
    found = []
    mask = _k.GetLogicalDrives()
    roots = []
    for i in range(26):
        if mask >> i & 1:
            d = f"{chr(65 + i)}:\\"
            if _k.GetDriveTypeW(d) == 3:                       # DRIVE_FIXED
                roots.append(d)
    level = [(r, 0) for r in roots]
    while level and time.monotonic() < t_end:
        nxt = []
        for d, lv in level:
            if time.monotonic() > t_end:
                break
            try:
                with os.scandir(d) as it:
                    for e in it:
                        try:
                            if not e.is_dir(follow_symlinks=False):
                                continue
                        except OSError:
                            continue
                        low = e.name.lower()
                        if low in SCAN_SKIP:
                            continue
                        if any(h in low for h in SCAN_HINTS) and is_game_dir(e.path):
                            found.append(e.path)
                            continue
                        if lv + 1 < depth:
                            nxt.append((e.path, lv + 1))
            except OSError:
                continue
        level = nxt
    return found


def find_games(extra=(), scan=True):
    """Every ETS2 folder on this PC, the ones the player runs first: the running game, copies Windows remembers
    starting, installed programs, `extra` (Steam libraries), then — only if nothing else turned up — a disk scan."""
    cands = []
    try:
        exe = game_process()
        if exe and exe.name:
            cands.append(str(exe))
    except OSError:
        pass
    for src in (_launched_exes, _uninstall_entries):
        try:
            cands += src()
        except Exception:  # noqa: BLE001 — a strange registry must not stop the search
            pass
    cands += [str(x) for x in extra]
    out, seen = [], set()

    def add(c):
        g = _root_of(c)
        if g:
            key = os.path.normcase(os.path.realpath(g))
            if key not in seen:
                seen.add(key)
                out.append(g)
    for c in cands:
        add(c)
    if not out and scan:
        try:
            for c in _scan_drives():
                add(c)
        except Exception:  # noqa: BLE001
            pass
    return out


# ---------------------------------------------------------------- administrator rights only when Windows demands
class _SEI(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", ctypes.c_void_p),
                ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]


def run_as_admin(file, params="", wait=True, timeout=120):
    """Start `file` with administrator rights (Windows asks the player «Да/Нет»), hidden window.
    -> (ok, None | 'cancelled' | error text)."""
    sh = ctypes.WinDLL("shell32", use_last_error=True)
    sh.ShellExecuteExW.argtypes = [ctypes.POINTER(_SEI)]
    sei = _SEI()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = 0x40 if wait else 0                              # SEE_MASK_NOCLOSEPROCESS
    sei.lpVerb, sei.lpFile, sei.lpParameters, sei.nShow = "runas", str(file), params, 0 if wait else 1
    if not sh.ShellExecuteExW(ctypes.byref(sei)):
        err = ctypes.get_last_error()
        return False, "cancelled" if err == 1223 else f"ошибка Windows {err}"
    if not wait:
        return True, None
    try:
        _k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        if _k.WaitForSingleObject(sei.hProcess, int(timeout * 1000)) != 0:
            return False, "не дождался"
        code = wintypes.DWORD()
        _k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        _k.GetExitCodeProcess(sei.hProcess, ctypes.byref(code))
        return code.value == 0, None if code.value == 0 else f"код {code.value}"
    finally:
        _k.CloseHandle(sei.hProcess)


def _ps_quote(v):
    return "'" + str(v).replace("'", "''") + "'"


def run_admin_ps(lines):
    """A few PowerShell commands with administrator rights in one prompt. -> (ok, None | 'cancelled' | text)."""
    import base64
    err = Path(os.environ.get("TEMP", str(Path.home()))) / "Kanal15-admin-error.txt"
    try:
        err.unlink(missing_ok=True)
    except OSError:
        pass
    script = ("$ErrorActionPreference='Stop'\ntry {\n" + "\n".join(lines) + "\nexit 0\n} catch { "
              f"$_ | Out-String | Out-File -LiteralPath {_ps_quote(err)} -Encoding utf8; exit 1 }}")
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    ps = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    ok, why = run_as_admin(ps, "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass "
                               f"-EncodedCommand {enc}")
    if not ok and why not in ("cancelled", None):
        try:
            why = f"{why}: " + " ".join(err.read_text(encoding="utf-8-sig").split())[:300]
        except OSError:
            pass
    return ok, why


def copy_files(pairs):
    """[(src, dst)] -> (ok, text). Plain copy; what Windows protects (C:\\Program Files …) — with ONE
    administrator prompt for all of it."""
    left = []
    for s, d in pairs:
        s, d = Path(s).resolve(), Path(d).resolve()          # the elevated PowerShell starts in System32
        try:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
        except OSError as e:
            if getattr(e, "winerror", None) != 32 and (getattr(e, "winerror", None) == 5 or isinstance(e, PermissionError)):
                left.append((s, d))
            elif getattr(e, "winerror", None) == 32:           # the file is in use
                return False, "Файл занят игрой. Закройте игру и попробуйте ещё раз."
            else:
                return False, f"Не получилось положить {d.name} в папку игры ({e.strerror or e})."
    if not left:
        return True, ""
    ok, why = run_admin_ps([f"New-Item -ItemType Directory -Force -Path {_ps_quote(d.parent)} | Out-Null\n"
                            f"Copy-Item -LiteralPath {_ps_quote(s)} -Destination {_ps_quote(d)} -Force"
                            for s, d in left])
    if ok and all(d.exists() for _, d in left):
        return True, "admin"
    if why == "cancelled":
        return False, ("Папка игры защищена Windows, а разрешение администратора не дали. Нажмите ещё раз и в "
                       "окне Windows ответьте «Да».")
    return False, f"Не получилось положить файлы в папку игры даже с правами администратора ({why or 'ошибка'})."


def remove_file(p):
    """Delete a file we put into the game (with an administrator prompt if the folder is protected)."""
    p = Path(p).resolve()
    try:
        p.unlink(missing_ok=True)
        return True, ""
    except OSError as e:
        if getattr(e, "winerror", None) == 32 or not (getattr(e, "winerror", None) == 5 or isinstance(e, PermissionError)):
            return False, e.strerror or str(e)
    ok, why = run_admin_ps([f"Remove-Item -LiteralPath {_ps_quote(p)} -Force"])
    return ok and not p.exists(), why or ""


# ---------------------------------------------------------------- «запускать от имени администратора»
def admin_flags():
    """Where the game is marked «run as administrator» (many repacks do it): [(hive, exe path, flags)]."""
    import winreg
    out = []
    for hive, hn in ((winreg.HKEY_CURRENT_USER, "HKCU"), (winreg.HKEY_LOCAL_MACHINE, "HKLM")):
        for name, data, _ in _reg_values(hive, LAYERS):
            if name.lower().endswith("\\" + GAME_EXE) and "RUNASADMIN" in str(data).upper().split():
                out.append((hn, name, str(data)))
    return out


def _without_admin(flags):
    toks = [t for t in flags.split() if t.upper() != "RUNASADMIN"]
    return " ".join(toks) if [t for t in toks if t != "~"] else None


def clear_admin_flags():
    """Take «run as administrator» off the game (other compatibility flags stay). -> (ok, text)."""
    import winreg
    flags = admin_flags()
    if not flags:
        return False, ("У самой игры нет отметки «запускать от имени администратора» — значит, её так запускает "
                       "лаунчер или ярлык. Запустите игру через Steam или bin\\win_x64\\eurotrucks2.exe, либо "
                       "перезапустите рацию с правами администратора (меню значка).")
    hklm = []
    for hn, exe, data in flags:
        new = _without_admin(data)
        if hn == "HKCU":
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, LAYERS, 0, winreg.KEY_SET_VALUE) as k:
                    if new is None:
                        winreg.DeleteValue(k, exe)
                    else:
                        winreg.SetValueEx(k, exe, 0, winreg.REG_SZ, new)
            except OSError as e:
                return False, f"Не получилось снять отметку ({e.strerror or e})."
        else:
            key = _ps_quote("HKLM:\\" + LAYERS)
            hklm.append(f"Remove-ItemProperty -LiteralPath {key} -Name {_ps_quote(exe)}" if new is None else
                        f"Set-ItemProperty -LiteralPath {key} -Name {_ps_quote(exe)} -Value {_ps_quote(new)}")
    if hklm:
        ok, why = run_admin_ps(hklm)
        if not ok:
            return False, ("Отметка стоит для всех пользователей, и снять её можно только с разрешения "
                           "администратора. Нажмите ещё раз и в окне Windows ответьте «Да».") if why == "cancelled" \
                else f"Не получилось снять отметку ({why})."
    if admin_flags():
        return False, "Отметка «от имени администратора» не снялась."
    return True, "Готово: игра больше не будет запускаться от имени администратора. Перезапустите игру."


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False
