# -*- coding: utf-8 -*-
"""Подпись фамилий на ярлыки папок обложки. Источник: cover_desk_raw.png -> cover_desk.png.
Правка одной фамилии: поменяй текст в LABELS и перезапусти (нейрокадр не трогается)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "cover_desk_raw.png"
OUT = ROOT / "cover_desk.png"
FONT = ROOT.parents[0] / "design/Channel15_Design_Pack/fonts/GolosText-Variable.ttf"

# (текст, центр x, центр y, угол поворота, размер шрифта, цвет)
# Координаты — в пикселях cover_desk_raw.png (1200x896). Угол: по часовой, градусы.
INK = (43, 52, 84)      # синяя паста отдела кадров
INK2 = (58, 42, 28)     # коричневая
LABELS = [
    ("ЗАХАРОВ",  "И.П.", 225, 187, -3, 15, INK),   # бородатый в красной кабине — Борода
    ("СОМОВ",    "Н.М.", 220, 332, -3, 15, INK),   # пожилой в кепке — Михалыч
    ("КОВТУН",   "Г.М.", 215, 467, -4, 14, INK),   # блондинка — Сова
    ("МОРОЗОВ",  "С.А.", 210, 553, -4, 14, INK),   # тёмный бородатый — Тень
    ("САЗОНОВ",  "О.П.", 530, 368, 12, 14, INK),   # усатый — Палыч
    ("КАРАСЕВА", "З.П.", 547, 485, 12, 14, INK),   # седая — Петровна
    ("МИРОНОВ",  "А.А.", 707, 402,  8, 14, INK),   # молодой — Студент
    ("ВОЛКОВА",  "В.А.", 740, 552, -12, 14, INK),  # женщина с собакой (Граф) — Вера
]

def main():
    img = Image.open(RAW).convert("RGB")
    for fam, init, cx, cy, ang, size, color in LABELS:
        f = ImageFont.truetype(str(FONT), size)
        f2 = ImageFont.truetype(str(FONT), max(12, size - 5))
        tmp = Image.new("RGBA", (320, 110), (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        d.text((160, 8), fam, font=f, fill=color + (215,), anchor="ma")
        d.text((160, 16 + size), init, font=f2, fill=color + (205,), anchor="ma")
        bbox = tmp.getbbox()
        tmp = tmp.crop(bbox)
        tmp = tmp.rotate(ang, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
        img.paste(tmp, (int(cx - tmp.width / 2), int(cy - tmp.height / 2)), tmp)
    img.save(OUT)
    print(f"{OUT.name}: ok {len(LABELS)}")

if __name__ == "__main__":
    main()
