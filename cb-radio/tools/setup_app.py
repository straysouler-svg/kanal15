"""CB-рация: установщик одним exe, классический мастер (2026-11-04, user: «стандартный дизайн инсталяторов
с вертикальным баннером»). Left: vertical banner. Right: white wizard pages. Bottom: «< Назад / Далее > / Отмена».
Pages: welcome -> folder -> install (progress) -> telemetry plugin -> push-to-talk button -> finish.
«Кардан крутится» plays during setup with a mute button in the bottom bar (user: «это шедевр»).
Everything is inside (payload.zip): no downloads."""
import array
import json
import math
import os
import queue
import shutil
import socket
import time
import subprocess
import sys
import threading
import tkinter as tk
import winsound
import zipfile
from pathlib import Path
from tkinter import filedialog, ttk

import release_installer as ri      # find_game_dirs, read_buttons (same code the radio uses for buttons)

BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
PAYLOAD = BUNDLE / "payload.zip"
if not PAYLOAD.exists() and getattr(sys, "frozen", False):
    # 1.02: the program archive is appended to the end of the setup exe and read in place. Before, PyInstaller
    # copied ~900 MB to %TEMP% at every start behind a still splash — on a slow disk + antivirus that looked hung.
    PAYLOAD = Path(sys.executable)
ART = BUNDLE / "art"
try:
    _V = json.loads((ART / "version.json").read_text(encoding="utf-8"))
    VERSION, VERSION_DATE = _V["version"], _V["date"]
except Exception:
    VERSION, VERSION_DATE = "1.00", ""
KEEP = {"config.json", "state.json", "world_state.json"}      # never overwritten on reinstall
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CB-Radio"
PAGE_BG, BAR_BG, TXT, GREY = "#ffffff", "#f0f0f0", "#000000", "#555555"
F_TITLE, F_TEXT, F_SMALL = ("Segoe UI", 12, "bold"), ("Segoe UI", 9), ("Segoe UI", 8)


# ---------------------------------------------------------------- system helpers
LOG = Path(os.environ.get("TEMP", str(Path.home()))) / "Kanal15-setup.log"


def slog(msg):
    """%TEMP%\\Kanal15-setup.log: where the setup was when something went wrong (2026-11-05: it hung on Kirill's PC)."""
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass


def game_found():
    """(folders with the game, has the player's profile folder). Never raises."""
    try:
        dirs = ri.find_game_dirs()
    except Exception as e:  # noqa: BLE001
        slog(f"поиск игры: {e!r}")
        dirs = []
    docs = Path(os.path.expanduser("~")) / "Documents" / "Euro Truck Simulator 2"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            docs = Path(os.path.expandvars(winreg.QueryValueEx(k, "Personal")[0])) / "Euro Truck Simulator 2"
    except OSError:
        pass
    return dirs, docs.exists()


