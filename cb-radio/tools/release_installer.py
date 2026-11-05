"""CB-рация: установщик (идёт в раздачу как installer.py). Plays «Кардан крутится» while installing
(user 2026-11-04: «это шедевр»), with a mute button. Only the standard library: tkinter + winsound + ctypes.
Creates .venv next to itself, installs requirements.txt into it, then binds the push-to-talk button
(a separate dialog: press the wheel button -> device + button number go to config.json)."""
import ctypes
import json
import subprocess
import sys
import threading
import tkinter as tk
import winsound
from pathlib import Path

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- joystick buttons (same way the radio reads them)
class JOYCAPSW(ctypes.Structure):
    _fields_ = ([("wMid", ctypes.c_uint16), ("wPid", ctypes.c_uint16), ("szPname", ctypes.c_wchar * 32)]
                + [(n, ctypes.c_uint) for n in ("wXmin", "wXmax", "wYmin", "wYmax", "wZmin", "wZmax", "wNumButtons",
                                               "wPeriodMin", "wPeriodMax", "wRmin", "wRmax", "wUmin", "wUmax", "wVmin",
                                               "wVmax", "wCaps", "wMaxAxes", "wNumAxes", "wMaxButtons")]
                + [("szRegKey", ctypes.c_wchar * 32), ("szOEMVxD", ctypes.c_wchar * 260)])


class JOYINFOEX(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint) for n in ("dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos",
                                               "dwVpos", "dwButtons", "dwButtonNumber", "dwPOV", "dwR1", "dwR2")]


def oem_name(vid, pid):
    import winreg
    key = rf"System\CurrentControlSet\Control\MediaProperties\PrivateProperties\Joystick\OEM\VID_{vid:04X}&PID_{pid:04X}"
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, key) as k:
                return winreg.QueryValueEx(k, "OEMName")[0]
        except OSError:
            pass
    return ""


def read_buttons(ids=None):
    """{joystick id: (name, buttons bitmask)} for every connected game controller (or only for `ids`)."""
    mm = ctypes.WinDLL("winmm")
    out = {}
    for i in (range(16) if ids is None else ids):
        caps = JOYCAPSW()
        if mm.joyGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps)) != 0:
            continue
        ji = JOYINFOEX()
        ji.dwSize, ji.dwFlags = ctypes.sizeof(ji), 0x80
        if mm.joyGetPosEx(i, ctypes.byref(ji)) == 0:
            out[i] = (oem_name(caps.wMid, caps.wPid) or f"{caps.wMid:04X}:{caps.wPid:04X}", ji.dwButtons)
    return out


class BindDialog:
    """«Нажми кнопку рации»: catches the first button that goes down and saves it to config.json."""

    def __init__(self, root):
        self.w = tk.Toplevel(root)
        self.w.title("Кнопка рации")
        self.w.geometry("460x230")
        self.w.configure(bg="#1d1f21")
        self.w.grab_set()
        tk.Label(self.w, text="Нажми и отпусти кнопку на руле,\nкоторой будешь говорить в рацию",
                 fg="#f0c674", bg="#1d1f21", font=("Segoe UI", 12)).pack(pady=(18, 8))
        self.info = tk.Label(self.w, text="Жду нажатия…", fg="#c5c8c6", bg="#1d1f21", font=("Segoe UI", 11))
        self.info.pack(pady=6)
        row = tk.Frame(self.w, bg="#1d1f21")
        row.pack(pady=12)
        self.save_btn = tk.Button(row, text="Сохранить", state="disabled", command=self.save, bg="#5f875f", fg="white",
                                  relief="flat", padx=12, pady=4, font=("Segoe UI", 10))
        self.save_btn.pack(side="left", padx=6)
        tk.Button(row, text="Ещё раз", command=self.reset, bg="#373b41", fg="white", relief="flat", padx=12, pady=4,
                  font=("Segoe UI", 10)).pack(side="left", padx=6)
        tk.Button(row, text="Позже", command=self.w.destroy, bg="#373b41", fg="white", relief="flat", padx=12, pady=4,
                  font=("Segoe UI", 10)).pack(side="left", padx=6)
        self.reset()

    def reset(self):
        try:
            ctypes.WinDLL("winmm").joyConfigChanged(0)
            self.base = read_buttons()
        except OSError:
            self.base = {}
        self.found = None
        self.save_btn.config(state="disabled")
        self.info.config(text="Жду нажатия…" if self.base else "Рули и кнопки не найдены. Подключи руль и нажми «Ещё раз».")
        self.poll()

    def poll(self):
        if self.found or not self.w.winfo_exists():
            return
        try:
            now = read_buttons()
        except OSError:
            now = {}
        for i, (name, b) in now.items():
            pressed = b & ~self.base.get(i, (name, 0))[1]
            if pressed:
                btn = (pressed & -pressed).bit_length() - 1
                self.found = (name, btn)
                self.info.config(text=f"Нашёл: {name}, кнопка {btn}", fg="#b5bd68")
                self.save_btn.config(state="normal")
                return
        self.base = {i: (n, b) for i, (n, b) in now.items()} if not self.base else self.base
        self.w.after(30, self.poll)

    def save(self):
        cfg_f = HERE / "config.json"
        cfg = json.loads(cfg_f.read_text(encoding="utf-8")) if cfg_f.exists() else {}
        cfg["ptt"] = {"device": self.found[0], "button": self.found[1]}
        cfg_f.write_text(json.dumps(cfg, ensure_ascii=False, indent=4), encoding="utf-8")
        self.info.config(text=f"Сохранено: {self.found[0]}, кнопка {self.found[1]}")
        self.w.after(900, self.w.destroy)


