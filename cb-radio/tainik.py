"""Тайник рации (2026-11-06).

Секрет — реакция, о которой игрок должен узнать сам: сказал в рацию особые слова — и водители отвечают.
Чтобы любопытный не прочитал их в папке рации, при сборке (tools/pack_release.py):
  * слова-ключи и тексты реплик уходят из открытых файлов в phrases/x.dat (зашифровано, не открытым текстом);
  * звуки лежат не в reactions/intent/<секрет>, а в reactions/x/<безликое имя>.
Это защита от случайного любопытства, а не от взлома: упорный человек докопается. Сюрприз не испортится случайно.

У разработчика (без сборки) всё лежит открыто: слова-ключи — phrases/secrets_src.json, реплики — как обычно
в phrases/level3_eleven.json (reactions.intent.<секрет>), звуки — audio/reactions/intent/<секрет>."""
import base64
import hashlib
import json
from pathlib import Path

_SALT = b"kanal15:x"


def dirname(kind):
    """Faceless folder name for a secret kind's audio."""
    return hashlib.sha256(_SALT + kind.encode()).hexdigest()[:12]


def _stream(n):
    out, i = bytearray(), 0
    while len(out) < n:
        out += hashlib.sha256(_SALT + i.to_bytes(4, "big")).digest()
        i += 1
    return bytes(out[:n])


def encode(obj):
    raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(bytes(a ^ b for a, b in zip(raw, _stream(len(raw)))))


def decode(blob):
    raw = base64.b64decode(blob)
    return json.loads(bytes(a ^ b for a, b in zip(raw, _stream(len(raw)))).decode("utf-8"))


def kinds(sec):
    return [k for k, _ in (sec or {}).get("intents", [])]


def load(phrases_dir):
    """-> {"intents": [[kind, [stems]], ...], "texts": {kind: [line text, ...]}} — from x.dat in a build,
    from phrases/secrets_src.json + level3_eleven.json at the developer's."""
    phrases_dir = Path(phrases_dir)
    x = phrases_dir / "x.dat"
    if x.exists():
        try:
            return decode(x.read_bytes())
        except Exception:
            return {"intents": [], "texts": {}}
    src = phrases_dir / "secrets_src.json"
    try:
        s = json.loads(src.read_text(encoding="utf-8"))
        d = json.loads((phrases_dir / "level3_eleven.json").read_text(encoding="utf-8"))
        texts = {k: [ln["text"] for ln in d["reactions"]["intent"].get(k, [])] for k, _ in s.get("intents", [])}
        return {"intents": s.get("intents", []), "texts": texts}
    except (OSError, ValueError, KeyError):
        return {"intents": [], "texts": {}}
