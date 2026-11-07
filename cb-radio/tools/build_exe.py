"""Build the one-file installer (2026-11-04). Run with the BUILD venv (G:\\Claude\\gruzovichki\\build\\venv):
  build_exe.py kirill | neutral
Needs: release/<variant>/CB-Radio made by pack_release.py (the air in Opus, phrases, map, config, plugin, art).
Steps: PyInstaller CB-Radio.exe (onedir) -> fix old VC runtime DLLs -> app folder + whisper-small model ->
payload.zip -> PyInstaller CB-Radio-Setup*.exe (onefile, windowed, splash) with payload inside."""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

CB = Path(__file__).resolve().parents[1]
BASE = CB.parent
BUILD = BASE / "build"
PY = BUILD / "venv" / "Scripts" / "python.exe"
MODEL = next((Path.home() / ".cache" / "huggingface" / "hub" / "models--Systran--faster-whisper-small" / "snapshots").glob("*"))
SYS32 = Path(r"C:\Windows\System32")
PYI_COOKIE = b"MEI\x0c\x0b\x0a\x0b\x0e"
import json as _json
VER = _json.loads((CB / "version.json").read_text(encoding="utf-8"))
README = """# Канал 15 — мультиплеер для интровертов

Версия {ver} от {date}. Что нового — CHANGELOG.md.

Рация для одиночной игры в Euro Truck Simulator 2. Никаких чужих людей, но и тишины в кабине не будет: по трассе едут водители-персонажи
со своими рейсами, ты слышишь тех, кто рядом, и можешь ответить им голосом через тангенту на руле. {who}

Запуск: ярлык «Канал 15» на рабочем столе. Запускай ДО игры (окно поверх игры ставит её на паузу).
Кнопку рации и плагин телеметрии можно настроить заново: запусти установщик ещё раз (настройки не сотрутся).
Интернет не нужен.
Проект бесплатный. Если захочется поддержать — пункт «☕ На токены и хлебушек» в меню значка рации.

Музыка в кабинах: см. CREDITS.md. Карта городов: координаты из игры и © участники OpenStreetMap.
Голоса сгенерированы ИИ (ElevenLabs, OpenAI gpt-audio), песни — Google Lyria. Распознавание речи — Whisper (MIT).
Только для личного некоммерческого использования.
"""


def run(args, cwd=BUILD):
    print(">", " ".join(map(str, args)), flush=True)
    subprocess.run(args, cwd=cwd, check=True)


def build_radio():
    run([PY, "-m", "PyInstaller", "--noconfirm", "--log-level", "ERROR", "radio.spec"])
    internal = BUILD / "dist" / "CB-Radio" / "_internal"
    for dll in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "msvcp140_1.dll", "msvcp140_2.dll"):
        if (internal / dll).exists() and (SYS32 / dll).exists():
            shutil.copy2(SYS32 / dll, internal / dll)         # PyInstaller picked a 2016 copy that crashes


def build_uninstaller():
    spec = BUILD / "uninstall.spec"
    spec.write_text(f"""
a = Analysis([r"{CB / 'tools' / 'uninstall_app.py'}"], pathex=[r"{CB}"], hiddenimports=["gamecheck"],
             excludes=["numpy", "scipy"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Uninstall", icon=r"{BUILD / 'cb_radio.ico'}",
          console=False, upx=False)
""", encoding="utf-8")
    run([PY, "-m", "PyInstaller", "--noconfirm", "--log-level", "ERROR", str(spec)])


def build_app(variant):
    rel = BASE / "release" / variant / "CB-Radio"
    app = BUILD / f"app_{variant}"
    if app.exists():
        shutil.rmtree(app)
    shutil.copytree(BUILD / "dist" / "CB-Radio", app)
    (app / "app").mkdir()                       # the radio's own code: plain .py, updated without touching any exe
    for mod in ("cb_radio", "world", "intents", "company", "tray", "mic", "gamecheck", "updater", "ed25519", "overlay",
                "bonds", "tainik"):
        shutil.copy2(CB / f"{mod}.py", app / "app" / f"{mod}.py")
    shutil.copy2(CB / "tools" / "savegame.py", app / "app" / "savegame.py")
    for part in ("audio", "phrases", "map", "config.json", "CREDITS.md"):
        src = rel / part
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, app / part)
    (app / "installer" / "plugins").mkdir(parents=True)
    shutil.copy2(rel / "installer" / "plugins" / "ets2-telemetry.dll", app / "installer" / "plugins")
    (app / "installer" / "plugins" / "vc").mkdir()        # Visual C++ 2012 x64 for the plugin (app-local copy)
    shutil.copy2(SYS32 / "msvcr110.dll", app / "installer" / "plugins" / "vc" / "msvcr110.dll")
    shutil.copy2(rel / "installer" / "icon.png", app / "installer" / "icon.png")
    shutil.copy2(BUILD / "dist" / "Uninstall.exe", app / "Uninstall.exe")
    shutil.copytree(MODEL, app / "models" / "whisper-small")
    who = {"kirill": "Обращения к игроку: Кирилл, Сиди-Посиди.",
           "alive": "Обращения к игроку: Алексей, Лёха, «Пятьдесят пятый»."}.get(variant, "Водители обращаются к тебе без имени.")
    (app / "README.md").write_text(README.format(who=who, ver=VER["version"], date=VER["date"]), encoding="utf-8")
    shutil.copy2(CB / "version.json", app / "version.json")
    shutil.copy2(CB / "CHANGELOG.md", app / "CHANGELOG.md")
    return app


