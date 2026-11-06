"""OBS для стримов «Канала 15» (2026-11-06): отдельный профиль и набор сцен, старые не трогаются.
  профиль  «Канал 15»  — кадр 1920x1080, 60 к/с, NVENC CBR 6000 (предел Twitch), звук 160
  сцены    «Канал 15»  — Скоро начнём / В пути / Перерыв / Конец
«В пути»: игра 21:9 вписана в 1920x804 по центру, поверх — оверлей рации http://127.0.0.1:47823/ (полосы 138 px).
Микрофон и захват игры — как в старом наборе пользователя (Безымянный.json). Запускать при закрытом OBS."""
import json
import shutil
import uuid
from pathlib import Path

OBS = Path.home() / "AppData" / "Roaming" / "obs-studio" / "basic"
BASE = Path(__file__).resolve().parents[1]
BANNER = BASE / "youtube" / "banner_2560x1440.png"
SONGS = BASE.parent / "cb-radio" / "Песни"
TG = "t.me/kanal15_ets2"


def U():
    return str(uuid.uuid4())


old = json.loads((OBS / "scenes" / "Безымянный.json").read_text(encoding="utf-8"))
mic_id = "{0.0.1.00000000}.{3137c7c8-f2b6-4cad-9492-cef6fb52550d}"   # Микрофон (fifine SC3); old collection pointed to a removed device

sources, order = [], []


def src(kind, name, settings, versioned=None, **extra):
    s = {"id": kind, "versioned_id": versioned or kind, "name": name, "uuid": U(), "settings": settings,
         "mixers": 255 if kind in ("ffmpeg_source", "browser_source") else 0, "sync": 0, "flags": 0, "volume": 1.0,
         "balance": 0.5, "enabled": True, "muted": False, "push-to-mute": False, "push-to-talk": False,
         "monitoring_type": 0, "private_settings": {}, "filters": []}
    s.update(extra)
    sources.append(s)
    return s


def item(s, i, x=0, y=0, bounds=None, scale=1.0):
    it = {"name": s["name"], "source_uuid": s["uuid"], "visible": True, "locked": False, "rot": 0.0,
          "scale_ref": {"x": 1920.0, "y": 1080.0}, "align": 5, "bounds_type": 0, "bounds_align": 0,
          "bounds_crop": False, "crop_left": 0, "crop_top": 0, "crop_right": 0, "crop_bottom": 0, "id": i,
          "group_item_backup": False, "pos": {"x": float(x), "y": float(y)}, "pos_rel": {"x": 0.0, "y": 0.0},
          "scale": {"x": scale, "y": scale}, "scale_rel": {"x": 1.0, "y": 1.0}, "bounds": {"x": 0.0, "y": 0.0},
          "bounds_rel": {"x": 0.0, "y": 0.0}, "scale_filter": "disable", "blend_method": "default",
          "blend_type": "normal", "show_transition": {"duration": 0}, "hide_transition": {"duration": 0},
          "private_settings": {}}
    if bounds:
        it.update(bounds_type=2, bounds={"x": float(bounds[0]), "y": float(bounds[1])})
    return it


def scene(name, items):
    s = src("scene", name, {"id_counter": len(items), "custom_size": False,
                            "items": [it for it in items]})
    order.append({"name": name})
    return s


def text(name, t, size, color=0xFFFFFFFF, bold=True):
    return src("text_gdiplus", name, {"text": t, "font": {"face": "Segoe UI", "size": size,
                                                         "style": "Bold" if bold else "Regular", "flags": 1 if bold else 0},
                                     "color": color, "align": "center", "outline": True, "outline_size": 4,
                                     "outline_color": 0xFF101010, "extents": False}, versioned="text_gdiplus_v3")


GOLD = 0xFF4EC1F2   # ABGR of #f2c14e
# (removed 06.11: scene screens are pictures now) banner = src("image_source", "Баннер Канал 15", {"file": str(BANNER).replace("\\", "/")})
music_start = src("ffmpeg_source", "Музыка: ожидание", {"local_file": str(SONGS / "Кардан — Кардан крутится.mp3").replace("\\", "/"),
                                                         "looping": True, "restart_on_activate": True}, volume=0.35)
music_break = src("ffmpeg_source", "Музыка: перерыв", {"local_file": str(SONGS / "Сова — Ой ты, ночь.mp3").replace("\\", "/"),
                                                        "looping": True, "restart_on_activate": True}, volume=0.35)
game = src("game_capture", "ETS2", {"capture_mode": "window", "window": "Euro Truck Simulator 2:prism3d:eurotrucks2.exe",
                                     "priority": 2, "capture_cursor": False, "allow_transparency": False})
radio = src("browser_source", "Рация — оверлей", {"url": "http://127.0.0.1:47823/", "width": 1920, "height": 1080,
                                                   "fps_custom": True, "fps": 30, "shutdown": False, "restart_when_active": False,
                                                   "reroute_audio": False, "css": ""})
# (removed 06.11: scene screens are pictures now) t_soon = text("Текст: скоро начнём", "Скоро начнём", 110, GOLD)
# (removed 06.11: scene screens are pictures now) t_soon2 = text("Текст: подзаголовок", "мультиплеер для интровертов · рация для одиночной игры в ETS2\nвопросы водителям — пишите в чат", 44)
# (removed 06.11: scene screens are pictures now) t_break = text("Текст: перерыв", "Перекур. Скоро вернёмся", 100, GOLD)
# (removed 06.11: scene screens are pictures now) t_end = text("Текст: конец", "Спасибо, что были в эфире!", 100, GOLD)
# (removed 06.11: scene screens are pictures now) t_end2 = text("Текст: ссылки", f"Канал 15 в Telegram: {TG}\nyoutube.com/@kanal15_ets2", 48)

