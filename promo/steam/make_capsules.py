# -*- coding: utf-8 -*-
"""Капсулы Steam «Канал 15» из арта «стол с делами».
Основы: capsules/hero_raw.png (4:1), capsules/library_raw.png (2:3), article_b/cover_desk_raw.png.
Текст — только PIL (нейросеть кириллицу ломает). Правки: меняй параметры и перезапускай."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = Path(__file__).resolve().parent
CAP = ROOT / "capsules"
ART = ROOT.parents[0] / "article_b"
FONTS = ROOT.parents[0] / "design/Channel15_Design_Pack/fonts"
G = FONTS / "GolosText-Variable.ttf"
ORE = FONTS / "OrelegaOne-Regular.ttf"

CREAM = (241, 233, 215)
AMBER = (214, 154, 69)
INK = (17, 27, 24)

def font(sz, ore=False):
    return ImageFont.truetype(str(ORE if ore else G), sz)

def cover_crop(img, tw, th, focus=0.5):
    """кадрирование с фокусом по горизонтали (0=left,1=right)"""
    w, h = img.size
    tr = tw / th
    if w / h > tr:
        nw = int(h * tr)
        x0 = int((w - nw) * focus)
        return img.crop((x0, 0, x0 + nw, h)).resize((tw, th), Image.LANCZOS)
    nh = int(w / tr)
    y0 = (h - nh) // 2
    return img.crop((0, y0, w, y0 + nh)).resize((tw, th), Image.LANCZOS)

def shade_left(img, w_frac=0.62, alpha=170):
    """затемнение слева под текст"""
    w, h = img.size
    ov = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(ov)
    for x in range(w):
        a = int(alpha * max(0, 1 - x / (w * w_frac)) ** 1.3)
        d.line([x, 0, x, h], fill=a)
    black = Image.new("RGB", (w, h), (8, 10, 9))
    img.paste(black, (0, 0), ov)
    return img

def shade_top(img, h_frac=0.45, alpha=185):
    w, h = img.size
    ov = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(ov)
    for y in range(h):
        a = int(alpha * max(0, 1 - y / (h * h_frac)) ** 1.2)
        d.line([0, y, w, y], fill=a)
    black = Image.new("RGB", (w, h), (8, 10, 9))
    img.paste(black, (0, 0), ov)
    return img

def text(d, xy, s, f, fill, ls=0):
    """текст с трекингом ls (пиксели между буквами)"""
    x, y = xy
    for ch in s:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + ls
    return x

# ---------- 1. header 460x215 ----------
hero = Image.open(CAP / "hero_raw.png").convert("RGB")
hdr = cover_crop(hero, 460, 215, focus=0.98)      # детали стола справа
hdr = shade_left(hdr, 0.75, 200)
d = ImageDraw.Draw(hdr)
text(d, (24, 46), "КАНАЛ 15", font(52, ore=True), CREAM, 1)
d.rectangle([26, 112, 196, 115], fill=AMBER)
text(d, (26, 124), "KANAL 15", font(17), AMBER, 4)
text(d, (26, 152), "мультиплеер для интровертов", font(15), CREAM)
hdr = ImageEnhance.Contrast(hdr).enhance(1.03)
hdr.save(CAP / "header.png"); print("header.png 460x215")

# ---------- 2. small 231x87 (только название, крупно) ----------
sm = cover_crop(hero, 231, 87, focus=0.98)
sm = shade_left(sm, 0.9, 210)
d = ImageDraw.Draw(sm)
text(d, (14, 18), "КАНАЛ 15", font(34, ore=True), CREAM, 1)
d.rectangle([15, 60, 92, 62], fill=AMBER)
sm.save(CAP / "small.png"); print("small.png 231x87")

# ---------- 3. main 616x353 ----------
mn = cover_crop(hero, 616, 353, focus=0.92)
mn = shade_left(mn, 0.7, 195)
d = ImageDraw.Draw(mn)
text(d, (36, 118), "КАНАЛ 15", font(72, ore=True), CREAM, 2)
d.rectangle([38, 205, 258, 209], fill=AMBER)
text(d, (38, 222), "KANAL 15", font(23), AMBER, 5)
text(d, (38, 258), "мультиплеер для интровертов", font(21), CREAM)
mn = ImageEnhance.Contrast(mn).enhance(1.03)
mn.save(CAP / "main.png"); print("main.png 616x353")

# ---------- 4. library 600x900 ----------
lib = Image.open(CAP / "library_raw.png").convert("RGB")
lib = cover_crop(lib, 600, 900, focus=0.5)
lib = shade_top(lib, 0.42, 200)
d = ImageDraw.Draw(lib)
text(d, (44, 88), "КАНАЛ 15", font(88, ore=True), CREAM, 2)
d.rectangle([46, 196, 306, 201], fill=AMBER)
text(d, (46, 218), "живая трасса для одиночной ETS2", font(24), CREAM)
text(d, (46, 258), "мультиплеер для интровертов", font(22), AMBER)
# фирменный знак внизу: рамка-выноска у тангенты
d.rounded_rectangle([218, 812, 382, 856], 8, outline=AMBER, width=3)
text(d, (238, 821), "КАНАЛ 15", font(22, ore=True), AMBER, 1)
lib = ImageEnhance.Contrast(lib).enhance(1.03)
lib.save(CAP / "library.png"); print("library.png 600x900")

# ---------- 5. hero / library_hero 3840x1240 (чистый центр, мелкий лого справа) ----------
hv = cover_crop(hero, 3840, 1240, focus=0.86)
d = ImageDraw.Draw(hv)
text(d, (3560, 1150), "КАНАЛ 15", font(44, ore=True), CREAM, 2)   # мелкий лого внизу справа
hv.save(CAP / "hero.png"); print("hero.png 3840x1240")
