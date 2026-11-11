# -*- coding: utf-8 -*-
"""Локальная сборка арта статьи Б (план Б: нейросеть заблокирована 403).
Стол сверху: папки «личных дел» с фото водителей из promo/drivers_art/selected.
"""
import math, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

ROOT = Path(__file__).resolve().parent
SEL = ROOT.parents[0] / "drivers_art" / "selected"
OUT = ROOT
random.seed(15)

W, H = 1600, 1200

def wood(w, h):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    base = (56, 38, 26)
    d.rectangle([0, 0, w, h], fill=base)
    # продольные доски с шумом
    bw = w // 6
    for b in range(6):
        tone = random.randint(-10, 10)
        d.rectangle([b*bw, 0, (b+1)*bw, h], fill=tuple(max(0, c+tone) for c in base))
        for _ in range(380):
            x = random.randint(b*bw, (b+1)*bw-1); y = random.randint(0, h-1)
            ln = random.randint(20, 160)
            t = random.randint(-14, 8)
            d.line([x, y, min((b+1)*bw-1, x+2), min(h-1, y+ln)], fill=tuple(max(0, c+t) for c in base), width=1)
        d.line([(b+1)*bw-1, 0, (b+1)*bw-1, h], fill=(28, 18, 12), width=3)
    return img.filter(ImageFilter.GaussianBlur(0.6))

def lamp(img, cx, cy, radius, strength=1.0):
    """тёплый круг света + виньетка"""
    w, h = img.size
    overlay = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(overlay)
    steps = 60
    for i in range(steps, 0, -1):
        r = int(radius * i / steps)
        a = int(120 * strength * (1 - i/steps)**1.5)
        d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=a)
    warm = Image.new("RGB", (w, h), (255, 196, 120))
    img.paste(warm, (0, 0), overlay)
    # виньетка по краям
    vin = Image.new("L", (w, h), 0)
    dv = ImageDraw.Draw(vin)
    dv.rectangle([0, 0, w, h], fill=110)
    dv.ellipse([cx-int(w*0.75), cy-int(h*0.75), cx+int(w*0.75), cy+int(h*0.75)], fill=0)
    vin = vin.filter(ImageFilter.GaussianBlur(220))
    dark = Image.new("RGB", (w, h), (8, 6, 10))
    img.paste(dark, (0, 0), vin)
    return img

