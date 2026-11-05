"""Значок рации возле часов вместо консольного окна (2026-11-04, выбор пользователя: «только значок в трее»).
Никаких окон поверх игры: значок ничего не открывает сам, только по клику пользователя.
Меню: состояние и кто в зоне, громкость, «Тишина в эфире», настройки (config.json), журнал эфира, выход.
Цвет точки на значке: зелёная — едем, жёлтая — пауза / мотор выключен, серая — игры нет.
Нужен пакет pystray (+ Pillow). Без него рация работает как раньше, в консоли."""
import json
import os
import threading
from pathlib import Path

STATE = {"status": "запуск…", "st": "no_game", "inside": [], "muted": False, "quit": False}
_icon = None
_lock = threading.Lock()
HOOKS = {}      # set by cb_radio: mics / mic_now / mic_info / mic_set / plugin_needed / plugin_install
COLORS = {"driving": (60, 190, 90), "engine_off": (235, 190, 40), "paused": (235, 190, 40), "no_game": (150, 150, 150)}


def _image(base, st):
    from PIL import Image, ImageDraw
    img = base.copy()
    d = ImageDraw.Draw(img)
    w, h = img.size
    r = w // 4
    d.ellipse((w - 2 * r - 1, h - 2 * r - 1, w - 1, h - 1), fill=COLORS.get(st, COLORS["no_game"]) + (255,),
              outline=(20, 20, 20, 255), width=max(1, w // 32))
    return img


def _base(root):
    from PIL import Image, ImageDraw
    for p in (root / "installer" / "icon.png", root / "installer_art" / "icon.png"):
        if p.exists():
            return Image.open(p).convert("RGBA").resize((64, 64), Image.LANCZOS)
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))            # fallback: a gold «15» badge
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, 60, 60), 12, fill=(242, 193, 78, 255))
    d.text((18, 20), "15", fill=(20, 20, 20, 255))
    return img


def start(cfg, cfg_file, log_file, root, names, version="?"):
    """Start the tray icon in its own thread. Returns False if pystray is missing (radio stays in console mode)."""
    global _icon
    try:
        import pystray
        from pystray import Menu, MenuItem as Item
    except Exception:
        return False
    base = _base(root)

    def save_cfg():
        try:
            cur = json.loads(cfg_file.read_text(encoding="utf-8-sig")) if cfg_file.exists() else {}
            cur["volume"] = cfg["volume"]
            cfg_file.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def set_vol(p):
        def f(icon, item):
            cfg["volume"] = p / 100
            save_cfg()
        return f

    def toggle_mute(icon, item):
        STATE["muted"] = not STATE["muted"]
        refresh()

    def open_file(path):
        def f(icon, item):
            try:
                os.startfile(str(path))
            except OSError:
                pass
        return f

    def quit_(icon, item):
        STATE["quit"] = True                  # the main loop saves the world and exits...
        icon.visible = False
        threading.Timer(4.0, os._exit, (0,)).start()   # ...unless it is busy playing a long scene: then just go

    def inside_text(item):
        who = [names.get(k, k) for k in STATE["inside"]]
        return "В зоне: " + (", ".join(who) if who else "никого")

    def hook(name, default=None):
        def f(*a):
            fn = HOOKS.get(name)
            try:
                return fn(*a) if fn else default
            except Exception:
                return default
        return f

    def mic_items():
        now = hook("mic_now", "")()
        names = hook("mics", [])() or []
        if not names:
            return (Item("микрофонов не найдено", None, enabled=False),)
        return tuple(Item(n, (lambda n: lambda icon, item: hook("mic_set")(n))(n),
                          checked=(lambda n: lambda i: n == hook("mic_now", "")())(n), radio=True) for n in names)

    def air_items():
        return tuple(Item(name, (lambda k: lambda icon, item: hook("air_set")(k))(k),
                          checked=(lambda k: lambda i: hook("air_now", "normal")() == k)(k), radio=True)
                     for k, name in (hook("air_levels", [])() or []))

    vol = Menu(*[Item(f"{p}%", set_vol(p), checked=lambda i, p=p: round(float(cfg["volume"]) * 100) == p, radio=True)
                 for p in (25, 50, 80, 100)])
    menu = Menu(
        Item(lambda i: f"Канал 15 v{version} · {STATE['status']}", None, enabled=False),
        Item(inside_text, None, enabled=False),
        Item(lambda i: "Микрофон: " + str(hook("mic_now", "—")() or "—")[:60], None, enabled=False),
        Item(lambda i: "Последнее нажатие: " + str(hook("mic_info", "—")() or "—")[:60], None, enabled=False),
        Menu.SEPARATOR,
        Item("Исправить плагин телеметрии", lambda icon, item: hook("plugin_install")(),
             visible=lambda i: bool(hook("plugin_needed", False)())),
        Item("Громкость", vol),
        Item("Эфир", Menu(air_items)),
        Item("Микрофон", Menu(mic_items)),
        Item("Тишина в эфире", toggle_mute, checked=lambda i: STATE["muted"]),
        Item("Настройки…", open_file(cfg_file)),
        Item("Журнал эфира…", open_file(log_file)),
        Menu.SEPARATOR,
        Item("Выключить рацию", quit_),
    )
    _icon = pystray.Icon("kanal15", _image(base, STATE["st"]), "Канал 15", menu)
    _icon._k15_base = base
    _icon.run_detached()
    refresh()
    threading.Thread(target=_promote, daemon=True).start()
    return True


