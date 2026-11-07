"""Вертикаль для стрима (Aitum Vertical 1.6.7, OBS 33, 2026-11-07): холст 1080x1920 в наборе «Канал 15».
  Верт: В пути        — 0..170 плашка оверлея, 170..1250 центр кабины квадратом, 1250..1500 субтитры (оверлей /v),
                        1500..1920 камера в рваной рамке по центру; донаты поверх игры.
  Верт: Скоро начнём / Перерыв / Конец — заставки стрима, вписанные по ширине на тёмном фоне.
Горизонтальные сцены не трогаются. Ключ YouTube вводится в настройках Aitum Vertical (здесь его нет).
Запускать при закрытом OBS."""
import copy
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

OBS = Path(os.environ["APPDATA"]) / "obs-studio"
COL = OBS / "basic" / "scenes" / "Канал_15.json"
AITUM = OBS / "plugin_config" / "vertical-canvas" / "config.json"
W, H = 1080, 1920
GAME_W, GAME_H = 3440, 1440
CANVAS_NAME = "Aitum Vertical"

if "obs64.exe" in subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe", "/NH"], capture_output=True,
                                 text=True, creationflags=0x08000000).stdout.lower():
    sys.exit("OBS открыт — закрой его и запусти ещё раз")


def U():
    return str(uuid.uuid4())


def rel(it):     # canvas-relative fields (OBS 31+): centre = 0, half the canvas height = 1
    it["pos_rel"] = {"x": (it["pos"]["x"] - W / 2) / (H / 2), "y": (it["pos"]["y"] - H / 2) / (H / 2)}
    it["scale_rel"] = dict(it["scale"])
    it["bounds_rel"] = {"x": it["bounds"]["x"] / (H / 2), "y": it["bounds"]["y"] / (H / 2)}
    return it


col = json.loads(COL.read_text(encoding="utf-8"))
(COL.with_name("Канал_15.before_vertical.json")).write_text(json.dumps(col, ensure_ascii=False, indent=4),
                                                           encoding="utf-8")
src = {s["name"]: s for s in col["sources"]}
canv = next((c for c in col.get("canvases") or [] if c["info"]["name"] == CANVAS_NAME), None)
if not canv:
    canv = {"info": {"name": CANVAS_NAME, "uuid": U(), "private": False, "flags": 14}}
    col.setdefault("canvases", []).append(canv)
CU = canv["info"]["uuid"]
# rebuild our vertical scenes from scratch on every run
col["sources"] = [s for s in col["sources"] if not (s["id"] == "scene" and s.get("canvas_uuid") == CU)
                  and s["name"] not in ("Верт: фон", "Рация — оверлей (верт.)")]
src = {s["name"]: s for s in col["sources"]}
main_cam_item = next(i for i in src["В пути"]["settings"]["items"] if i["name"] == "Устройство захвата видео")


def source(kind, name, settings, **kw):
    s = {"prev_ver": 553648129, "name": name, "uuid": U(), "id": kind, "versioned_id": kind, "settings": settings,
         "mixers": 0, "sync": 0, "flags": 0, "volume": 1.0, "balance": 0.5, "enabled": True, "muted": False,
         "push-to-mute": False, "push-to-mute-delay": 0, "push-to-talk": False, "push-to-talk-delay": 0,
         "hotkeys": {}, "deinterlace_mode": 0, "deinterlace_field_order": 0, "monitoring_type": 0,
         "monitoring_enabled": False, "private_settings": {}, "filters": []}
    s.update(kw)
    col["sources"].append(s)
    return s


bg = source("color_source_v3", "Верт: фон", {"color": 0xFF120C0A, "width": W, "height": H})
ov = source("browser_source", "Рация — оверлей (верт.)",
            {"url": "http://127.0.0.1:47823/v", "width": W, "height": H, "fps": 30, "fps_custom": True,
             "shutdown": False, "restart_when_active": False, "css": "", "reroute_audio": False})


