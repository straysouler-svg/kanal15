"""CB-рация: деинсталлятор (Uninstall.exe в папке программы, 2026-11-04). Removes every trace the installer left:
the program folder (logs, state), desktop + Start menu shortcuts, the «Programs and Features» entry, and the
telemetry plugin in the game - only if WE put it there (install.json says so). Settings can be kept."""
import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path

APP = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CB-Radio"
BG, FG = "#1d1f21", "#c5c8c6"


def manifest():
    try:
        return json.loads((APP / "install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def remove_registry():
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass


class Uninstall:
    def __init__(self, root):
        self.root, self.m = root, manifest()
        root.title("Канал 15 — удаление")
        root.geometry("520x300")
        root.resizable(False, False)
        root.configure(bg=BG)
        try:
            self.icon = tk.PhotoImage(file=str(APP / "installer" / "icon.png"))
            root.iconphoto(True, self.icon)
        except tk.TclError:
            pass
        tk.Label(root, text="Удалить «Канал 15»?", fg="#f0c674", bg=BG, font=("Segoe UI", 14, "bold")).pack(pady=(18, 4))
        tk.Label(root, text=str(APP), fg=FG, bg=BG, font=("Segoe UI", 9)).pack()
        self.plugin = tk.BooleanVar(value=bool(self.m.get("plugin_installed")))
        self.keep = tk.BooleanVar(value=False)
        opts = dict(bg=BG, fg=FG, selectcolor="#373b41", activebackground=BG, activeforeground=FG, font=("Segoe UI", 10))
        cb = tk.Checkbutton(root, text="Убрать плагин телеметрии из игры", variable=self.plugin, **opts)
        cb.pack(anchor="w", padx=40, pady=(16, 2))
        if not self.m.get("plugin_installed"):
            cb.config(state="disabled", text="Плагин телеметрии стоял до нас — его не трогаю")
        tk.Checkbutton(root, text="Оставить мои настройки (кнопка рации, config.json)", variable=self.keep,
                       **opts).pack(anchor="w", padx=40, pady=2)
        self.status = tk.Label(root, text="", fg="#81a2be", bg=BG, font=("Segoe UI", 9), wraplength=480)
        self.status.pack(pady=10)
        row = tk.Frame(root, bg=BG)
        row.pack(pady=4)
        b = dict(fg="white", relief="flat", padx=14, pady=5, font=("Segoe UI", 10))
        self.go = tk.Button(row, text="Удалить", command=self.uninstall, bg="#a54242", **b)
        self.go.pack(side="left", padx=6)
        tk.Button(row, text="Отмена", command=root.destroy, bg="#373b41", **b).pack(side="left", padx=6)

    def uninstall(self):
        self.go.config(state="disabled")
        notes = []
        # the radio may be running from this folder
        subprocess.run(["taskkill", "/F", "/IM", "CB-Radio.exe"], capture_output=True, creationflags=0x08000000)
        for lnk in self.m.get("shortcuts", []):
            try:
                Path(lnk).unlink(missing_ok=True)
            except OSError:
                notes.append(f"не удалил ярлык {lnk}")
        if self.plugin.get() and self.m.get("plugin_installed"):
            try:
                Path(self.m["plugin_installed"]).unlink(missing_ok=True)
            except OSError:
                notes.append("плагин занят игрой — закрой игру и удали его вручную: " + self.m["plugin_installed"])
        remove_registry()
        keep = APP.parent / "CB-Radio-настройки"
        if self.keep.get() and (APP / "config.json").exists():
            keep.mkdir(exist_ok=True)
            shutil.copy2(APP / "config.json", keep / "config.json")
            notes.append(f"настройки сохранены в {keep}")
        # only what the installer put here + what the radio itself creates; folders only if empty afterwards
        me = Path(sys.executable).resolve()
        made = ["cb_radio.log", "state.json", "world_state.json", "last_ptt.wav", "last_ptt_boosted.wav",
                "_foreign.wav", "_murmur.wav", "map/hazards.json", "install.json"]
        for rel in self.m.get("files", []) + made:
            f = APP / rel
            if f.resolve() == me:
                continue
            try:
                f.unlink(missing_ok=True)
            except OSError:
                notes.append(f"не удалил {rel}")
        # folders that only the radio and its updates fill (updates add files the install list doesn't know)
        if (APP / "CB-Radio.exe").exists() and APP.name.lower() == "cb-radio":
            import shutil
            for sub in ("update", "reports", "app", "audio", "phrases", "map", "installer", "models", "_internal"):
                shutil.rmtree(APP / sub, ignore_errors=True)
        for d in sorted((q for q in APP.rglob("*") if q.is_dir()), key=lambda q: -len(q.parts)):
            try:
                d.rmdir()                                  # only empty folders
            except OSError:
                pass
        subprocess.Popen(f'cmd /c ping -n 3 127.0.0.1 >nul & del /f /q "{me}" & rmdir "{APP}"', shell=True,
                         creationflags=0x08000000, cwd=os.environ.get("TEMP", "C:\\"))
        self.status.config(text="«Канал 15» удалён." + ("\n" + "\n".join(notes) if notes else ""), fg="#b5bd68")
        self.root.after(2500 if not notes else 8000, self.root.destroy)


if __name__ == "__main__":
    root = tk.Tk()
    Uninstall(root)
    root.mainloop()
