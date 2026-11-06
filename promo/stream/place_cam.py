"""Камера стримера как у Кирилла (2026-11-06): портретное окно слева, поверх — рваная рамка scenes/cam_frame.png.
Правит текущий набор сцен «Канал 15» на месте (остальные правки пользователя не трогает). Запускать при закрытом OBS.
Камера — первый источник «Устройство захвата видео» (dshow_input) в наборе; 1280x720 обрезается до портрета."""
import copy
import json
import uuid
from pathlib import Path

COL = Path.home() / "AppData" / "Roaming" / "obs-studio" / "basic" / "scenes" / "Канал_15.json"
FRAME = Path(__file__).resolve().parent / "scenes" / "cam_frame.png"
SCENE = "В пути"
CAM_W, CAM_H = 1280, 720          # DroidCam
WIN = (246, 356)                  # окно в рамке (make_cam_frame.py INNER)
PAD = 32                          # отступ окна от края картинки рамки
AT = (24, 380)                    # левый верхний угол рамки в кадре 1920x1080
FACE_X = 0.70                     # где лицо по ширине кадра камеры (0..1): телефон стоит левее тебя
# 06.11 вечер: телефон поставлен ВЕРТИКАЛЬНО -> картинка DroidCam лежит на боку (макушка справа).
# ROT: поворот в OBS по часовой (270 = на 90° против часовой); 0 = телефон лёжа, старая обрезка по FACE_X.
ROT = 270
TOP = 160                         # для вертикального телефона: сколько срезать сверху (над головой), px повёрнутого кадра
# 06.11 17:45: поворот включён в самом DroidCam -> он отдаёт ровную вертикальную картинку 405x720 у ЛЕВОГО края
# кадра 1280x720, справа чёрное. Тогда поворот в OBS не нужен: CROP = (слева, справа, сверху, снизу) в px камеры.
PORTRAIT_W = 405
CROP = (0, CAM_W - PORTRAIT_W, 110, 720 - 110 - round(PORTRAIT_W * WIN[1] / WIN[0]))
ROT = 0

col = json.loads(COL.read_text(encoding="utf-8"))
src = {s["name"]: s for s in col["sources"]}
cam = next(s for s in col["sources"] if s["id"] == "dshow_input")
scene = src[SCENE]
items = scene["settings"]["items"]

# crop 1280x720 -> portrait with the face in the middle
it = next(i for i in items if i["source_uuid"] == cam["uuid"])
if ROT == 0 and CROP:
    cl, cr, ct, cb = CROP
    left, crop_w = cl, CAM_W - cl - cr
    scale = WIN[0] / crop_w
    it.update(crop_left=cl, crop_right=cr, crop_top=ct, crop_bottom=cb, rot=0.0, align=5,
              pos={"x": float(AT[0] + PAD), "y": float(AT[1] + PAD)}, scale={"x": scale, "y": scale},
              bounds_type=0, visible=True)
elif ROT in (90, 270):
    # rotated: the full 720 px width of the picture is the window width; its height comes out of the 1280 side
    h = round(CAM_H * WIN[1] / WIN[0])                     # 720 -> 1042
    top = max(0, min(CAM_W - h, TOP))
    # crops are in the camera's own (unrotated) pixels: for 270 the picture's top is the camera's right side
    cl, cr = (CAM_W - h - top, top) if ROT == 270 else (top, CAM_W - h - top)
    scale = WIN[0] / CAM_H
    left = cl
    it.update(crop_left=cl, crop_right=cr, crop_top=0, crop_bottom=0, rot=float(ROT), align=0,
              pos={"x": float(AT[0] + PAD + WIN[0] / 2), "y": float(AT[1] + PAD + WIN[1] / 2)},   # centre: no
              scale={"x": scale, "y": scale}, bounds_type=0, visible=True)                     # rotation surprises
    crop_w = CAM_W - cl - cr
else:
    crop_w = round(CAM_H * WIN[0] / WIN[1])
    cx = round(CAM_W * FACE_X)
    left = max(0, min(CAM_W - crop_w, cx - crop_w // 2))
    scale = WIN[1] / CAM_H
    it.update(crop_left=left, crop_right=CAM_W - crop_w - left, crop_top=0, crop_bottom=0, rot=0.0,
              pos={"x": float(AT[0] + PAD), "y": float(AT[1] + PAD)}, scale={"x": scale, "y": scale},
              bounds_type=0, align=5, visible=True)

# the frame picture, right above the camera in the item list (later in the list = drawn on top)
fr = src.get("Рамка камеры")
if not fr:
    img = next(s for s in col["sources"] if s["id"] == "image_source")
    fr = copy.deepcopy(img)
    fr.update(name="Рамка камеры", uuid=str(uuid.uuid4()), filters=[])
    col["sources"].append(fr)
fr["settings"] = {"file": str(FRAME).replace("\\", "/")}
items[:] = [i for i in items if i["source_uuid"] != fr["uuid"]]
fi = copy.deepcopy(it)
fi.update(name=fr["name"], source_uuid=fr["uuid"], crop_left=0, crop_right=0, crop_top=0, crop_bottom=0,
          pos={"x": float(AT[0]), "y": float(AT[1])}, scale={"x": 1.0, "y": 1.0}, rot=0.0, align=5,
          id=max(i["id"] for i in items) + 1)
items.insert(items.index(it) + 1, fi)
scene["settings"]["id_counter"] = max(i["id"] for i in items)


def sync_rel(i, w=1920, h=1080):
    """OBS 31+ (collection "version": 2) loads positions from the RELATIVE fields, not pos/scale (06.11: the camera
    kept jumping back to its old place). rel: centre of the canvas = 0, half the height = 1."""
    i["pos_rel"] = {"x": (i["pos"]["x"] - w / 2) / (h / 2), "y": (i["pos"]["y"] - h / 2) / (h / 2)}
    i["scale_rel"] = dict(i["scale"])
    i["bounds_rel"] = {"x": i["bounds"]["x"] / (h / 2), "y": i["bounds"]["y"] / (h / 2)}


MIRROR = True                     # 06.11: the user wants to see himself mirrored (OBS: «Отразить по горизонтали»)
if MIRROR and it["scale"]["x"] > 0 and it.get("align", 5) == 5 and not it.get("rot"):
    it["scale"]["x"] = -it["scale"]["x"]            # a negative width grows to the left of pos -> shift pos right
    it["pos"]["x"] += WIN[0]
sync_rel(it)
sync_rel(fi)
COL.write_text(json.dumps(col, ensure_ascii=False, indent=2), encoding="utf-8")
print("камера:", it["name"], "обрезка слева", left, "справа", CAM_W - crop_w - left, "масштаб", round(scale, 4))
print("порядок в сцене:", [i["name"] for i in items])
