"""Images via OpenRouter (Gemini image models). gen_image.py <out.png> "<prompt>" [aspect e.g. 21:9] [model]"""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = (ROOT / "openrouter_key.txt").read_text(encoding="utf-8").strip()


def generate(prompt, aspect="16:9", model="google/gemini-3.1-flash-image"):
    body = {"model": model, "modalities": ["image", "text"], "usage": {"include": True},
            "image_config": {"aspect_ratio": aspect},
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"OpenRouter {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")
    msg = r["choices"][0]["message"]
    imgs = [i["image_url"]["url"] for i in msg.get("images") or []]
    if not imgs:
        raise SystemExit(f"картинки нет: {str(msg.get('content'))[:300]}")
    return base64.b64decode(imgs[0].split(",", 1)[1]), r.get("usage", {}).get("cost", 0)


if __name__ == "__main__":
    out, prompt = Path(sys.argv[1]), sys.argv[2]
    aspect = sys.argv[3] if len(sys.argv) > 3 else "16:9"
    model = sys.argv[4] if len(sys.argv) > 4 else "google/gemini-3.1-flash-image"
    data, cost = generate(prompt, aspect, model)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"{out.name}: {len(data) // 1024} КБ, ${cost:.3f}")
