"""OBS для записи под шортсы (2026-11-07): свой профиль и набор сцен, стримовые «Канал 15» не трогаются.
  профиль «Канал 15 — Шортсы»: кадр 2580x1080 (монитор 3440x1440 x0.75, квадрат 1080 из центра без потерь), 60 к/с,
    NVENC HEVC CQP 22, hybrid MP4, 4 дорожки звука, буфер повтора 90 с.
    F9 — сохранить последние 90 с («Клип ...»), Scroll Lock — старт/стоп полной записи («Запись ...»).
    Файлы -> promo/shorts/raw. Дорожки: 1 всё вместе, 2 микрофон, 3 только игра, 4 игра+рация.
  сцены «Канал 15 — Шортсы»: одна сцена «Запись» — чистая игра на весь кадр; оверлей рации есть, но скрыт
    (в шортсах свои субтитры с именами — оверлей бы дублировал их и резался квадратом).
Ярлыки на рабочем столе: «Канал 15 — запись» (сразу включает буфер повтора) и «Канал 15 — стрим».
Запускать только при закрытом OBS."""
import copy
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

OBS = Path(os.environ["APPDATA"]) / "obs-studio" / "basic"
BASE = Path(__file__).resolve().parents[1]
RAW = BASE / "shorts" / "raw"
W, H = 2580, 1080
PROFILE_DIR, PROFILE = "Канал15_Шортсы", "Канал 15 — Шортсы"
COLL_FILE, COLL = "Канал_15_Шортсы.json", "Канал 15 — Шортсы"
GAME_WIN = "Euro Truck Simulator 2:prism3d:eurotrucks2.exe"

if subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe", "/NH"], capture_output=True, text=True,
                  creationflags=0x08000000).stdout.lower().count("obs64.exe"):
    sys.exit("OBS открыт — закрой его и запусти ещё раз")


def U():
    return str(uuid.uuid4())


def rel(it):   # OBS 31+ (collection version 2) reads the relative fields: canvas centre = 0, half the height = 1
    it["pos_rel"] = {"x": (it["pos"]["x"] - W / 2) / (H / 2), "y": (it["pos"]["y"] - H / 2) / (H / 2)}
    it["scale_rel"] = dict(it["scale"])
    it["bounds_rel"] = {"x": it["bounds"]["x"] / (H / 2), "y": it["bounds"]["y"] / (H / 2)}
    return it


# ---------------------------------------------------------------- scene collection
base = json.loads((OBS / "scenes" / "Канал_15.json").read_text(encoding="utf-8"))
src_by = {s["name"]: s for s in base["sources"]}
col = {k: copy.deepcopy(v) for k, v in base.items() if k not in ("sources", "scene_order", "saved_projectors")}
col.update(name=COLL, groups=[], transitions=[], quick_transitions=[], saved_projectors=[], canvases=[],
           resolution={"x": W, "y": H}, migration_resolution={"x": W, "y": H}, current_scene="Запись",
           current_program_scene="Запись", scene_order=[{"name": "Запись"}])
desk, mic = col["DesktopAudioDevice1"], col["AuxAudioDevice1"]
for a in (desk, mic):
    a["uuid"] = U()
desk["name"], desk["mixers"] = "Игра и рация", 0b1001          # track 1 (mix) + track 4
mic["name"], mic["mixers"] = "Микрофон", 0b0011                # track 1 (mix) + track 2 (filters kept: RNNoise etc.)


def source(kind, name, settings, mixers=0, **kw):
    s = {"prev_ver": 553648129, "id": kind, "versioned_id": kind, "name": name, "uuid": U(), "settings": settings,
         "mixers": mixers, "sync": 0, "flags": 0, "volume": 1.0, "balance": 0.5, "enabled": True, "muted": False,
         "push-to-mute": False, "push-to-mute-delay": 0, "push-to-talk": False, "push-to-talk-delay": 0,
         "hotkeys": {}, "deinterlace_mode": 0, "deinterlace_field_order": 0, "monitoring_type": 0,
         "private_settings": {}, "filters": []}
    s.update(kw)
    return s


game = source("game_capture", "ETS2", copy.deepcopy(src_by["ETS2"]["settings"]))
game["settings"]["window"] = GAME_WIN
game_audio = source("wasapi_process_output_capture", "Звук игры (отдельно)",
                    {"window": GAME_WIN, "priority": 2}, mixers=0b0100)            # track 3 only
ov_src = src_by["Рация — оверлей"]
overlay = source("browser_source", "Рация — оверлей", copy.deepcopy(ov_src["settings"]), mixers=0)


