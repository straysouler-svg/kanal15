"""Build a shareable copy of the radio (2026-11-04).
  pack_release.py kirill    -> G:\\Claude\\gruzovichki\\release\\kirill\\CB-Radio   (Кирилл / Сиди-Посиди)
  pack_release.py neutral   -> ...\\release\\neutral\\CB-Radio                     (no name, public)
What goes in: only what the radio plays (Opus .ogg, mono 48 kHz), the code, phrases json, city map, credits.
What never goes in: Сорока (Tatiana's voice is personal), API keys, the user's state/logs/fines map, sources,
backups, samples, music sources, game files. Lines that call the player «Железяка» are replaced by the variant;
if a line has no voiced variant yet it is left out (never ships the user's handle)."""
import json
import shutil
import sys
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
OUT_BASE = ROOT.parent / "release"
PERSONAL = {"soroka"}
CODE = ["cb_radio.py", "world.py", "intents.py", "company.py", "tools/savegame.py", "tray.py", "mic.py", "gamecheck.py",
        "updater.py", "ed25519.py", "launcher.py"]
HANDLE = {"kirill": "Сиди-Посиди", "alive": "Пятьдесят пятый", "neutral": ""}   # alive = blogger TheAlive55 (Алексей)
README = r"""# CB-рация для Euro Truck Simulator 2

Живой эфир дальнобойщиков: водители едут своими рейсами, ты слышишь тех, кто рядом,
и можешь отвечать им голосом через тангенту на руле. Обращения к игроку: {who}.
Во время игры интернет не нужен (только при установке и при первом нажатии тангенты).

## Установка
1. Python 3.11 или новее с python.org (при установке отметь «Add python.exe to PATH»).
2. Запусти «Установка.cmd»: один раз скачает библиотеки (около 1 ГБ).
3. Плагин телеметрии установщик положит сам (окно «Плагин телеметрии», игру перед этим закрой).
   По желанию: плагин SimHub (`SHETS2Telemetry_x64.dll`, ставится вместе с SimHub) даёт рации твой заказ и штрафы.
4. Кнопка тангенты: запусти «Проверка кнопки.cmd», нажми нужную кнопку на руле, впиши имя устройства и номер
   кнопки в `config.json` → `"ptt": {{"device": "...", "button": N}}`.
5. Микрофон: в `config.json` → `"mic"` → `"device"` впиши часть названия микрофона (пусто = микрофон по умолчанию).

## Запуск
«CB Radio.cmd» запускай ДО игры: окно, которое появилось поверх игры, ставит её на паузу.
При первом нажатии тангенты скачается модель распознавания речи (около 470 МБ, один раз).

## Благодарности
Музыка в кабинах: см. CREDITS.md. Карта городов: координаты из игры и © участники OpenStreetMap.
Голоса сгенерированы ИИ (ElevenLabs, OpenAI gpt-audio), песни — Google Lyria.
Только для личного некоммерческого использования.
"""


CACHE = Path(__file__).resolve().parents[2] / "build" / "opus_cache"
VARIANT = [None]


def opus(src, dst):
    """2026-11-05: an Opus file differs byte-for-byte on every encode (random stream serial), so every release
    re-sent ALL sounds to players (1.14: 83 MB). The same wav -> the same .ogg as last time, from the cache."""
    import hashlib
    key = hashlib.sha256(Path(src).read_bytes()).hexdigest()
    c = CACHE / (VARIANT[0] or "_") / key[:2] / (key + ".ogg")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not c.exists():
        x, sr = sf.read(src, dtype="float32")
        c.parent.mkdir(parents=True, exist_ok=True)
        tmp = c.with_name(key + ".tmp.ogg")
        sf.write(tmp, x, sr, format="OGG", subtype="OPUS")
        tmp.replace(c)
    shutil.copy2(c, dst.with_suffix(".ogg"))


