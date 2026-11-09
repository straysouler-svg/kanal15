# Сборка коллажа «весь состав» БЕЗ подписей-позывных (канон: персонажей поимённо в промо не светим).
# Исходники: promo/drivers_art/selected (17 утверждённых артов).
# Запуск: G:/Claude/gruzovichki/build/venv/Scripts/python.exe make_collage_nonames.py
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "drivers_art" / "selected"
OUT = HERE / "collage_nonames.png"

COLS, ROWS = 6, 3
CARD_W, CARD_H = 464, 576
MARGIN, GAP = 40, 16

W = MARGIN * 2 + COLS * CARD_W + (COLS - 1) * GAP
H = MARGIN * 2 + ROWS * CARD_H + (ROWS - 1) * GAP
canvas = Image.new("RGB", (W, H), (18, 20, 24))

files = sorted(SRC.glob("*.png"))
assert len(files) <= COLS * ROWS
for i, f in enumerate(files):
    row, col = divmod(i, COLS)
    x = MARGIN + col * (CARD_W + GAP)
    y = MARGIN + row * (CARD_H + GAP)
    img = Image.open(f).convert("RGB").resize((CARD_W, CARD_H), Image.LANCZOS)
    canvas.paste(img, (x, y))
canvas.save(OUT)
print(f"{OUT} {W}x{H}, {len(files)} портретов, без подписей")
