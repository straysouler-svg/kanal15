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


def vc_missing(gdir=None):
    """Runtime DLLs the plugin needs that Windows cannot find (System32, or next to eurotrucks2.exe)."""
    import os
    sys32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    here = Path(gdir) / "bin" / "win_x64" if gdir else None
    return [d for d in VC_DLLS if not (sys32 / d).exists() and not (here and (here / d).exists())]


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
        return "admin", ("Игра запущена от имени администратора, и Windows не пускает к ней рацию. Запустите игру "
                         "обычным способом (без «от имени администратора») или рацию тоже от администратора.")
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
    return bool(gdir) and (not plugin_path(gdir).exists() or bool(vc_missing(gdir)))


def fix(src, vc_dir, gdir):
    """Plugin into the game + (if Windows lacks it) MSVCR110.dll next to eurotrucks2.exe — app-local,
    no admin rights; the installer carries it in installer\\plugins\\vc. -> (ok, text)."""
    msgs, ok = [], True
    if not plugin_path(gdir).exists():
        ok, text = install_plugin(src, gdir)
        if not ok:
            return ok, text
        msgs.append("плагин поставлен")
    vc = vc_missing(gdir)
    if vc:
        here = Path(gdir) / "bin" / "win_x64"
        for d in vc:
            s = next((f for f in Path(vc_dir).glob("*") if f.name.lower() == d), None) if vc_dir else None
            if not s:
                return False, f"Не хватает {d}, а взять его негде. Установите Visual C++ x64 с сайта Microsoft: {VC_URL}"
            try:
                shutil.copy2(s, here / d)
            except OSError as e:
                return False, (f"Не получилось положить {d} в папку игры ({e.strerror}). Закройте игру и попробуйте "
                               f"ещё раз или установите Visual C++ x64: {VC_URL}")
        msgs.append("библиотеки Visual C++ положены рядом с игрой")
    if not msgs:
        return True, "Плагин и библиотеки на месте. Перезапустите игру и в окне про SDK нажмите OK."
    return ok, ("Готово: " + ", ".join(msgs) + ". Перезапустите игру и в окне про SDK нажмите OK.")


def details():
    """One log line for the radio's log: how the radio and the game run, and what the memory names answer."""
    me, game = token_info(), (token_info(LAST_PID) if LAST_PID else {})
    return f"рация {me}; игра (pid {LAST_PID}) {game}; память {mapping_probe()}; журнал игры: {game_log_plugin()}"


def install_plugin(src, gdir):
    """Copy the plugin into the game. -> (ok, text). The game loads it on its next start."""
    t = plugin_path(gdir)
    try:
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, t)
        return True, f"Плагин поставлен в {t.parent}. Перезапустите игру — рация её увидит."
    except OSError as e:
        return False, f"Не получилось поставить плагин ({e.strerror}). Закройте игру и попробуйте ещё раз."
