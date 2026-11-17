"""Проверка ударений реплик перед озвучкой (ruaccent + проектный stress_dict).

Использование:
  stress_check.py level3                 — все пулы level3_eleven.json
  stress_check.py <файл.md>              — черновик (строки реплик: нумерованные, «- », кавычки)
  stress_check.py --text "реплика"       — одна строка

Отчёт: `персонаж | реплика | слово → предлагаемое ударение | причина`.
Флаги: dict-mismatch (слово есть в stress_dict, модель ставит иное ударение — подтверждено словарём,
подмена для синтеза сработает), no-stress (модель не поставила ударение), jargon (слово из проектного
жаргона вне словаря). Неподтверждённые флаги (no-stress, jargon) → exit 1.
Ключ --stress-ok: не блокировать (записывается в отчёт) — только для вызова из gen_eleven.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG_RX = re.compile(r"\[[^\]]*\]|\([^)]*\)")          # ремарки вида [chuckles], (смеётся)
WORD_RX = re.compile(r"[а-яёА-ЯЁ]+(?:-[а-яёА-ЯЁ]+)*")
TOK_RX = re.compile(r"[а-яё+]+(?:-[а-яё+]+)*")


def _word_tok(tok):
    """Токен разметки ruaccent -> слово с '+' без пунктуации ('Гудни,' -> 'гудни')."""
    m = TOK_RX.search(tok.lower())
    return m.group(0) if m else None
VOWELS = "аеёиоуыэюя"

JARGON = {"лео"}  # позывные/клички вне словаря — на память; подтверждённые живут в stress_dict.json

# модель turbo2 не ставит «+» на этих словах в контексте (проверено прогоном эфира 16.11) —
# ложные срабатывания, не риски для синтеза
NO_STRESS_IGNORE = {"или", "меня", "мама", "кого", "когда", "его", "мимо", "даже", "они",
                    "один", "моей", "мамой", "иди", "задом", "тебя", "собой", "кому",
                    "где-то", "что-то", "что-нибудь", "кое-что", "ии",
                    "кто-то", "как-то", "э-э", "я-то", "чуть-чуть", "сам-то", "ты-то",
                    "из-за", "из-под", "чем-то", "хот-дог", "тип-топ", "нью-йорк", "рок-н-ролл"}

_ACC = None
_DICT = None


def _acc():
    global _ACC
    if _ACC is None:
        import numpy as _np
        from ruaccent import RUAccent
        _ACC = RUAccent()
        _ACC.load(omograph_model_size="turbo2", use_dictionary=False)
        # старый transformers не отдаёт token_type_ids: докидываем/убираем под требования конкретной onnx-модели
        def _patch_tok(model):
            tok = model.tokenizer
            want = {"token_type_ids"} & {i.name for i in model.session.get_inputs()}

            def _call(*a, **kw):
                out = tok(*a, **kw)
                if want and "token_type_ids" not in out:
                    out["token_type_ids"] = _np.zeros_like(out["input_ids"])
                elif not want and "token_type_ids" in out:
                    del out["token_type_ids"]
                return out

            model.tokenizer = _call

        _patch_tok(_ACC.omograph_model)
        _patch_tok(_ACC.accent_model)
    return _ACC


def stress_dict():
    global _DICT
    if _DICT is None:
        _DICT = {e["word"].lower(): e for e in
                 json.loads((ROOT / "phrases" / "stress_dict.json").read_text(encoding="utf-8"))}
    return _DICT


def _expected_vowel(entry):
    m = re.search(r"[" + VOWELS.upper() + "]", entry["stressed"])
    return m.group(0).lower() if m else None


def _truly_unstressed(w):
    """Слово без '+' в контексте: если в одиночную прогонку модель ставит ударение —
    это контекстный пропуск (ложный флаг), не риск для синтеза."""
    marked = _acc().process_all(w)
    return "+" not in marked


def check_line(text):
    """[(word, proposed, reason, confirmed)] — proposed: ударение из словаря или None."""
    clean = TAG_RX.sub(" ", text)
    marked = _acc().process_all(clean)
    d = stress_dict()
    flags = []
    for tok in marked.split():
        low = _word_tok(tok)
        if not low:
            continue
        w = low.replace("+", "")
        if sum(ch in VOWELS for ch in w) <= 1:     # односложные: ударение не нужно
            continue
        if w in d:
            entry = d[w]
            want = _expected_vowel(entry)
            got = None
            for i, ch in enumerate(low):
                if ch == "+" and i + 1 < len(low):
                    got = low[i + 1]
                    break
            if got != want:
                flags.append((w, entry["stressed"], "dict-mismatch", True))
        elif "+" not in low and "ё" not in w and w not in NO_STRESS_IGNORE and _truly_unstressed(w):
            if not _chatter(w):
                flags.append((w, None, "no-stress", False))
        if w in JARGON and w not in d:
            flags.append((w, None, "jargon", False))
    return flags


CHATTER_PARTS = ("то", "та", "либо", "нибудь")   # «кто-то», «спишь-то» — клитики, ударение несущественно


def _chatter(w):
    """Слэнговая слоговая разбивка/междометие («вой-бо», «да-да», «та-та-та-та», «не-е-ет»): TTS читает
    по слогам как написано, ударение не коварное — в пропуск (17.11, после интеграции стрим-пулов)."""
    parts = w.split("-")
    if len(parts) < 2:
        return False
    if any(p in CHATTER_PARTS for p in parts):
        return True
    return all(len(p) <= 4 for p in parts)


def _lines_from_md(path):
    out = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith(("#", "|")):
            continue
        m = re.match(r"^(-\s*)?(»)?[«\"]?(.+?)[»\"]?$", s)
        if not m:
            continue
        t = m.group(3)
        if re.match(r"^\d+\.\s", t) or t.startswith(("«", '"')) or s.startswith("- "):
            t = re.sub(r"^\d+\.\s*", "", t)
            out.append(t)
    return out


def _lines_level3():
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    out = []
    for a, spec in data["actors"].items():
        for p in spec.get("phrases", []):
            if isinstance(p, dict):
                out.append((a, p.get("text", "")))
    for g, kinds in data["reactions"].items():
        if g.startswith("_"):
            continue
        for kind, lines in kinds.items():
            if kind.startswith("_"):
                continue
            seqs = lines.values() if isinstance(lines, dict) else [lines]
            for seq in seqs:
                for ln in seq:
                    if isinstance(ln, dict) and ln.get("text") and not ln.get("v_pending"):
                        out.append((ln.get("actor", g), ln["text"]))
    return out


def ruaccent_opinion(text):
    """ВТОРОЕ МНЕНИЕ (оценка 17.11: омографы разрешает отлично, но на коварных словах
    («гудни»->гУдни, «йогурты»->йОгурты) ошибается ровно как TTS — НЕ источник истины).
    -> {word: stressed_form_с_+} — только информационно, exit-код не меняет."""
    marked = _acc().process_all(TAG_RX.sub(" ", text))
    out = {}
    for tok in marked.split():
        low = _word_tok(tok)
        if low and "+" in low:
            out[low.replace("+", "")] = low
    return out


def main(argv):
    stress_ok = "--stress-ok" in argv
    second = "--ruaccent" in argv          # второе мнение ruaccent: только печать, не блокирует
    argv = [a for a in argv if a not in ("--stress-ok", "--ruaccent")]
    if len(argv) >= 2 and argv[1] == "level3":
        rows = _lines_level3()
    elif len(argv) >= 2 and argv[1] == "--text":
        rows = [("?", argv[2])]
    else:
        rows = [("?", t) for t in _lines_from_md(argv[1])]
    n_conf = n_unconf = 0
    for actor, text in rows:
        for word, proposed, reason, confirmed in check_line(text):
            n_conf += confirmed
            n_unconf += not confirmed
            print(f"{actor} | {text[:70]} | {word} → {proposed or '???'} | {reason}"
                  + ("" if confirmed else "  НЕПОДТВЕРЖДЁН"))
        if second:
            d = stress_dict()
            for w, marked_form in sorted(ruaccent_opinion(text).items()):
                if w not in d:
                    continue
                got_v = None
                low = marked_form.lower()
                for i, ch in enumerate(low):
                    if ch == "+" and i + 1 < len(low):
                        got_v = low[i + 1]
                        break
                want_v = _expected_vowel(d[w])
                if got_v != want_v:
                    print(f"   [ruaccent] {w}: модель {marked_form} | словарь {d[w]['stressed']}  (сверить вручную)")
    print(f"строк: {len(rows)}, флагов подтверждённых: {n_conf}, неподтверждённых: {n_unconf}"
          + ("  (--stress-ok)" if stress_ok and n_unconf else ""))
    return 0 if stress_ok or n_unconf == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
