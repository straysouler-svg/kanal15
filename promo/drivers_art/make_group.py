"""Общая сцена «вечеринка на полянке» (фото). Лица берутся из лучших портретов (picks.json -> коллаж-референс).
make_group.py [takes=2] [aspect=16:9] [size=1K]  -> group/party_<n>.png, журнал make_group.log"""
import base64
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
KEY = (HERE.parents[1] / "cb-radio" / "openrouter_key.txt").read_text(encoding="utf-8").strip()
MODEL = "google/gemini-3.1-flash-image"

ORDER = ["mihalych", "stas", "yanek", "lastochka", "boroda", "student", "professor", "petrovna", "ten",
         "vitek", "sova", "palych", "kardan", "lisa", "rustam", "bahti", "vera"]
WHO = ("1 Mikhalych (old man, flat cap, grey moustache), 2 Stas (young, cap backwards, filming on phone), "
       "3 Yanek (calm, beanie, honey jar), 4 Lastochka (confident woman, short light hair), 5 Boroda (huge beard, loud), "
       "6 Student (nervous young guy), 7 Professor (glasses, tweed), 8 Petrovna (plump cheerful woman with pies), "
       "9 Ten (quiet guy in dark hood with coffee, standing a bit apart), 10 Vitek (white shirt, no tie, on the phone), "
       "11 Sova (woman with glasses on a chain and shawl), 12 Palych (stocky, moustache, whistle), "
       "13 Kardan (rocker with guitar), 14 Lisa (copper-red hair, leather jacket), 15 Rustam (Uzbek skullcap, kazan of "
       "plov), 16 Bakhtiyar (cowboy hat), 17 Vera (dark green fleece) with her old German shepherd dog")

PROMPT = (
    "Photorealistic aerial drone photograph, natural colours, bright sunny summer day, a few fluffy clouds. "
    "The drone hovers about 10-15 metres high just behind and above the player, tilted down at about 35 degrees: in the "
    "lower part of the frame we see a man from behind and above (short hair, plain grey t-shirt, his face NOT visible), "
    "walking across a green meadow towards a big happy party of truck drivers further ahead. People are small in the "
    "frame, recognisable by silhouette, hair, clothes and gestures rather than facial detail. Around the meadow stand about a dozen modern European cab-over trucks of different colours "
    "(burgundy, green, white, dark grey with reefer trailer, blue, black, red, orange, light blue, silver, dark green, "
    "timber truck with logs), parked in a loose circle like a camp. String lights between the trucks, a long folding "
    "table with food, a big kazan of plov steaming, a samovar, a guitar, balloons. "
    "The drivers are the 17 people from the reference collage, keep their faces, hair, age and clothes: " + WHO + ". "
    "Almost everyone is overjoyed to see the newcomer: waving both hands, raising cups, cheering, Stas filming him on "
    "his phone, the dog running towards him. One or two are comically sulking: Boroda with crossed arms and a pouting "
    "face, pretending to be offended he was not the first to be greeted. Joyful, warm, friendly atmosphere. "
    "No text, no letters, no logos, no brand emblems on any truck, no writing on clothes, no watermark.")


def collage(picks):
    tiles = [Image.open(HERE / "portraits" / picks[k]).convert("RGB") for k in ORDER if k in picks]
    w, h = 300, 375
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t.resize((w, h)), ((i % cols) * w, (i // cols) * h))
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=88)
    (HERE / "group").mkdir(exist_ok=True)
    sheet.save(HERE / "group" / "_reference_collage.jpg", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def generate(prompt, ref, aspect, size, intro=True):
    text = ("Reference collage of the 17 characters, left to right, top to bottom, in this order: " + WHO + ".\n\n"
            if intro else "") + prompt
    body = {"model": MODEL, "modalities": ["image", "text"], "usage": {"include": True},
            "image_config": {"aspect_ratio": aspect, "image_size": size},
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": ref}}]}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=600))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"OpenRouter {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")
    msg = r["choices"][0]["message"]
    imgs = [i["image_url"]["url"] for i in msg.get("images") or []]
    if not imgs:
        raise SystemExit(f"картинки нет: {str(msg.get('content'))[:300]}")
    return base64.b64decode(imgs[0].split(",", 1)[1]), r.get("usage", {}).get("cost", 0)


if __name__ == "__main__":
    takes = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    aspect = sys.argv[2] if len(sys.argv) > 2 else "16:9"
    size = sys.argv[3] if len(sys.argv) > 3 else "1K"
    picks = json.loads((HERE / "picks.json").read_text(encoding="utf-8"))
    ref = collage(picks)
    out_dir = HERE / "group"
    with (HERE / "make_group.log").open("a", encoding="utf-8") as log:
        total = 0.0
        start = len(list(out_dir.glob("party_*.png")))
        for n in range(start + 1, start + takes + 1):
            try:
                data, cost = generate(PROMPT, ref, aspect, size)
                (out_dir / f"party_{n}.png").write_bytes(data)
                total += cost or 0
                log.write(f"party_{n}.png {aspect} {size} {len(data) // 1024} KB ${cost:.3f}\n")
            except BaseException as e:
                log.write(f"party_{n}: ОШИБКА {e}\n")
            log.flush()
        log.write(f"итого ${total:.3f}\nDONE\n")