def stop_running_radio(port=47819):
    """The radio holds its files open: ask it to switch off before we overwrite them (radio >= 1.01)."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2) as c:
            c.sendall(b"quit")
            c.recv(16)
    except OSError:
        pass
    try:
        subprocess.run(["taskkill", "/F", "/IM", "CB-Radio.exe"], capture_output=True, creationflags=0x08000000,
                       timeout=20, check=False)          # an old 1.00 radio does not listen for «quit»
    except (OSError, subprocess.TimeoutExpired):
        pass
    time.sleep(1.0)


def default_dir():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CB-Radio"


def register_uninstall(app, size_kb):
    """«Программы и компоненты» (per user, no admin rights)."""
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        for name, val in (("DisplayName", "Канал 15 — рация для одиночной игры в ETS2"), ("DisplayVersion", VERSION),
                          ("Publisher", "Грузовички"), ("InstallLocation", str(app)),
                          ("DisplayIcon", str(app / "CB-Radio.exe")),
                          ("UninstallString", f'"{app / "Uninstall.exe"}"')):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
        for name, val in (("EstimatedSize", int(size_kb)), ("NoModify", 1), ("NoRepair", 1)):
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, val)


def desktop_dir():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            return Path(os.path.expandvars(winreg.QueryValueEx(k, "Desktop")[0]))
    except OSError:
        return Path(os.path.expanduser("~")) / "Desktop"


def start_menu():
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def make_shortcuts(items):
    """items: [(lnk path, target exe, workdir, arguments, description)]. One PowerShell call with a time limit
    (2026-11-05: an endless PowerShell call is one way the setup could hang). Returns the links that exist."""
    def q(v):                                             # PowerShell single-quoted string
        return "'" + str(v).replace("'", "''") + "'"
    ps = ";".join(f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({q(l)});$s.TargetPath={q(t)};"
                  f"$s.Arguments={q(a)};$s.WorkingDirectory={q(w)};$s.IconLocation={q(t)};$s.Description={q(d)};$s.Save()"
                  for l, t, w, a, d in items)
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           creationflags=0x08000000, check=False, capture_output=True, timeout=60)
        if r.returncode:
            slog(f"ярлыки: код {r.returncode} {r.stderr.decode('cp866', 'replace')[-300:]}")
    except (OSError, subprocess.TimeoutExpired) as e:
        slog(f"ярлыки: {e!r}")
    return [str(l) for l, *_ in items if Path(l).exists()]


# ---------------------------------------------------------------- the wizard
class Wizard:
    W, H, SIDE, BAR = 660, 460, 200, 48

    def __init__(self, root):
        self.root, self.muted = root, False
        self.app, self.files, self.shortcuts = None, [], []
        self.plugin_target, self.plugin_was, self.ptt = None, False, None
        root.title(f"Установка — Канал 15 v{VERSION}")
        root.geometry(f"{self.W}x{self.H}")
        root.resizable(False, False)
        root.configure(bg=PAGE_BG)
        try:
            self.icon = tk.PhotoImage(file=str(ART / "icon.png"))
            root.iconphoto(True, self.icon)
            self.side_img = tk.PhotoImage(file=str(ART / "side_banner.png"))
        except tk.TclError:
            self.side_img = None
        body = tk.Frame(root, bg=PAGE_BG, height=self.H - self.BAR)
        body.pack(fill="both", expand=True)
        body.pack_propagate(False)
        side = tk.Label(body, image=self.side_img, bd=0, bg="#0b0e12", width=self.SIDE)
        side.pack(side="left", fill="y")
        self.page = tk.Frame(body, bg=PAGE_BG)
        self.page.pack(side="left", fill="both", expand=True, padx=(20, 18), pady=(18, 10))
        tk.Frame(root, height=1, bg="#a0a0a0").pack(fill="x")
        bar = tk.Frame(root, bg=BAR_BG, height=self.BAR)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        self.mute_btn = ttk.Button(bar, text="Выключить музыку", command=self.toggle, width=18)
        self.mute_btn.pack(side="left", padx=(10, 6), pady=10)
        tk.Label(bar, text="♪ Кардан — «Кардан крутится»", bg=BAR_BG, fg=GREY, font=F_SMALL).pack(side="left")
        bb = dict(width=11)
        self.cancel_btn = ttk.Button(bar, text="Отмена", command=self.cancel, **bb)
        self.cancel_btn.pack(side="right", padx=(6, 12), pady=10)
        self.next_btn = ttk.Button(bar, text="Далее >", command=self.next, **bb)
        self.next_btn.pack(side="right", pady=10)
        self.back_btn = ttk.Button(bar, text="< Назад", command=self.back, **bb)
        self.back_btn.pack(side="right", padx=(0, 2), pady=10)
        self.ui_q = queue.Queue()                     # worker thread -> UI (only the main thread touches Tk)
        self._pump()
        self.game_dirs, self.has_profile = game_found()
        slog(f"запуск установщика v{VERSION}; игра: {[str(d) for d in self.game_dirs]}, профиль: {self.has_profile}")
        self.dir = tk.StringVar(value=str(default_dir()))
        self.run_after = tk.BooleanVar(value=True)
        self.pages = [self.p_welcome, self.p_folder, self.p_install, self.p_plugin, self.p_ptt, self.p_mic, self.p_finish]
        self.mic_stream = None
        self.i = 0
        root.protocol("WM_DELETE_WINDOW", self.cancel)
        self.play()
        self.show()

    def _pump(self):
        try:
            while True:
                self.ui_q.get_nowait()()
        except queue.Empty:
            pass
        except Exception as e:  # noqa: BLE001  (a widget of a page already left)
            slog(f"ui: {e!r}")
        self.root.after(50, self._pump)

    def ui(self, fn):
        self.ui_q.put(fn)

    # ---- music
    def play(self):
        song = ART / "kardan_kruchitsya.wav"
        if song.exists() and not os.environ.get("CB_SETUP_SILENT"):
            winsound.PlaySound(str(song), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)

    def toggle(self):
        self.muted = not self.muted
        winsound.PlaySound(None, 0) if self.muted else self.play()
        self.mute_btn.config(text="Включить музыку" if self.muted else "Выключить музыку")

    # ---- page frame helpers
    def clear(self):
        for w in self.page.winfo_children():
            w.destroy()

    def title(self, text, sub=None):
        tk.Label(self.page, text=text, font=F_TITLE, bg=PAGE_BG, fg=TXT, anchor="w", justify="left",
                 wraplength=420).pack(fill="x")
        if sub:
            tk.Label(self.page, text=sub, font=F_TEXT, bg=PAGE_BG, fg=GREY, anchor="w", justify="left",
                     wraplength=420).pack(fill="x", pady=(2, 12))

    def text(self, t, **kw):
        lab = tk.Label(self.page, text=t, font=kw.pop("font", F_TEXT), bg=PAGE_BG, fg=kw.pop("fg", TXT), anchor="w",
                       justify="left", wraplength=420)
        lab.pack(fill="x", pady=kw.pop("pady", 3))
        return lab

    def buttons(self, back=True, nxt="Далее >", nxt_on=True, cancel=True):
        self.back_btn.config(state="normal" if back else "disabled")
        self.next_btn.config(text=nxt, state="normal" if nxt_on else "disabled")
        self.cancel_btn.config(state="normal" if cancel else "disabled")

    def show(self):
        self.clear()
        self.pages[self.i]()

    def next(self):
        hook = getattr(self, "_on_next", None)
        self._on_next = None
        if hook and hook() is False:
            return
        if self.i < len(self.pages) - 1:
            self.i += 1
            self.show()
        else:
            self.finish()

    def back(self):
        self._mic_close()
        if self.i > 0:
            self.i -= 1
            self.show()

    def cancel(self):
        if self.i == len(self.pages) - 1 or self.app is None or tk.messagebox.askyesno(
                "Канал 15", "Прервать настройку? Программа уже установлена, плагин и кнопку можно настроить "
                            "позже, запустив установщик ещё раз.", parent=self.root):
            winsound.PlaySound(None, 0)
            self.root.destroy()

    # ---- pages
    def p_welcome(self):
        self.title("Вас приветствует мастер установки «Канала 15»")
        self.text("«Канал 15» — мультиплеер для интровертов. Рация для одиночной игры в Euro Truck Simulator 2: водители-персонажи едут "
                  "своими рейсами, вы слышите тех, кто рядом, и можете ответить им голосом через тангенту на руле.", pady=(10, 6))
        self.text(f"Версия {VERSION}" + (f" от {VERSION_DATE[8:10]}.{VERSION_DATE[5:7]}.{VERSION_DATE[:4]}" if VERSION_DATE else "") + ".")
        self.text("Всё нужное уже внутри установщика: интернет не понадобится.")
        if self.game_dirs or self.has_profile:
            self.text("Перед установкой рекомендуется закрыть игру.")
        else:
            self.text("Euro Truck Simulator 2 на этом компьютере не найден. Рацию можно установить и сейчас, "
                      "но эфир начнётся только в игре. Плагин телеметрии тогда поставите позже: запустите "
                      "установщик ещё раз, когда игра будет установлена.", fg="#b06000", pady=(8, 3))
        self.text("Нажмите «Далее», чтобы продолжить, или «Отмена», чтобы выйти.", pady=(18, 3))
        self.buttons(back=False)

    def p_folder(self):
        self.title("Выбор папки установки", "В какую папку установить «Канал 15»?")
        self.text("Программа будет установлена в следующую папку. Чтобы выбрать другую, нажмите «Обзор».")
        row = tk.Frame(self.page, bg=PAGE_BG)
        row.pack(fill="x", pady=(10, 4))
        ttk.Entry(row, textvariable=self.dir, font=F_TEXT).pack(side="left", fill="x", expand=True, ipady=2)
        ttk.Button(row, text="Обзор…", command=self.browse).pack(side="left", padx=(6, 0))
        try:
            with zipfile.ZipFile(PAYLOAD) as z:
                size = sum(i.file_size for i in z.infolist()) / 1e6
        except (OSError, zipfile.BadZipFile) as e:
            slog(f"архив не читается: {e!r}")
            size = 0
        self.text(f"Требуется как минимум {size:.0f} МБ свободного места на диске.", fg=GREY, pady=(14, 3))
        self.text("Будут созданы ярлыки «Канал 15» на рабочем столе и в меню «Пуск». Права администратора "
                  "не нужны.", fg=GREY)
        self.buttons(nxt="Установить")

    def browse(self):
        d = filedialog.askdirectory(parent=self.root, title="Куда установить «Канал 15»")
        if d:
            p = Path(d)
            self.dir.set(str(p if p.name.lower() == "cb-radio" else p / "CB-Radio"))

    def p_install(self):
        self.title("Установка", "Подождите, пока «Канал 15» устанавливается на компьютер.")
        self.status = self.text("Распаковка файлов…")
        self.bar = ttk.Progressbar(self.page, mode="determinate", length=420)
        self.bar.pack(fill="x", pady=(6, 6))
        self.file_lab = self.text("", fg=GREY, font=F_SMALL)
        self.buttons(back=False, nxt_on=False, cancel=False)
        self._watch_t = time.monotonic()
        threading.Thread(target=self._extract, args=(Path(self.dir.get()),), daemon=True).start()
        self._watchdog()

    def _watchdog(self):
        """If the install thread is silent for 3 minutes, say so instead of a frozen page."""
        if self.app or self.i != 2 or not self.status.winfo_exists():
            return
        if time.monotonic() - self._watch_t > 180:
            self.status.config(text="Установка идёт дольше обычного. Возможно, антивирус проверяет файлы. "
                                    f"Если ничего не меняется, пришлите файл {LOG}", fg="#b06000")
        self.root.after(5000, self._watchdog)

    def _extract(self, dst):
        try:
            slog(f"установка в {dst}")
            stop_running_radio()
            dst.mkdir(parents=True, exist_ok=True)
            slog(f"архив: {PAYLOAD}")
            with zipfile.ZipFile(PAYLOAD) as z:
                items = [i for i in z.infolist() if not i.is_dir()]
                self.files = [i.filename for i in items]
                total, done = sum(i.file_size for i in items) or 1, 0
                last_ui = 0.0
                for i in items:
                    out = dst / i.filename
                    if out.name in KEEP and out.exists():
                        done += i.file_size
                        continue
                    out.parent.mkdir(parents=True, exist_ok=True)
                    # by chunks: the 480 MB Whisper model must move the bar too (2026-11-05: «движения нет»)
                    with z.open(i) as src, open(out, "wb") as f:
                        while True:
                            b = src.read(4 << 20)
                            if not b:
                                break
                            f.write(b)
                            done += len(b)
                            if time.monotonic() - last_ui > 0.25:
                                last_ui = self._watch_t = time.monotonic()
                                self.ui(lambda v=done * 100 / total, fn=i.filename: (
                                    self.bar.config(value=v), self.file_lab.config(text=fn[-70:])))
            slog(f"файлы распакованы: {len(items)}")
            self.ui(lambda: (self.status.config(text="Создаю ярлыки…"), self.file_lab.config(text="")))
            keep = dst.parent / "CB-Radio-настройки" / "config.json"      # kept by the uninstaller last time
            if keep.exists():
                shutil.copy2(keep, dst / "config.json")
            exe = dst / "CB-Radio.exe"
            desc = "Канал 15 — мультиплеер для интровертов (рация для ETS2)"
            self.shortcuts = make_shortcuts([
                (desktop_dir() / "Канал 15.lnk", exe, dst, "", desc),
                (start_menu() / "Канал 15.lnk", exe, dst, "", desc),
                (start_menu() / "Выключить Канал 15.lnk", exe, dst, "--quit", "Выключить рацию «Канал 15»")])
            slog(f"ярлыки: {self.shortcuts}")
            register_uninstall(dst, total / 1024)
            slog("установлено")
            self.app = dst
            self.ui(self._installed)
        except Exception as e:  # noqa: BLE001
            slog(f"ошибка установки: {e!r}")
            self.ui(lambda: (self.status.config(text=f"Не получилось: {e}", fg="#b00000"),
                             self.buttons(back=True, nxt_on=False)))

    def _installed(self):
        self.bar.config(value=100)
        self.status.config(text="Файлы установлены.")
        self.file_lab.config(text="")
        self._manifest()
        self.buttons(back=False)

    def _manifest(self):
        old = {}
        try:
            old = json.loads((self.app / "install.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        plugin = old.get("plugin_installed")
        if self.plugin_target and not self.plugin_was and self.plugin_target.exists():
            plugin = str(self.plugin_target)                 # we put it there -> the uninstaller may take it away
        (self.app / "install.json").write_text(json.dumps(
            {"files": self.files, "shortcuts": self.shortcuts, "plugin_installed": plugin}, ensure_ascii=False,
            indent=1), encoding="utf-8")

    def p_plugin(self):
        self.title("Плагин телеметрии", "По нему рация понимает, что вы едете, где вы и когда игра на паузе.")
        src = self.app / "installer" / "plugins" / "ets2-telemetry.dll"   # 1.06: the one that makes SimTelemetryETS2
        dirs = self.game_dirs
        self.game = getattr(self, "game", None) or (dirs[0] if dirs else None)
        self.plug_info = self.text("")
        row = tk.Frame(self.page, bg=PAGE_BG)
        row.pack(fill="x", pady=8)
        self.plug_btn = ttk.Button(row, text="Установить плагин", command=lambda: self._plugin_copy(src))
        self.plug_btn.pack(side="left")
        ttk.Button(row, text="Выбрать папку игры…", command=lambda: self._plugin_pick(src)).pack(side="left", padx=6)
        self.text("Игра должна быть закрыта. Этот шаг можно пропустить и вернуться к нему, запустив установщик ещё раз.",
                  fg=GREY, pady=(12, 3))
        self._plugin_show(src)
        self.buttons(back=False)

    def _plugin_show(self, src):
        if not self.game:
            self.plug_info.config(text="Игру найти не удалось. Если она установлена, укажите папку игры (ту, где "
                                       "лежит bin). Если игры пока нет, просто нажмите «Далее».", fg="#b06000")
            self.plug_btn.config(state="disabled")
            return
        t = self.game / "bin" / "win_x64" / "plugins" / src.name
        if self.plugin_target is None:
            self.plugin_target, self.plugin_was = t, t.exists()
        import gamecheck
        vc = gamecheck.vc_missing(self.game)
        same = t.exists() and t.read_bytes() == src.read_bytes() and not vc
        slog(f"плагин: {t} — {'на месте' if t.exists() else 'нет'}; не хватает Visual C++: {vc or 'нет'}")
        self.plug_info.config(text=f"Игра: {self.game}\n" + (
            "Плагин уже установлен — ничего делать не нужно." if same else
            "Плагин на месте, но ему не хватает Visual C++ 2012 — нажмите «Установить плагин»." if t.exists() else
            "Плагин ещё не установлен."), fg="#2e7d32" if same else TXT)
        self.plug_btn.config(state="disabled" if same else "normal")

    def _plugin_pick(self, src):
        d = filedialog.askdirectory(parent=self.root, title="Папка Euro Truck Simulator 2")
        if d:
            g = Path(d)
            g = g.parents[1] if g.name == "win_x64" else g
            if not (g / "bin" / "win_x64").exists():
                self.plug_info.config(text=r"В этой папке нет bin\win_x64 — это не папка игры.", fg="#b00000")
                return
            self.game, self.plugin_target = g, None
            self._plugin_show(src)

    def _plugin_copy(self, src):
        t = self.game / "bin" / "win_x64" / "plugins" / src.name
        try:
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, t)
            slog(f"плагин поставлен: {t}")
            import gamecheck                       # 1.04: Kirill's game showed the SDK dialog but never loaded it
            ok, msg = gamecheck.fix(src, src.parent / "vc", self.game)
            slog(f"Visual C++ для плагина: {msg}")
            if not ok:
                self.plug_info.config(text=msg, fg="#b00000")
                return
            try:                                   # 1.00-1.05 put the WRONG plugin in; remove it only if WE did
                old = json.loads((self.app / "install.json").read_text(encoding="utf-8")).get("plugin_installed") or ""
                if old.endswith(gamecheck.WRONG_PLUGIN) and Path(old).exists():
                    Path(old).unlink()
                    slog(f"убран неверный плагин прошлых версий: {old}")
            except (OSError, ValueError) as e:
                slog(f"старый плагин: {e!r}")
            self._manifest()
            self._plugin_show(src)
        except OSError as e:
            slog(f"плагин не встал: {e!r}")
            self.plug_info.config(text=f"Не получилось ({e.strerror}). Закройте игру и нажмите ещё раз.", fg="#b00000")

    def p_ptt(self):
        self.title("Кнопка рации", "Кнопка на руле, которую вы зажимаете, чтобы говорить в эфир.")
        self.text("Нажмите и отпустите нужную кнопку на руле или кнопочной панели.", pady=(4, 10))
        self.ptt_lab = self.text("Жду нажатия…", font=("Segoe UI", 11, "bold"))
        row = tk.Frame(self.page, bg=PAGE_BG)
        row.pack(fill="x", pady=8)
        ttk.Button(row, text="Ещё раз", command=self._ptt_reset).pack(side="left")
        cfg = self._cfg()
        if (cfg.get("ptt") or {}).get("button") is not None:
            self.text(f"Сейчас задано: {cfg['ptt'].get('device')}, кнопка {cfg['ptt'].get('button')}. "
                      "Нажмите «Далее», чтобы оставить как есть.", fg=GREY, pady=(10, 3))
        self.text("Без кнопки рацию можно слушать, но не отвечать.", fg=GREY)
        self._on_next = self._ptt_save
        self.buttons(back=True)
        self._ptt_reset()

    def _cfg(self):
        try:
            return json.loads((self.app / "config.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _ptt_reset(self):
        import ctypes
        try:
            ctypes.WinDLL("winmm").joyConfigChanged(0)
            self.ptt_base = ri.read_buttons()
        except OSError:
            self.ptt_base = {}
        self.ptt = None
        slog(f"кнопка рации: контроллеры {list(self.ptt_base.values())}")
        self.ptt_lab.config(text="Жду нажатия…" if self.ptt_base else "Руль не найден — подключите его и нажмите «Ещё раз».",
                            fg=TXT)
        self._ptt_poll()

    def _ptt_poll(self):
        if self.ptt or self.i != 4 or not self.ptt_lab.winfo_exists():
            return
        if not self.ptt_base:                 # no wheel: nothing to poll (press «Ещё раз» after plugging it in)
            return
        try:
            now = ri.read_buttons(ids=list(self.ptt_base))
        except OSError:
            now = {}
        for j, (name, b) in now.items():
            pressed = b & ~self.ptt_base.get(j, (name, 0))[1]
            if pressed:
                self.ptt = (name, (pressed & -pressed).bit_length() - 1)
                self.ptt_lab.config(text=f"✔ {self.ptt[0]}, кнопка {self.ptt[1]}", fg="#2e7d32")
                return
        self.root.after(40, self._ptt_poll)

    def _ptt_save(self):
        if self.ptt:
            cfg = self._cfg()
            cfg["ptt"] = {"device": self.ptt[0], "button": self.ptt[1]}
            (self.app / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=4), encoding="utf-8")

    # ---- microphone check (2026-11-05: Kirill pressed the key, nobody heard him)
    def p_mic(self):
        self.title("Микрофон", "Через него водители слышат, что вы говорите в рацию.")
        try:
            import sounddevice as sd
            import mic
            self.sd, self.mic = sd, mic
            ins = mic.inputs(sd)
            _, name, why = mic.pick(sd, (self._cfg().get("mic") or {}).get("device") or "")
        except Exception as e:  # noqa: BLE001
            slog(f"микрофон: список не читается {e!r}")
            self.text(f"Не удалось получить список микрофонов ({e}). Рация попробует выбрать сама.", fg="#b06000")
            self.buttons(back=True)
            return
        slog(f"микрофоны: {[n for _, n in ins]}; выбран {name} ({why})")
        if not ins:
            self.text("Микрофон не найден. Подключите его и нажмите «< Назад», затем «Далее». Без микрофона рацию "
                      "можно слушать, но водители не поймут, что вы говорите.", fg="#b06000", pady=(6, 3))
            self.buttons(back=True)
            return
        blocked = mic.privacy_blocked()
        if blocked:
            slog(f"микрофон: {blocked}")
            self.text(blocked, fg="#b00000", pady=(0, 4))
            ttk.Button(self.page, text="Открыть настройки микрофона",
                       command=lambda: os.startfile("ms-settings:privacy-microphone")).pack(anchor="w", pady=(0, 6))
        self.mic_names = [n for _, n in ins]
        self.mic_var = tk.StringVar(value=name if name in self.mic_names else self.mic_names[0])
        self.text("Выберите микрофон и скажите что-нибудь, например «Проверка связи».", pady=(2, 6))
        box = ttk.Combobox(self.page, textvariable=self.mic_var, values=self.mic_names, state="readonly", font=F_TEXT)
        box.pack(fill="x", pady=(0, 8))
        box.bind("<<ComboboxSelected>>", lambda e: self._mic_open())
        self.mic_bar = ttk.Progressbar(self.page, mode="determinate", length=420, maximum=60)
        self.mic_bar.pack(fill="x")
        self.mic_lab = self.text("", font=("Segoe UI", 10, "bold"), pady=(6, 3))
        self.text("Полоса должна прыгать, когда вы говорите. Если стоит на месте — выберите другой микрофон. "
                  "«Steam Streaming Microphone» и «Стерео микшер» — не настоящие микрофоны, они молчат. "
                  "Сменить микрофон можно и потом: правый клик по значку рации → Микрофон.", fg=GREY, pady=(8, 3))
        self._on_next = self._mic_save
        self.buttons(back=True)
        self._mic_open()
        self._mic_tick()

    def _mic_close(self):
        st, self.mic_stream = self.mic_stream, None
        if st is not None:
            try:
                st.stop()
                st.close()
            except Exception:  # noqa: BLE001
                pass

    def _mic_open(self):
        self._mic_close()
        self.mic_peak, self.mic_best = 0, -90.0
        name = self.mic_var.get()
        idx = next((i for i, n in self.mic.inputs(self.sd) if n == name), None)

        def cb(data, frames, t, status):
            a = array.array("h", bytes(data))
            if a:
                self.mic_peak = max(self.mic_peak, max(a), -min(a))
        try:
            sr = int(self.sd.query_devices(idx)["default_samplerate"])
            self.mic_stream = self.sd.RawInputStream(device=idx, channels=1, samplerate=sr, dtype="int16",
                                                     blocksize=sr // 20, callback=cb)
            self.mic_stream.start()
            self.mic_lab.config(text="Скажите что-нибудь…", fg=TXT)
        except Exception as e:  # noqa: BLE001
            slog(f"микрофон {name} не открылся: {e!r}")
            self.mic_lab.config(text=f"Этот микрофон не открылся ({e}). Выберите другой.", fg="#b00000")

    def _mic_tick(self):
        if self.i != 5 or not self.mic_bar.winfo_exists():
            self._mic_close()
            return
        p, self.mic_peak = self.mic_peak, 0
        db = 20 * math.log10(p / 32768) if p else -90.0
        self.mic_bar.config(value=max(0.0, db + 60))
        if self.mic_stream is not None and db > self.mic_best:
            self.mic_best = db
            if db > -45:
                self.mic_lab.config(text="✔ Слышу вас", fg="#2e7d32")
            elif db > -62:
                self.mic_lab.config(text="Слышу, но очень тихо — говорите громче или ближе к микрофону", fg="#b06000")
        self.root.after(80, self._mic_tick)

    def _mic_save(self):
        self._mic_close()
        cfg = self._cfg()
        cfg.setdefault("mic", {})["device"] = self.mic_var.get()
        slog(f"микрофон сохранён: {self.mic_var.get()} (лучший уровень {self.mic_best:.0f} дБ)")
        try:
            (self.app / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=4), encoding="utf-8")
        except OSError as e:
            slog(f"микрофон не сохранился: {e!r}")

    def p_finish(self):
        self.title("Завершение установки «Канала 15»")
        ptt = (self._cfg().get("ptt") or {})
        self.text("«Канал 15» установлен. Запускать его лучше ДО игры: окно, открытое поверх игры, ставит игру на паузу.",
                  pady=(10, 6))
        if ptt.get("button") is None:
            self.text("Кнопка рации не задана: слушать эфир можно, отвечать — нет. Её можно задать, запустив "
                      "установщик ещё раз.", fg="#b06000")
        tk.Checkbutton(self.page, text="Запустить «Канал 15»", variable=self.run_after, bg=PAGE_BG, activebackground=PAGE_BG,
                       font=F_TEXT, anchor="w").pack(fill="x", pady=(16, 3))
        self.text("Рация работает без окна: её значок — возле часов. Правый клик по нему — меню, там же "
                  "«Выключить рацию». Ещё выключить можно ярлыком «Выключить Канал 15» в меню «Пуск».", pady=(10, 3))
        self.text("Удалить программу можно в «Параметры → Приложения» или файлом Uninstall.exe в папке программы.",
                  fg=GREY, pady=(10, 3))
        self.buttons(back=False, nxt="Готово", cancel=False)

    def finish(self):
        slog("готово" + (", запускаю рацию" if self.run_after.get() else ""))
        if self.run_after.get() and self.app:
            subprocess.Popen([str(self.app / "CB-Radio.exe")], cwd=str(self.app), creationflags=0x00000010)
        winsound.PlaySound(None, 0)
        self.root.destroy()


if __name__ == "__main__":
    try:
        import pyi_splash  # noqa: F401  (closes the PyInstaller splash once the window is up)
        pyi_splash.close()
    except ImportError:
        pass
    import tkinter.messagebox  # noqa: F401
    root = tk.Tk()
    ttk.Style().theme_use("vista")
    Wizard(root)
    root.mainloop()
