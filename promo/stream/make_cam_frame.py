"""Рамка для камеры стримера (2026-11-06): чёрная окантовка с рваным краем, «мазок кистью», как у Кирилла.
Внутри прозрачное окно INNER; результат — scenes/cam_frame.png (кладётся в OBS поверх камеры)."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

INNER = (246, 356)          # окно камеры, px (портрет)
BORDER = 12                 # сплошная часть рамки
RAGGED = 16                 # насколько рвётся внешний край
PAD = BORDER + RAGGED + 4
W, H = INNER[0] + 2 * PAD, INNER[1] + 2 * PAD
rng = np.random.default_rng(15)


def walk(n, amp, smooth):
    """Rough 1-D edge: random walk + spikes, smoothed a little (brush bristles)."""
    x = np.cumsum(rng.normal(0, 1, n))
    x = (x - x.min()) / (np.ptp(x) or 1)
    k = np.ones(smooth) / smooth
    base = np.convolve(x, k, mode="same") * 0.55
    spikes = (rng.random(n) ** 6) * 0.9            # rare long bristles
    return np.clip(base + spikes * rng.random(n), 0, 1) * amp


yy, xx = np.mgrid[0:H, 0:W]
x0, y0, x1, y1 = PAD - BORDER, PAD - BORDER, PAD + INNER[0] + BORDER, PAD + INNER[1] + BORDER
top, bot = walk(W, RAGGED, 5), walk(W, RAGGED, 5)
lef, rig = walk(H, RAGGED, 5), walk(H, RAGGED, 5)
outer = ((yy >= y0 - top[xx]) & (yy <= y1 + bot[xx]) & (xx >= x0 - lef[yy]) & (xx <= x1 + rig[yy]))
# the inner edge is nearly straight, just a hint of roughness
it, ib = walk(W, 2.5, 3), walk(W, 2.5, 3)
il, ir = walk(H, 2.5, 3), walk(H, 2.5, 3)
hole = ((yy >= PAD + it[xx]) & (yy < PAD + INNER[1] - ib[xx]) & (xx >= PAD + il[yy]) & (xx < PAD + INNER[0] - ir[yy]))
alpha = (outer & ~hole).astype(np.float32)
# dry-brush texture: some see-through streaks in the outer half of the border
streak = rng.random((H, W)) < 0.10
far = ~((yy >= y0) & (yy <= y1) & (xx >= x0) & (xx <= x1))
alpha[streak & far] *= 0.35
a = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
rgb = np.zeros((H, W, 3), np.uint8)
rgb[..., :] = (14, 14, 16)                          # not pure black: reads as paint, not a hole
img = Image.fromarray(rgb).convert("RGBA")
img.putalpha(a)
out = Path(__file__).resolve().parent / "scenes" / "cam_frame.png"
img.save(out)
print(out, img.size, "окно", INNER, "отступ", PAD)
