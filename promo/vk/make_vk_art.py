# -*- coding: utf-8 -*-
"""Оформление группы VK «Канал 15»: avatar.png (1024) и cover.png (1590x400).
Источники: promo/design/Channel15_Design_Pack (фон night, аватар, логотип)."""
import os
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACK = os.path.join(ROOT, "promo", "design", "Channel15_Design_Pack", "assets")
OUT = os.path.dirname(os.path.abspath(__file__))

FOREST = (34, 63, 47)
INK = (17, 27, 24)
CREAM = (241, 233, 215)
AMBER = (214, 154, 69)


def make_avatar(size=1024):
    src = Image.open(os.path.join(PACK, "avatar_800.png")).convert("RGBA")
    bg = Image.new("RGBA", (size, size), CREAM + (255,))
    mark = src.resize((size, size), Image.LANCZOS)
    bg.alpha_composite(mark)
    bg.convert("RGB").save(os.path.join(OUT, "avatar.png"), quality=95)
    # превью: как выглядит в кружочке VK
    prev = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    prev.paste(bg, (0, 0), mask)
    prev.save(os.path.join(OUT, "preview_avatar_circle.png"))


def make_cover(w=1590, h=400):
    src = Image.open(os.path.join(PACK, "background_night.jpg")).convert("RGB")
    # широкая ночная полоса: дорога с огнями встречки, y ~ 760..1031 из 1920
    band_h = int(src.width / (w / h))          # 1080 / 3.975 = 271
    y0 = 800
    crop = src.crop((0, y0, src.width, y0 + band_h))
    cover = crop.resize((w, h), Image.LANCZOS)
    cover = ImageEnhance.Contrast(cover).enhance(1.05)
    cover = ImageEnhance.Color(cover).enhance(1.1)

    # градиент слева для читаемости логотипа
    grad = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(grad)
    for x in range(w):
        a = int(215 * max(0.0, 1.0 - x / (w * 0.62)) ** 1.4)
        d.line((x, 0, x, h), fill=a)
    dark = Image.new("RGB", (w, h), INK)
    cover = Image.composite(dark, cover, grad)

    # лёгкая виньетка сверху/снизу
    vin = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(vin)
    for y in range(h):
        edge = min(y, h - y) / (h * 0.5)
        a = int(90 * max(0.0, 1.0 - edge) ** 2)
        d.line((0, y, w, y), fill=a)
    cover = Image.composite(Image.new("RGB", (w, h), INK), cover, vin)

    # логотип-вордмарк «КАНАЛ 15» (светлый)
    logo = Image.open(os.path.join(PACK, "logo_light.png")).convert("RGBA")
    lw = 760
    lh = int(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    cover_rgba = cover.convert("RGBA")
    lx, ly = 90, (h - lh) // 2
    # мягкая тень
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    alpha = logo.split()[3].point(lambda a: int(a * 0.55))
    black = Image.new("RGBA", logo.size, INK + (255,))
    black.putalpha(alpha)
    sh.paste(black, (lx + 4, ly + 6), black)
    sh = sh.filter(ImageFilter.GaussianBlur(6))
    cover_rgba.alpha_composite(sh)
    cover_rgba.alpha_composite(logo, (lx, ly))

    # янтарный акцент-черта под логотипом
    d = ImageDraw.Draw(cover_rgba)
    d.rounded_rectangle((lx + 6, ly + lh + 22, lx + 250, ly + lh + 30), 4, fill=AMBER)

    cover_rgba.convert("RGB").save(os.path.join(OUT, "cover.png"), quality=93)


if __name__ == "__main__":
    make_avatar()
    make_cover()
    for f in ("avatar.png", "cover.png"):
        im = Image.open(os.path.join(OUT, f))
        print(f, im.size)
