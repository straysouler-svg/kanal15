# PyInstaller spec: CB-Radio.exe (onedir). Built from G:\Claude\gruzovichki\cb-radio sources.
from PyInstaller.utils.hooks import collect_all
SRC = r"G:\Claude\gruzovichki\cb-radio"
datas, binaries, hidden = [], [], ["world", "intents", "company", "savegame", "tray", "mic", "gamecheck", "pystray._win32", "pystray._base", "PIL.Image", "PIL.ImageDraw"]
for pkg in ("faster_whisper", "ctranslate2", "sounddevice", "soundfile", "_sounddevice_data", "_soundfile_data", "onnxruntime", "tokenizers", "av"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hidden += h
    except Exception:
        pass
a = Analysis([SRC + r"\cb_radio.py"], pathex=[SRC, SRC + r"\tools"], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=["tkinter", "matplotlib", "pygame", "torch", "TTS", "IPython", "pytest"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CB-Radio", icon="cb_radio.ico", console=False,   # 2026-11-04: no window, the icon by the clock (tray.py)
          upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="CB-Radio", upx=False)
