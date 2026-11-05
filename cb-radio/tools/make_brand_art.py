"""Надписи на фирменных картинках «Канала 15» (2026-11-04, слоган пользователя: «Мультиплеер для интровертов»).
Фоны без текста: installer_art/banner_1.png (широкий), vbanner_1.png (вертикальный). Старые версии -> *.before_tagline.png.
  installer_art/banner_final.png 640x200  (установщик, README) = promo/telegram/post1_banner.png
  installer_art/side_banner.png  200x412  (левая панель мастера установки)"""
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "installer_art"
TG = ROOT.parent / "promo" / "telegram"
F = "C:/Windows/Fonts/"
GOLD, WHITE, GREY = (242, 193, 78), (240, 240, 240), (190, 196, 206)
TITLE, TAG, SUB = "КАНАЛ 15", "Мультиплеер для интровертов", "рация для одиночной игры в ETS2"


def backup(p):
    b = p.with_name(p.stem + ".before_tagline.png")
    if p.exists() and not b.exists():
        shutil.copy2(p, b)


def shade(img, side="left", strength=0.8):
    w, h = img.size
    if side == "left":
        a = np.clip(1.15 - 1.9 * np.linspace(0, 1, w), 0, strength)[None, :].repeat(h, 0)
    else:                                   # top
        a = np.clip(1.1 - 2.2 * np.linspace(0, 1, h), 0, strength)[:, None].repeat(w, 1)
    return Image.composite(Image.new("RGB", (w, h), (8, 10, 16)), img, Image.fromarray((a * 255).astype(np.uint8), "L"))


def wide():
    src = Image.open(ART / "banner_1.png").convert("RGB")
    h = round(src.height * 640 / src.width)
    img = src.resize((640, h), Image.LANCZOS)
    top = (h - 200) // 2
    img = shade(img.crop((0, top, 640, top + 200)), "left")
    d = ImageDraw.Draw(img)
    d.text((24, 62), TITLE, font=ImageFont.truetype(F + "seguibl.ttf", 44), fill=GOLD)
    d.text((26, 118), TAG, font=ImageFont.truetype(F + "segoeuib.ttf", 21), fill=WHITE)
    d.text((26, 146), SUB, font=ImageFont.truetype(F + "segoeui.ttf", 15), fill=GREY)
    return img


def tall():
    src = Image.open(ART / "vbanner_1.png").convert("RGB")
    w = round(src.width * 412 / src.height)
    img = src.resize((w, 412), Image.LANCZOS)
    left = (w - 200) // 2
    img = shade(img.crop((left, 0, left + 200, 412)), "top", 0.85)
    d = ImageDraw.Draw(img)
    def center(y, text, font, fill):
        tw = d.textlength(text, font=font)
        d.text(((200 - tw) / 2, y), text, font=font, fill=fill)
    center(26, TITLE, ImageFont.truetype(F + "seguibl.ttf", 30), GOLD)
    head, tail = TAG.split(" ", 1)          # «Мультиплеер» / «для интровертов»: 200 px is too narrow for one line
    center(64, head, ImageFont.truetype(F + "segoeuib.ttf", 15), WHITE)
    center(82, tail, ImageFont.truetype(F + "segoeuib.ttf", 15), WHITE)
    center(106, "рация для одиночной игры", ImageFont.truetype(F + "segoeui.ttf", 11), GREY)
    center(120, "Euro Truck Simulator 2", ImageFont.truetype(F + "segoeui.ttf", 11), GREY)
    return img


def main():
    for p in (ART / "banner_final.png", ART / "side_banner.png", TG / "post1_banner.png"):
        backup(p)
    b = wide()
    b.save(ART / "banner_final.png")
    b.save(TG / "post1_banner.png")
    tall().save(ART / "side_banner.png")
    print("ok")


if __name__ == "__main__":
    main()