def item(s, i, visible=True, bounds=None):
    it = {"name": s["name"], "source_uuid": s["uuid"], "visible": visible, "locked": False, "rot": 0.0,
          "scale_ref": {"x": float(W), "y": float(H)}, "align": 5, "bounds_type": 2 if bounds else 0,
          "bounds_align": 0, "bounds_crop": False, "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0,
          "id": i, "group_item_backup": False, "pos": {"x": 0.0, "y": 0.0}, "scale": {"x": 1.0, "y": 1.0},
          "bounds": {"x": float(bounds[0]), "y": float(bounds[1])} if bounds else {"x": 0.0, "y": 0.0},
          "scale_filter": "disable", "blend_method": "default", "blend_type": "normal",
          "show_transition": {"duration": 0}, "hide_transition": {"duration": 0}, "private_settings": {}}
    return rel(it)


ov_item = item(overlay, 3, visible=False)            # 1920x1080 page centred over the game when switched on
ov_item["pos"] = {"x": (W - 1920) / 2, "y": 0.0}
rel(ov_item)
scene = source("scene", "Запись", {"id_counter": 3, "custom_size": False,
                                   "items": [item(game, 1, bounds=(W, H)), item(game_audio, 2), ov_item]})
col["sources"] = [scene, game, game_audio, overlay]
(OBS / "scenes" / COLL_FILE).write_text(json.dumps(col, ensure_ascii=False, indent=4), encoding="utf-8")

# ---------------------------------------------------------------- profile
pd = OBS / "profiles" / PROFILE_DIR
pd.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)
raw = RAW.as_posix()
hk = lambda *keys: json.dumps({"bindings": [{"key": k} for k in keys]})  # noqa: E731
ini = f"""[General]
Name={PROFILE}

[Output]
Mode=Advanced
FilenameFormatting=Запись %CCYY-%MM-%DD %hh-%mm-%ss
DelayEnable=false
Reconnect=true

[SimpleOutput]
FilePath={raw}
RecFormat2=hybrid_mp4
RecRB=true
RecRBTime=90
RecRBPrefix=Клип

[AdvOut]
ApplyServiceSettings=true
TrackIndex=1
Encoder=obs_nvenc_h264_tex
RecType=Standard
RecFilePath={raw}
RecFormat2=hybrid_mp4
RecUseRescale=false
RecTracks=15
RecEncoder=obs_nvenc_hevc_tex
RecAudioEncoder=ffmpeg_aac
AudioEncoder=ffmpeg_aac
Track1Bitrate=192
Track2Bitrate=160
Track3Bitrate=160
Track4Bitrate=160
Track1Name=Всё вместе
Track2Name=Микрофон
Track3Name=Только игра
Track4Name=Игра и рация
RecRB=true
RecRBTime=90
RecRBSize=1536
RecRBPrefix=Клип
RecRBSuffix=
RecSplitFile=false

[Video]
BaseCX={W}
BaseCY={H}
OutputCX={W}
OutputCY={H}
FPSType=0
FPSCommon=60
ScaleType=lanczos
ColorFormat=NV12
ColorSpace=709
ColorRange=Partial

[Audio]
MonitoringDeviceId=default
SampleRate=48000
ChannelSetup=Stereo

[Hotkeys]
OBSBasic.SaveReplayBuffer={hk("OBS_KEY_F9")}
OBSBasic.StartRecording={hk("OBS_KEY_SCROLLLOCK")}
OBSBasic.StopRecording={hk("OBS_KEY_SCROLLLOCK")}
"""
(pd / "basic.ini").write_text(ini, encoding="utf-8-sig")
(pd / "recordEncoder.json").write_text(json.dumps(
    {"rate_control": "CQP", "cqp": 22, "preset2": "p5", "tune": "hq", "multipass": "qres", "profile": "main",
     "bf": 2, "keyint_sec": 2}), encoding="utf-8")

# ---------------------------------------------------------------- desktop shortcuts
exe = r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"
ps = ["$w=New-Object -ComObject WScript.Shell", "$d=[Environment]::GetFolderPath('Desktop')"]
for name, args in (("Канал 15 — запись", f'--profile "{PROFILE}" --collection "{COLL}" --startreplaybuffer'),
                   ("Канал 15 — стрим", '--profile "Канал 15" --collection "Канал 15"')):
    ps.append(f"$s=$w.CreateShortcut((Join-Path $d '{name}.lnk'));$s.TargetPath='{exe}';$s.Arguments='{args}';"
              f"$s.WorkingDirectory='{Path(exe).parent}';$s.IconLocation='{exe},0';$s.Save()")
ps.append("Write-Output $d")
ps1 = pd / "_shortcuts.ps1"
ps1.write_text("\n".join(ps), encoding="utf-8-sig")     # a file: no argument-quoting trouble with «» and quotes
r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
                   capture_output=True, text=True, creationflags=0x08000000)
ps1.unlink()
print("готово:", pd, "|", OBS / "scenes" / COLL_FILE, "| ярлыки:", r.stdout.strip() or r.stderr.strip()[:300])
