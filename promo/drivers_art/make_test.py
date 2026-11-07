"""Проба двух стилей портрета водителя (Кардан): иллюстрация и почти-фото. Пишет картинки и журнал рядом."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "cb-radio" / "tools"))
import gen_image  # noqa: E402

SUBJECT = (
    "Gena, nicknamed 'Kardan', a 41-year-old Russian long-haul truck driver and former rock musician: shoulder-length "
    "messy dark hair with grey streaks, stubble, black band t-shirt under an open worn denim vest, leather wristbands, "
    "sitting on the step of his truck cab and playing an electric guitar, grinning, full of energy. Behind him a big "
    "modern European cab-over semi tractor, dark red, with a plain cab and NO brand logos and NO text anywhere. "
    "A truck stop parking lot at golden hour, warm sunset light, a few string lights. Vertical composition, "
    "the man and his truck both clearly visible. No text, no letters, no logos, no watermarks.")
STYLES = {
    "illustr": "Warm hand-painted digital illustration, cozy storybook style, soft brush strokes, rich warm colours, "
               "friendly and expressive character, slightly stylised proportions. ",
    "photo": "Photorealistic cinematic photograph, 50mm lens, shallow depth of field, natural skin texture, "
             "realistic lighting and materials. ",
}
log = HERE / "make_test.log"
with log.open("w", encoding="utf-8") as f:
    total = 0.0
    for name, style in STYLES.items():
        try:
            data, cost = gen_image.generate(style + SUBJECT, "4:5")
            out = HERE / "test" / f"kardan_{name}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            total += cost or 0
            f.write(f"{name}: {out} {len(data) // 1024} KB ${cost:.3f}\n")
        except BaseException as e:      # gen_image raises SystemExit on API errors
            f.write(f"{name}: ОШИБКА {e}\n")
        f.flush()
    f.write(f"итого ${total:.3f}\n")