# scene screens: one picture each, centred title + description, DIN-style Bahnschrift (scenes/*.png, 2026-11-06)
SC = Path(__file__).resolve().parent / "scenes"
img_soon = src("image_source", "Заставка: скоро начнём", {"file": str(SC / "scene_soon.png").replace("\\", "/")})
img_break = src("image_source", "Заставка: перерыв", {"file": str(SC / "scene_break.png").replace("\\", "/")})
img_end = src("image_source", "Заставка: конец", {"file": str(SC / "scene_end.png").replace("\\", "/")})
scene("Скоро начнём", [item(img_soon, 1, bounds=(1920, 1080)), item(music_start, 2)])
# donation alerts: the user's own DonationAlerts widget, URL taken from his old collection (never printed / stored here)
da_url = next((x["settings"].get("url", "") for x in old["sources"]
               if x["id"] == "browser_source" and "donationalerts.com/widget/alerts" in x["settings"].get("url", "")), "")
donat = src("browser_source", "Донаты (DonationAlerts)", {"url": da_url, "width": 800, "height": 600, "fps_custom": True,
                                                         "fps": 30, "shutdown": False, "reroute_audio": False,
                                                         "restart_when_active": False, "css": ""})
# donation goal bar «На голоса новых водителей» (DonationAlerts «Сбор средств»); URL kept in the private file .da_goal_url
goal_file = Path(__file__).resolve().parent / ".da_goal_url"
goal_url = goal_file.read_text(encoding="utf-8").strip() if goal_file.exists() else ""
goal = src("browser_source", "Сбор: голоса новых водителей", {"url": goal_url, "width": 1000, "height": 160, "fps_custom": True,
                                                              "fps": 30, "shutdown": False, "reroute_audio": False,
                                                              "restart_when_active": False, "css": ""})
# 1000x160 at 0.5 → 500x80 in the top-right of the game picture, under the radio bar (radio chips sit inside the bar itself)
# the streamer's camera (DroidCam, added by the user in OBS): carried over from the current collection;
# place_cam.py then puts it on the left in the ragged frame (as Kirill has it)
prev_col = OBS / "scenes" / "Канал_15.json"
prev = json.loads(prev_col.read_text(encoding="utf-8")) if prev_col.exists() else {"sources": []}
cams = [s for s in prev["sources"] if s["id"] == "dshow_input"]
sources.extend(cams)
scene("В пути", [item(game, 1, 0, 138, bounds=(1920, 804)), item(radio, 2), item(donat, 3, 560, 150),
                 item(goal, 4, 1920 - 500 - 24, 138 + 16, scale=0.5)] + [item(c, 5 + n) for n, c in enumerate(cams)])
scene("Перерыв", [item(img_break, 1, bounds=(1920, 1080)), item(music_break, 2)])
scene("Конец", [item(img_end, 1, bounds=(1920, 1080))])

col = {"name": "Канал 15", "current_scene": "Скоро начнём", "current_program_scene": "Скоро начнём",
       "scene_order": order, "sources": sources, "groups": [], "quick_transitions": [], "transitions": [],
       "current_transition": "Затухание", "transition_duration": 300, "saved_projectors": [], "preview_locked": False,
       "scaling_enabled": False, "scaling_level": 0, "scaling_off_x": 0.0, "scaling_off_y": 0.0, "modules": {},
       "DesktopAudioDevice1": {**old["DesktopAudioDevice1"], "uuid": U(), "name": "Игра и рация (fifine)",
                               "settings": {"device_id": "{0.0.0.00000000}.{621bd3e2-5165-46c5-a744-6a6cef2a210d}"}},
       "AuxAudioDevice1": {**old["AuxAudioDevice1"], "uuid": U(), "settings": {"device_id": mic_id}}}
out = OBS / "scenes" / "Канал_15.json"
out.write_text(json.dumps(col, ensure_ascii=False, indent=2), encoding="utf-8")
if cams:
    import runpy
    runpy.run_path(str(Path(__file__).with_name("place_cam.py")))

prof = OBS / "profiles" / "Канал15"
prof.mkdir(parents=True, exist_ok=True)
KEEP_INI = (prof / "basic.ini").exists()                # once made, the profile is the user's (Twitch login lives there)
ini = (OBS / "profiles" / "Безымянный" / "basic.ini").read_text(encoding="utf-8-sig")
ini = ini.replace("Name=Безымянный", "Name=Канал 15")
for a, b in (("BaseCX=3440", "BaseCX=1920"), ("BaseCY=1440", "BaseCY=1080"), ("OutputCX=1964", "OutputCX=1920"),
             ("OutputCY=822", "OutputCY=1080"), ("FPSCommon=60", "FPSCommon=60")):
    ini = ini.replace(a, b)
ini = "\n".join(l for l in ini.splitlines() if not l.startswith(("RefreshToken=", "Token=", "ExpireTime=")))
if not KEEP_INI:
    (prof / "basic.ini").write_text(ini + "\n", encoding="utf-8")
(prof / "streamEncoder.json").write_text(json.dumps({"rate_control": "CBR", "bitrate": 6000, "keyint_sec": 2,
                                                    "preset2": "p5", "profile": "high", "bf": 2}), encoding="utf-8")
src_service = OBS / "profiles" / "Безымянный" / "service.json"
if not (prof / "service.json").exists():                # keep the stream target the user / Claude set (Twitch)
    (prof / "service.json").write_text(json.dumps({"type": "rtmp_common", "settings": {"service": "Twitch",
                                                   "server": "auto", "protocol": "RTMPS", "use_auth": True}}), encoding="utf-8")
print("сцены:", out)
print("профиль:", prof)