PLUGIN = HERE / "installer" / "plugins" / "ets2-telemetry.dll"


def find_game_dirs():
    """ETS2 install folders: every Steam library (registry + libraryfolders.vdf) that has the game."""
    import re
    import winreg
    steam = []
    for root, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
        try:
            with winreg.OpenKey(root, key) as k:
                for name in ("SteamPath", "InstallPath"):
                    try:
                        steam.append(Path(winreg.QueryValueEx(k, name)[0]))
                    except OSError:
                        pass
        except OSError:
            pass
    libs = []
    for st in steam + [Path(r"C:\Program Files (x86)\Steam")]:
        libs.append(st)
        vdf = st / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace")):
                libs.append(Path(m.group(1).replace("\\\\", "\\")))
    found = []
    for lib in libs:
        g = lib / "steamapps" / "common" / "Euro Truck Simulator 2"
        if (g / "bin" / "win_x64").exists() and g.resolve() not in [f.resolve() for f in found]:
            found.append(g)
    return found


class PluginDialog:
    """Puts the telemetry plugin (the radio's eyes: driving / paused / position) into the game's plugins folder."""

    def __init__(self, root, then=None):
        self.then = then
        self.w = tk.Toplevel(root)
        self.w.title("Плагин телеметрии")
        self.w.geometry("560x260")
        self.w.configure(bg="#1d1f21")
        self.w.grab_set()
        self.w.protocol("WM_DELETE_WINDOW", self.done)
        tk.Label(self.w, text="Плагин телеметрии для игры", fg="#f0c674", bg="#1d1f21",
                 font=("Segoe UI", 12, "bold")).pack(pady=(16, 4))
        tk.Label(self.w, text="По нему рация понимает, что ты едешь, где ты и когда пауза.\nИгру перед установкой закрой.",
                 fg="#c5c8c6", bg="#1d1f21", font=("Segoe UI", 10)).pack()
        self.info = tk.Label(self.w, text="", fg="#81a2be", bg="#1d1f21", font=("Segoe UI", 9), wraplength=520)
        self.info.pack(pady=10)
        row = tk.Frame(self.w, bg="#1d1f21")
        row.pack(pady=6)
        b = dict(fg="white", relief="flat", padx=12, pady=4, font=("Segoe UI", 10))
        self.inst = tk.Button(row, text="Установить", command=self.install, bg="#5f875f", **b)
        self.inst.pack(side="left", padx=5)
        tk.Button(row, text="Выбрать папку игры…", command=self.pick, bg="#373b41", **b).pack(side="left", padx=5)
        tk.Button(row, text="Пропустить", command=self.done, bg="#373b41", **b).pack(side="left", padx=5)
        dirs = find_game_dirs()
        self.game = dirs[0] if dirs else None
        self.show()

    def target(self):
        return self.game / "bin" / "win_x64" / "plugins" / PLUGIN.name if self.game else None

    def show(self):
        if not self.game:
            self.info.config(text="Игру не нашёл. Нажми «Выбрать папку игры…» (папка, где лежит bin).", fg="#cc6666")
            self.inst.config(state="disabled")
            return
        t = self.target()
        same = t.exists() and t.stat().st_size == PLUGIN.stat().st_size and t.read_bytes() == PLUGIN.read_bytes()
        self.info.config(text=f"Игра: {self.game}\n" + ("Плагин уже стоит — ничего делать не нужно." if same
                         else r"Плагин будет положен в bin\win_x64\plugins"), fg="#b5bd68" if same else "#81a2be")
        self.inst.config(state="disabled" if same else "normal")

    def pick(self):
        from tkinter import filedialog
        d = filedialog.askdirectory(parent=self.w, title="Папка Euro Truck Simulator 2")
        if d:
            g = Path(d)
            if (g / "bin" / "win_x64").exists():
                self.game = g
            elif g.name == "win_x64":
                self.game = g.parents[1]
            else:
                self.info.config(text=r"В этой папке нет bin\win_x64 — это не папка игры.", fg="#cc6666")
                return
            self.show()

    def install(self):
        import shutil
        t = self.target()
        try:
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PLUGIN, t)
            self.info.config(text=f"Готово: {t}", fg="#b5bd68")
            self.inst.config(state="disabled")
            self.w.after(1200, self.done)
        except OSError as e:
            self.info.config(text=f"Не получилось ({e.strerror}). Закрой игру и нажми ещё раз.", fg="#cc6666")

    def done(self):
        self.w.destroy()
        if self.then:
            self.then()


