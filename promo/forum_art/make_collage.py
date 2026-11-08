# Сборка коллажа «весь состав» из утверждённых портретов promo/drivers_art/selected/.
# Сетка 6x3, карточка: портрет 928x1152 -> 464x576, снизу плашка с позывным.
# Запуск: G:/Claude/gruzovichki/build/venv/Scripts/python.exe make_collage.py
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "drivers_art" / "selected"
OUT = HERE / "collage_all.png"

CALLSIGNS = {
    "bahti": "Бахти", "boroda": "Борода", "kardan": "Кардан",
    "lastochka": "Ласточка", "lisa": "Лиса", "mihalych": "Михалыч",
    "palych": "Палыч", "petrovna": "Петровна", "professor": "Профессор",
    "rustam": "Рустам", "sova": "Сова", "stas": "Стас",
    "student": "Студент", "ten": "Тень", "vera": "Вера",
    "vitek": "Витёк", "yanek": "Янек",
}

COLS, ROWS = 6, 3
CARD_W, CARD_H, LABEL_H = 464, 576, 64
MARGIN, GAP = 40, 16

W = MARGIN * 2 + COLS * CARD_W + (COLS - 1) * GAP
H = MARGIN * 2 + ROWS * (CARD_H + LABEL_H) + (ROWS - 1) * GAP

canvas = Image.new("RGB", (W, H), (18, 20, 24))
draw = ImageDraw.Draw(canvas)
font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 34)

files = sorted(SRC.glob("*.png"))
assert len(files) <= COLS * ROWS, f"портретов {len(files)} > ячеек {COLS*ROWS}"

for i, f in enumerate(files):
    name = f.stem
    row, col = divmod(i, COLS)
    x = MARGIN + col * (CARD_W + GAP)
    y = MARGIN + row * (CARD_H + LABEL_H + GAP)
    img = Image.open(f).convert("RGB").resize((CARD_W, CARD_H), Image.LANCZOS)
    canvas.paste(img, (x, y))
    label = CALLSIGNS.get(name, name)
    lx = x + CARD_W // 2
    ly = y + CARD_H + LABEL_H // 2
    draw.text((lx, ly), label, font=font, fill=(235, 230, 220), anchor="mm")

canvas.save(OUT)
print(f"{OUT} {W}x{H}, {len(files)} портретов")