def shadow(canvas, box, blur=18, alpha=110):
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(box, 12, fill=(0, 0, 0, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(sh)

def folder(w, h, color=(196, 164, 110)):
    """папка-обложка с вкладкой"""
    f = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(f)
    d.rounded_rectangle([0, 18, w, h], 10, fill=color)
    d.rounded_rectangle([8, 0, int(w*0.42), 34], 8, fill=color)
    d.line([0, 20, w, 20], fill=tuple(max(0, c-28) for c in color), width=2)
    # потёртости
    for _ in range(120):
        x, y = random.randint(0, w-1), random.randint(20, h-1)
        d.point([x, y], fill=tuple(min(255, c+random.randint(-12, 14)) for c in color))
    return f

def polaroid(face_img, size=240, border=26):
    """мгновенный снимок: белая рамка, лицо крупно"""
    p = Image.new("RGBA", (size, size + border*2), (0, 0, 0, 0))
    d = ImageDraw.Draw(p)
    d.rounded_rectangle([0, 0, size-1, size + border*2 - 1], 4, fill=(238, 233, 220))
    f = face_img.convert("RGB").resize((size - 12, size - 12))
    mask = Image.new("L", f.size, 0)
    ImageDraw.Draw(mask).rectangle([0, 0, f.size[0], f.size[1]], fill=255)
    p.paste(f, (6, 6))
    return p

def paste_rot(canvas, item, cx, cy, angle):
    r = item.rotate(angle, expand=True, resample=Image.BICUBIC)
    canvas.alpha_composite(r, (int(cx - r.width/2), int(cy - r.height/2)))

def crop_face(name, box_rel):
    im = Image.open(SEL / f"{name}.png").convert("RGB")
    w, h = im.size
    box = (int(box_rel[0]*w), int(box_rel[1]*h), int(box_rel[2]*w), int(box_rel[3]*h))
    return im.crop(box)

def type_text(canvas, xy, text, size=30, color=(52, 42, 30), angle=0, font="GolosText-Variable.ttf"):
    fp = ROOT.parents[0]/"design/Channel15_Design_Pack/fonts"/font
    f = ImageFont.truetype(str(fp), size)
    t = Image.new("RGBA", (700, 90), (0, 0, 0, 0))
    ImageDraw.Draw(t).text((6, 6), text, font=f, fill=color)
    t = t.rotate(angle, expand=True, resample=Image.BICUBIC)
    canvas.alpha_composite(t, xy)

# области лиц в selected/*.png (доляи кадра)
FACES = {
    "boroda":   (0.10, 0.30, 0.85, 0.80),
    "mihalych": (0.22, 0.28, 0.85, 0.85),
    "lastochka":(0.05, 0.30, 0.85, 0.80),
    "palych":   (0.25, 0.30, 0.90, 0.80),
    "sova":     (0.15, 0.25, 0.95, 0.75),
    "vera":     (0.10, 0.25, 0.90, 0.85),
    "kardan":   (0.10, 0.25, 0.90, 0.85),
}

# ---------- обложка ----------
desk = wood(W, H).convert("RGBA")
items = []  # (surface, cx, cy, angle)

# папки
folders = [
    (folder(430, 330), 420, 380, -9),
    (folder(470, 350), 1080, 330, 6),
    (folder(400, 320), 780, 780, -4),
    (folder(430, 330), 1240, 830, 12),
    (folder(380, 300), 300, 900, 7),
]
for f, cx, cy, a in folders:
    shadow(desk, [cx-230, cy-160, cx+230, cy+170], 22, 120)
    paste_rot(desk, f, cx, cy, a)

# фото на папках
photos = [
    ("boroda", 415, 350, -12, 250),
    ("mihalych", 1090, 320, 8, 250),
    ("lastochka", 770, 750, -7, 235),
    ("palych", 1230, 800, 14, 245),
    ("sova", 300, 870, 9, 225),
]
for name, cx, cy, a, s in photos:
    pol = polaroid(crop_face(name, FACES[name]), size=s)
    shadow(desk, [cx-130, cy-130, cx+130, cy+140], 14, 100)
    paste_rot(desk, pol, cx, cy, a)

# атрибуты: карта Европы (схема), чек, ключи, зажигалка, кружка
d = ImageDraw.Draw(desk)
mapa = Image.new("RGBA", (380, 260), (0,0,0,0))
dm = ImageDraw.Draw(mapa)
dm.rounded_rectangle([0, 0, 379, 259], 6, fill=(222, 209, 178))
for _ in range(9):  # «маршруты»
    pts = [(random.randint(20, 360), random.randint(20, 240)) for _ in range(4)]
    dm.line(pts, fill=(150, 60, 48), width=3)
for _ in range(14):  # точки-города
    x, y = random.randint(20, 360), random.randint(20, 240)
    dm.ellipse([x-4, y-4, x+4, y+4], fill=(63, 74, 58))
dm.rectangle([186, 0, 192, 259], fill=(200, 186, 152))  # сгиб
shadow(desk, [620, 500, 1010, 770], 16, 100)
paste_rot(desk, mapa, 815, 635, -14)

# чек
chek = Image.new("RGBA", (150, 300), (0,0,0,0))
dc = ImageDraw.Draw(chek)
dc.polygon([(0,0),(150,0),(150,290),(140,300),(130,290),(120,300),(110,290),(100,300),(90,290),(80,300),(70,290),(60,300),(50,290),(40,300),(30,290),(20,300),(10,290),(0,300)], fill=(235, 230, 218))
for i in range(8):
    dc.line([18, 30+i*28, 132-random.randint(0,40), 30+i*28], fill=(150, 145, 135), width=4)
paste_rot(desk, chek, 1420, 480, 22)

# ключи
keys = Image.new("RGBA", (170, 100), (0,0,0,0))
dk = ImageDraw.Draw(keys)
for i, (x, y, r) in enumerate([(40, 50, 26), (95, 45, 20), (130, 62, 16)]):
    dk.ellipse([x-r, y-r, x+r, y+r], outline=(178, 160, 120), width=8)
    dk.line([x+r, y, x+r+34, y+18], fill=(178, 160, 120), width=8)
paste_rot(desk, keys, 560, 1010, -16)

# зажигалка
lig = Image.new("RGBA", (60, 110), (0,0,0,0))
dl = ImageDraw.Draw(lig)
dl.rounded_rectangle([6, 30, 54, 106], 8, fill=(168, 96, 60))
dl.rectangle([14, 8, 46, 32], fill=(150, 150, 155))
dl.rectangle([24, 0, 36, 10], fill=(120, 120, 125))
paste_rot(desk, lig, 1330, 1080, 30)

# кружка с чаем
mug = Image.new("RGBA", (180, 180), (0,0,0,0))
dm2 = ImageDraw.Draw(mug)
dm2.ellipse([20, 30, 140, 150], fill=(120, 58, 42))
dm2.ellipse([34, 44, 126, 136], fill=(74, 46, 30))  # чай
dm2.arc([120, 55, 175, 130], -80, 100, fill=(120, 58, 42), width=14)
paste_rot(desk, mug, 170, 640, -10)

# надписи на папках
type_text(desk, (300, 500), "ЛИЧНОЕ ДЕЛО № 07", 26, (74, 56, 36), -9)
type_text(desk, (960, 470), "ЛИЧНОЕ ДЕЛО № 12", 26, (74, 56, 36), 6)
type_text(desk, (660, 880), "ЛИЧНОЕ ДЕЛО № 15", 26, (74, 56, 36), -4)

cover = lamp(desk.convert("RGB"), W//2, H//2 - 40, 760, 1.0)
cover = ImageEnhance.Contrast(cover).enhance(1.04)
cover.save(OUT / "cover_desk.png")
print("cover_desk.png", cover.size)

# ---------- баннеры 21:9 ----------
BW, BH = 1600, 686
def banner_face(name, num, out):
    bg = wood(BW, BH).convert("RGBA")
    f = folder(560, 560)
    shadow(bg, [BW//2-300, BH//2-260, BW//2+300, BH//2+280], 26, 130)
    paste_rot(bg, f, BW//2, BH//2, -3)
    pol = polaroid(crop_face(name, FACES[name]), size=430, border=40)
    shadow(bg, [BW//2-220, BH//2-220, BW//2+230, BH//2+240], 16, 110)
    paste_rot(bg, pol, BW//2, BH//2 - 10, -4)
    type_text(bg, (BW//2-200, BH//2+190), f"ЛИЧНОЕ ДЕЛО № {num}", 40, (74, 56, 36), -3)
    img = lamp(bg.convert("RGB"), BW//2, BH//2, 620, 0.9)
    img.save(OUT / out)
    print(out, img.size)

banner_face("boroda", "07", "banner_face.png")
banner_face("sova", "03", "banner_mug.png")

night = Image.open(ROOT.parents[0]/"design/Channel15_Design_Pack/assets/background_night.jpg").convert("RGB")
radio = night.crop((0, 1130, 1080, 1600)).resize((BW, int(BW*470/1080)))
rh = radio.height
canvas = Image.new("RGB", (BW, BH), (10, 8, 12))
canvas.paste(radio, (0, (BH-rh)//2))
canvas = lamp(canvas, BW//2, BH//2, 700, 0.55)
canvas.save(OUT / "banner_radio.png"); print("banner_radio.png", canvas.size)

bg = wood(BW, BH).convert("RGBA")
mapa2 = Image.new("RGBA", (900, 560), (0,0,0,0))
dm3 = ImageDraw.Draw(mapa2)
dm3.rounded_rectangle([0, 0, 899, 559], 10, fill=(224, 211, 180))
for xx in (300, 600):
    dm3.rectangle([xx-3, 0, xx+3, 559], fill=(198, 184, 150))
cities = [(120, 140), (300, 90), (520, 180), (760, 120), (240, 380), (470, 420), (700, 350), (830, 470)]
route = [0, 2, 4, 6, 7]
for i in range(len(route)-1):
    a, b = cities[route[i]], cities[route[i+1]]
    dm3.line([a, b], fill=(150, 60, 48), width=6)
for x, y in cities:
    dm3.ellipse([x-9, y-9, x+9, y+9], fill=(63, 74, 58))
shadow(bg, [BW//2-470, BH//2-290, BW//2+470, BH//2+290], 24, 130)
paste_rot(bg, mapa2, BW//2, BH//2, -5)
type_text(bg, (BW//2-330, BH//2+170), "МАРШРУТ: ПРОВЕРЕНО ЛИЧНО", 44, (74, 56, 36), -5)
img = lamp(bg.convert("RGB"), BW//2, BH//2, 640, 0.9)
img.save(OUT / "banner_map.png"); print("banner_map.png", img.size)