def _promote(tries=20):
    """Windows 11 hides every NEW tray icon under «^» (2026-11-05: the user and Kirill never saw ours, so they
    could not reach «Выход»). Explorer keeps one entry per program in HKCU\\Control Panel\\NotifyIconSettings;
    IsPromoted=1 puts the icon on the taskbar. We set it only for our own entry and only while the value is
    absent, so if the user later hides the icon himself, his choice stays."""
    import sys
    import time
    import winreg
    exe = os.path.normcase(os.path.abspath(sys.executable))
    frozen = getattr(sys, "frozen", False)
    for _ in range(tries):                    # the entry appears a moment after the icon does
        time.sleep(1.5)
        try:
            root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\NotifyIconSettings")
        except OSError:
            return                            # Windows 10: no such list, icons are managed differently
        with root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, sub, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
                        path = os.path.normcase(os.path.expandvars(winreg.QueryValueEx(k, "ExecutablePath")[0]))
                        if path != exe:
                            continue
                        if not frozen:        # dev: pythonw.exe serves other scripts too -> only our tooltip
                            try:
                                if not str(winreg.QueryValueEx(k, "InitialTooltip")[0]).startswith("Канал 15"):
                                    continue
                            except OSError:
                                continue
                        try:
                            winreg.QueryValueEx(k, "IsPromoted")
                        except OSError:
                            winreg.SetValueEx(k, "IsPromoted", 0, winreg.REG_DWORD, 1)
                        return
                except OSError:
                    continue


def notify(text):
    """A Windows notification from the icon (does not take focus from the game)."""
    if not _icon:
        return
    try:
        _icon.notify(text[:250], "Канал 15")
    except Exception:
        pass


def refresh():
    """Update the icon colour, tooltip and menu texts (call after the state changes; cheap)."""
    if not _icon:
        return
    with _lock:
        try:
            _icon.icon = _image(_icon._k15_base, STATE["st"])
            who = len(STATE["inside"])
            tip = f"Канал 15 — {STATE['status']}" + (f", в зоне: {who}" if who else "") + \
                  (" (тишина)" if STATE["muted"] else "")
            _icon.title = tip[:127]
            _icon.update_menu()
        except Exception:
            pass


def set_state(st, status=None, inside=None):
    changed = False
    if st != STATE["st"] or (status and status != STATE["status"]):
        STATE["st"], STATE["status"] = st, status or STATE["status"]
        changed = True
    if inside is not None and sorted(inside) != STATE["inside"]:
        STATE["inside"] = sorted(inside)
        changed = True
    if changed:
        refresh()


def stop():
    if _icon:
        try:
            _icon.stop()
        except Exception:
            pass