def main(variant):
    assert variant in HANDLE, " | ".join(HANDLE)
    VARIANT[0] = variant
    out = OUT_BASE / variant / "CB-Radio"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    d = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    A = ROOT / "audio"
    var_dir = A / "variants" / variant
    handle_rel = set()
    for sid, ls in d["scenes"].items():
        handle_rel |= {f"scenes/{sid}/{i:02d}" for i, ln in enumerate(ls, 1) if "v_neutral" in ln}
    for g, ks in d["reactions"].items():
        if g.startswith("_"):
            continue
        for k, ls in ks.items():
            if not k.startswith("_"):
                handle_rel |= {f"reactions/{g}/{k}/{i:02d}" for i, ln in enumerate(ls, 1) if "v_neutral" in ln}
    n = skipped = 0
    for sub in ("level3", "scenes", "reactions", "fx"):
        for f in sorted((A / sub).rglob("*.wav")):
            rel = f.relative_to(A).with_suffix("").as_posix()
            parts = rel.split("/")
            if "_dry" in f.stem or not (f.stem.isdigit() or sub == "fx"):
                continue                                          # sources, dropped lines
            if any(p in PERSONAL for p in parts):
                continue                                          # Сорока's dirs
            if any(p.startswith("only_") and p != f"only_{variant}" for p in parts):
                continue                                          # another build's personal lines
            src = f
            if rel in handle_rel:
                v = var_dir / (rel + ".wav")
                if not v.exists():
                    skipped += 1
                    continue
                src = v
            elif sub in ("reactions", "scenes"):
                idx = f.parent / ("index.json" if sub == "reactions" else "scene.json")
                try:
                    acts = json.loads(idx.read_text(encoding="utf-8"))["actors"]
                    if acts[int(f.stem) - 1] in PERSONAL:
                        continue                                  # Сорока inside a shared reaction pool
                except (OSError, ValueError, KeyError, IndexError):
                    pass
            opus(src, out / "audio" / (rel + ".ogg"))
            n += 1
    for meta in list((A / "reactions").rglob("index.json")) + list((A / "scenes").rglob("scene.json")):
        rel = meta.relative_to(A)
        if any(p in PERSONAL for p in rel.parts):
            continue
        if any(p.startswith("only_") and p != f"only_{variant}" for p in rel.parts):
            continue
        (out / "audio" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(meta, out / "audio" / rel)
    # a scene with a missing line (a name call without a voiced variant) is dropped whole
    for sj in (out / "audio" / "scenes").rglob("scene.json"):
        acts = json.loads(sj.read_text(encoding="utf-8"))["actors"]
        if any(not (sj.parent / f"{i:02d}.ogg").exists() for i in range(1, len(acts) + 1)):
            print("  без сценки:", sj.parent.name)
            shutil.rmtree(sj.parent)
            d["scenes"].pop(sj.parent.name, None)
    # phrases: without Сорока (no driver, no roles); the radio reads actors/roles/schedules from it
    for k in PERSONAL:
        d["actors"].pop(k, None)
    for g in [g for g in d["reactions"] if g.startswith("only_") and g != f"only_{variant}"]:
        d["reactions"].pop(g)                                     # no other build's personal texts either
    d["player_handle"] = HANDLE[variant]
    (out / "phrases").mkdir()
    (out / "phrases" / "level3_eleven.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in CODE:
        (out / c).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / c, out / c)
    (out / "map").mkdir()
    shutil.copy2(ROOT / "map" / "cities_full.json", out / "map" / "cities_full.json")
    shutil.copy2(ROOT / "music" / "CREDITS.md", out / "CREDITS.md")
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    cfg["ptt"] = {"device": "", "button": None}
    cfg["mic"] = {"enabled": True, "device": "", "model": "small"}
    cfg.pop("variant", None)                 # names are baked into the audio files of this build
    cfg["build"] = variant                    # -> reactions/only_<build> (personal lines, e.g. Ласточка for Кирилл)
    chf = ROOT / "tools" / "update_channels.json"
    if chf.exists():                          # auto-update: where this build looks for new versions
        ch = json.loads(chf.read_text(encoding="utf-8"))
        cfg["update"] = {"url": f"https://storage.yandexcloud.net/{ch['bucket']}",
                         "channel": ch["channels"].get(variant, "public"), "auto": True}
    (out / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=4), encoding="utf-8")
    (out / "requirements.txt").write_text("numpy\nscipy\nsoundfile\nsounddevice\nfaster-whisper\npygame-ce\n",
                                          encoding="utf-8")
    # installer: a window with «Кардан крутится» playing and a mute button (user 2026-11-04: «это шедевр»)
    shutil.copy2(ROOT / "tools" / "release_installer.py", out / "installer.py")
    from math import gcd
    from scipy.signal import resample_poly
    x, sr = sf.read(ROOT / "music" / "lyria_src" / "rock_lyria_kardan.mp3", dtype="float32", always_2d=True)
    g_ = gcd(32000, sr)
    y = resample_poly(x.mean(axis=1), 32000 // g_, sr // g_)
    (out / "installer").mkdir()
    shutil.copy2(ROOT / "installer_art" / "banner_final.png", out / "installer" / "banner.png")
    shutil.copy2(ROOT / "installer_art" / "icon.png", out / "installer" / "icon.png")
    (out / "installer" / "plugins").mkdir()
    shutil.copy2(Path(r"G:\SteamLibrary\steamapps\common\Euro Truck Simulator 2\bin\win_x64\plugins")
                 / "ets2-telemetry.dll", out / "installer" / "plugins" / "ets2-telemetry.dll")   # makes SimTelemetryETS2
    sf.write(out / "installer" / "kardan_kruchitsya.wav", (y / (abs(y).max() + 1e-9) * 0.85).astype("float32"),
             32000, subtype="PCM_16")
    (out / "Установка.cmd").write_text(
        "@echo off\r\nchcp 65001 >nul\r\n"
        "where py >nul 2>nul || (echo Нужен Python 3.11+ с python.org, при установке отметь Add to PATH & pause & exit /b 1)\r\n"
        "start \"\" py -3w \"%~dp0installer.py\"\r\n", encoding="utf-8")
    for name, arg in (("CB Radio.cmd", ""), ("Проверка кнопки.cmd", " --ptt-test")):
        (out / name).write_text("@echo off\r\nchcp 65001 >nul\r\ntitle CB-рация (ETS2)\r\n"
                                f"\"%~dp0.venv\\Scripts\\python.exe\" -W ignore \"%~dp0cb_radio.py\"{arg}\r\npause\r\n",
                                encoding="utf-8")
    who = {"kirill": "Кирилл, Сиди-Посиди", "alive": "Алексей, Лёха, Пятьдесят пятый"}.get(variant, "без обращения по имени")
    (out / "README.md").write_text(README.format(who=who), encoding="utf-8")
    # never ship secrets / personal files
    bad = [p for p in out.rglob("*") if p.is_file() and (p.name.endswith("_key.txt") or p.name in
           ("state.json", "world_state.json", "hazards.json", "cb_radio.log", "last_ptt.wav"))]
    assert not bad, bad
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"{variant}: {n} звуков, пропущено без варианта {skipped}, размер {size / 1e6:.1f} МБ -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
