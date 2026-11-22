"""Черновые тексты через Google Gemini (замена/дополнение локальных Ollama-ролей).

Использование:
  py cb-radio/tools/gemini_llm.py [--role lite|flash] "промт"
  echo "промт" | py cb-radio/tools/gemini_llm.py
  py cb-radio/tools/gemini_llm.py --check

Роли:
  lite  = gemini-3.5-flash-lite — дефолт, черновая масса текстов (аналог draft)
  flash = gemini-3.5-flash       — вкуснее, тот же запрос, дороже

Ключ читается из build/gemini_key.txt (gitignored), никогда не печатается.
Только stdlib (urllib.request, json), без зависимостей.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

KEY_FILE = Path(__file__).resolve().parents[2] / "build" / "gemini_key.txt"
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT_S = 60

ROLES = {
    "lite": "gemini-3.5-flash-lite",
    "flash": "gemini-3.5-flash",
}


def fail(msg: str) -> int:
    print(f"gemini_llm: {msg}", file=sys.stderr)
    return 2


def load_key() -> str:
    if not KEY_FILE.exists():
        raise SystemExit(fail(f"нет файла ключа: {KEY_FILE}"))
    key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key:
        raise SystemExit(fail(f"файл ключа пуст: {KEY_FILE}"))
    return key


def ask(model: str, prompt: str) -> dict:
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 2048},
    }).encode("utf-8")
    req = urllib.request.Request(
        API.format(model=model),
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": load_key()},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = (e.read().decode("utf-8", "replace") or "")[:200]
        if e.code == 400 or e.code in (401, 403):
            return _raise(fail(f"ключ не принят ({e.code}), проверь build/gemini_key.txt"))
        if e.code == 429:
            return _raise(fail("квота исчерпана (429)"))
        if "location" in detail.lower() and "not supported" in detail.lower():
            return _raise(fail("User location is not supported — включи VPN (NL/FI)"))
        return _raise(fail(f"HTTP {e.code}: {detail}"))
    except urllib.error.URLError as e:
        reason = str(getattr(e, "reason", e))[:200]
        if "timed out" in reason.lower():
            return _raise(fail(f"таймаут {TIMEOUT_S} с — сеть/VPN не отвечает"))
        return _raise(fail(f"сетевая ошибка: {reason}"))


def _raise(code: int):
    raise SystemExit(code)


def extract_text(data: dict) -> str:
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError, TypeError):
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=sorted(ROLES), default="lite")
    ap.add_argument("--check", action="store_true",
                    help="минимальный запрос: OK, модель, токены, время")
    ap.add_argument("prompt", nargs="?", default=None)
    args = ap.parse_args()
    model = ROLES[args.role]

    if args.check:
        prompt = "Ответь одним словом: готов"
    else:
        prompt = args.prompt if args.prompt is not None else sys.stdin.read()
        if not prompt.strip():
            return fail("пустой промт (передай аргументом или через stdin)")

    t0 = time.monotonic()
    data = ask(model, prompt)
    secs = time.monotonic() - t0
    usage = data.get("usageMetadata", {})
    total = usage.get("totalTokenCount", "?")

    if args.check:
        ok = bool(extract_text(data).strip()) and data.get("candidates")
        print(f"{'OK' if ok else 'FAIL'} | {model} | токенов: {total} | {secs:.1f} с")
        return 0 if ok else fail("модель вернула пустой ответ")

    text = extract_text(data)
    if not text:
        return fail(f"пустой ответ (usage: {json.dumps(usage, ensure_ascii=False)[:200]})")
    sys.stdout.write(text + "\n")
    print(f"[gemini_llm] {model}: {total} tok, {secs:.1f} с", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