def build_payload(app, variant):
    pz = BUILD / f"payload_{variant}.zip"
    with zipfile.ZipFile(pz, "w") as z:
        for f in sorted(app.rglob("*")):
            if f.is_file():
                # 1.02: everything but Opus is deflated. Besides size, this hides the PyInstaller cookies of
                # CB-Radio.exe / Uninstall.exe: the payload now sits at the END of the setup exe and the bootloader
                # looks for its own cookie from the end — a stored inner exe would be found first.
                store = f.suffix == ".ogg"
                z.write(f, f.relative_to(app), compress_type=zipfile.ZIP_STORED if store else zipfile.ZIP_DEFLATED,
                        compresslevel=None if store else 6)
    if PYI_COOKIE in pz.read_bytes():
        raise SystemExit("в payload видна метка PyInstaller — установщик не запустится")
    print("payload", round(pz.stat().st_size / 1e6), "MB")
    return pz


def build_setup(variant, payload):
    rel = BASE / "release" / variant / "CB-Radio"
    art = BUILD / "art"
    if art.exists():
        shutil.rmtree(art)
    art.mkdir()
    for f in ("banner.png", "icon.png", "kardan_kruchitsya.wav"):
        shutil.copy2(rel / "installer" / f, art / f)
    shutil.copy2(CB / "installer_art" / "side_banner.png", art / "side_banner.png")
    shutil.copy2(CB / "version.json", art / "version.json")
    tag = {"kirill": "-Kirill", "alive": "-Alexey"}.get(variant, "")      # personal builds carry the owner's name
    name = f"Kanal15-Setup{tag}-v{VER['version']}"
    spec = BUILD / f"setup_{variant}.spec"
    spec.write_text(f'''
a = Analysis([r"{CB / "tools" / "setup_app.py"}"], pathex=[r"{CB / "tools"}", r"{CB}"],
             hiddenimports=["release_installer", "mic", "gamecheck", "sounddevice", "_sounddevice_data"],
             datas=[(r"{art}", "art")], excludes=["numpy", "scipy"])
a.datas = [d for d in a.datas]
splash = Splash(r"{art / "banner.png"}", binaries=a.binaries, datas=a.datas, text_pos=(24, 188), text_size=9,
                text_color="#c5c8c6", text_default="Запускаю установщик…")
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, splash, splash.binaries, a.binaries, a.datas, [], name="{name}", icon=r"{BUILD / "cb_radio.ico"}",
          console=False, upx=False)
''', encoding="utf-8")
    run([PY, "-m", "PyInstaller", "--noconfirm", "--log-level", "ERROR", str(spec)])
    out = BUILD / "dist" / f"{name}.exe"
    final = BASE / "release" / f"{name}.exe"
    with open(final, "wb") as dst:                       # setup exe + program archive appended (read in place)
        for part in (out, payload):
            with open(part, "rb") as src:
                shutil.copyfileobj(src, dst, 16 << 20)
    with zipfile.ZipFile(final) as z:                    # the archive must open from the exe
        assert z.testzip() is None, "архив в установщике повреждён"
    print("SETUP:", final, round(final.stat().st_size / 1e6), "MB")


if __name__ == "__main__":
    variant = sys.argv[1]
    if "--skip-radio" not in sys.argv:
        build_radio()
    if "--app-only" in sys.argv:              # an update: refresh build/app_<variant> only, then publish_update.py
        build_app(variant)
        print("APP:", BUILD / f"app_{variant}")
        sys.exit(0)
    build_uninstaller()
    app = build_app(variant)
    build_setup(variant, build_payload(app, variant))