def item(s, i, x=0.0, y=0.0, scale=1.0, crop=(0, 0, 0, 0), sx=None):
    it = {"name": s["name"], "source_uuid": s["uuid"], "visible": True, "locked": False, "rot": 0.0,
          "scale_ref": {"x": float(W), "y": float(H)}, "align": 5, "bounds_type": 0, "bounds_align": 0,
          "bounds_crop": False, "crop_left": crop[0], "crop_right": crop[1], "crop_top": crop[2],
          "crop_bottom": crop[3], "id": i, "group_item_backup": False, "pos": {"x": float(x), "y": float(y)},
          "scale": {"x": float(sx if sx is not None else scale), "y": float(scale)}, "bounds": {"x": 0.0, "y": 0.0},
          "scale_filter": "disable", "blend_method": "default", "blend_type": "normal",
          "show_transition": {"duration": 0}, "hide_transition": {"duration": 0}, "private_settings": {}}
    return rel(it)


def scene(name, items, order):
    return source("scene", name, {"id_counter": len(items), "custom_size": False, "items": items, "order": order,
                                  "canvas_active": True}, canvas_uuid=CU, hotkeys={"OBSBasic.SelectScene": []})


# --- «В пути»: centre of the cab as a square
side = (GAME_W - GAME_H) // 2
game = item(src["ETS2"], 2, 0, 170, W / GAME_H, (side, side, 0, 0))
# camera: same crop / scale / mirror as on the horizontal stream, the frame centred at the bottom
FR_AT = ((W - 310) // 2, 1500)
main_fr = next(i for i in src["В пути"]["settings"]["items"] if i["name"] == "Рамка камеры")
dx, dy = FR_AT[0] - main_fr["pos"]["x"], FR_AT[1] - main_fr["pos"]["y"]   # keep the camera inside the frame as on the stream
cam = copy.deepcopy(main_cam_item)
cam.update(id=4, scale_ref={"x": float(W), "y": float(H)},
           pos={"x": main_cam_item["pos"]["x"] + dx, "y": main_cam_item["pos"]["y"] + dy})
rel(cam)
frame = item(src["Рамка камеры"], 5, *FR_AT)
dono = item(src["Донаты (DonationAlerts)"], 6, (W - 800) / 2, 420)
on_road = [item(bg, 1), game, item(ov, 3), cam, frame, dono]
scene("Верт: В пути", on_road, 1)

# --- title cards: the horizontal 1920x1080 picture fitted to the width
k = W / 1920
for n, (name, img) in enumerate((("Верт: Скоро начнём", "Заставка: скоро начнём"), ("Верт: Перерыв", "Заставка: перерыв"),
                                 ("Верт: Конец", "Заставка: конец")), 2):
    scene(name, [item(bg, 1), item(src[img], 2, 0, (H - 1080 * k) / 2, k), item(dono_src := src["Донаты (DonationAlerts)"], 3,
                                                                              (W - 800) / 2, 300)], n)
# scene order inside the vertical canvas: Скоро начнём, В пути, Перерыв, Конец
for s in col["sources"]:
    if s.get("canvas_uuid") == CU and s["id"] == "scene":
        s["settings"]["order"] = {"Верт: Скоро начнём": 0, "Верт: В пути": 1, "Верт: Перерыв": 2, "Верт: Конец": 3}[s["name"]]
COL.write_text(json.dumps(col, ensure_ascii=False, indent=4), encoding="utf-8")

# --- Aitum settings: NVENC (never x264 while the game runs), 1080x1920, start on «Скоро начнём»
cfg = json.loads(AITUM.read_text(encoding="utf-8"))
(AITUM.with_name("config.before_kanal15.json")).write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
c = cfg["canvas"][0]
c.update(width=W, height=H, current_scene="Верт: Скоро начнём", streaming_match_main=False,
         streaming_video_bitrate=9000, audio_bitrate=160, stream_advanced_settings=True,
         stream_encoder="obs_nvenc_h264_tex",
         stream_encoder_settings={"rate_control": "CBR", "bitrate": 9000, "preset2": "p5", "tune": "hq",
                                  "multipass": "qres", "profile": "high", "keyint_sec": 2, "bf": 2},
         backtrack=False)
AITUM.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
print("готово: 4 вертикальные сцены в «Канал 15»; Aitum: NVENC 9000 кбит/с; ключ YouTube — в настройках Aitum")
