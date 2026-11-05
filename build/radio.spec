# PyInstaller spec: CB-Radio.exe (onedir). Built from G:\Claude\gruzovichki\cb-radio sources.
from PyInstaller.utils.hooks import collect_all
SRC = r"G:\Claude\gruzovichki\cb-radio"
# 2026-11-05: CB-Radio.exe is a STABLE launcher (launcher.py). Our own modules live as .py files in app/ (copied by
# build_exe.build_app) so updates never replace an exe. They are analysed here for their dependencies, then dropped from PYZ.
OURS = ["cb_radio", "world", "intents", "company", "savegame", "tray", "mic", "gamecheck", "updater", "ed25519"]
datas, binaries, hidden = [], [], OURS + ["runpy", "pystray._win32", "pystray._base", "PIL.Image", "PIL.ImageDraw"]
for pkg in ("faster_whisper", "ctranslate2", "sounddevice", "soundfile", "_sounddevice_data", "_soundfile_data", "onnxruntime", "tokenizers", "av"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hidden += h
    except Exception:
        pass
a = Analysis([SRC + r"\launcher.py"], pathex=[SRC, SRC + r"\tools"], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=["tkinter", "matplotlib", "pygame", "torch", "TTS", "IPython", "pytest"],
             noarchive=False)
a.pure = [x for x in a.pure if x[0] not in OURS]          # they come from app/*.py, not from the exe
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CB-Radio", icon="cb_radio.ico", console=False,   # 2026-11-04: no window, the icon by the clock (tray.py)
          upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="CB-Radio", upx=False)