SONG = HERE / "installer" / "kardan_kruchitsya.wav"
VENV = HERE / ".venv"


class App:
    def __init__(self, root):
        self.root, self.muted = root, False
        root.title("CB-рация — установка")
        root.geometry("640x560")
        root.resizable(False, False)
        root.configure(bg="#1d1f21")
        art = HERE / "installer"
        try:
            self.icon = tk.PhotoImage(file=str(art / "icon.png"))
            root.iconphoto(True, self.icon)
            self.banner = tk.PhotoImage(file=str(art / "banner.png"))
            tk.Label(root, image=self.banner, bd=0, bg="#1d1f21").pack()
        except tk.TclError:
            tk.Label(root, text="CB-рация для Euro Truck Simulator 2", fg="#f0c674", bg="#1d1f21",
                     font=("Segoe UI", 15, "bold")).pack(pady=(14, 2))
        tk.Label(root, text="♪ Сейчас играет: Кардан — «Кардан крутится»", fg="#b5bd68", bg="#1d1f21",
                 font=("Segoe UI", 10)).pack(pady=(8, 0))
        self.btn = tk.Button(root, text="🔇 Выключить музыку", command=self.toggle, font=("Segoe UI", 10),
                             bg="#373b41", fg="#ffffff", activebackground="#4a4f57", relief="flat", padx=10, pady=4)
        self.btn.pack(pady=(8, 2))
        row = tk.Frame(root, bg="#1d1f21")
        row.pack(pady=(2, 8))
        for text, cmd in (("🔌 Плагин телеметрии", lambda: PluginDialog(root)), ("🎙 Кнопка рации", lambda: BindDialog(root))):
            tk.Button(row, text=text, command=cmd, font=("Segoe UI", 10), bg="#373b41", fg="#ffffff",
                      activebackground="#4a4f57", relief="flat", padx=10, pady=4).pack(side="left", padx=4)
        self.log = tk.Text(root, height=11, bg="#111213", fg="#c5c8c6", font=("Consolas", 9), relief="flat")
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.status = tk.Label(root, text="Устанавливаю…", fg="#81a2be", bg="#1d1f21", font=("Segoe UI", 10))
        self.status.pack(pady=(0, 10))
        self.play()
        root.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self.install, daemon=True).start()

    def play(self):
        if SONG.exists():
            winsound.PlaySound(str(SONG), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)

    def toggle(self):
        self.muted = not self.muted
        if self.muted:
            winsound.PlaySound(None, 0)
            self.btn.config(text="🔊 Включить музыку")
        else:
            self.play()
            self.btn.config(text="🔇 Выключить музыку")

    def say(self, line):
        self.root.after(0, lambda: (self.log.insert("end", line), self.log.see("end")))

    def run(self, cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                             errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in p.stdout:
            self.say(line)
        return p.wait()

    def install(self):
        ok = True
        try:
            if not (VENV / "Scripts" / "python.exe").exists():
                self.say("Создаю окружение Python…\n")
                ok = self.run([sys.executable, "-m", "venv", str(VENV)]) == 0
            if ok:
                self.say("Скачиваю библиотеки (около 1 ГБ, один раз)…\n")
                ok = self.run([str(VENV / "Scripts" / "python.exe"), "-m", "pip", "install", "--disable-pip-version-check",
                               "-r", str(HERE / "requirements.txt")]) == 0
        except Exception as e:  # noqa: BLE001
            self.say(f"\nОшибка: {e!r}\n")
            ok = False
        msg = ("Готово! Плагин и кнопка рации — в окнах; потом запускай «CB Radio.cmd» до запуска игры."
               if ok else "Не получилось — пришли эти строки автору.")
        self.root.after(0, lambda: self.status.config(text=msg, fg="#b5bd68" if ok else "#cc6666", wraplength=580))
        if ok:
            self.root.after(300, lambda: PluginDialog(self.root, then=lambda: BindDialog(self.root)))

    def close(self):
        winsound.PlaySound(None, 0)
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
