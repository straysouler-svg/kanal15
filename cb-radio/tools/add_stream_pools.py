"""Интеграция стрим-пулов 17.11: черновики drafts_stream_*_2026-11-16.md -> reactions level3_eleven.json.

ТОЛЬКО дописывает строки в конец существующих списков (позиции озвученного не сдвигаются).
Персональный пул (drafts_stream_banter_personal) -> phrases/personal_local.json (не в git/релиз).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHRASES = ROOT / "phrases" / "level3_eleven.json"
PERSONAL = ROOT / "phrases" / "personal_local.json"

NAME2ID = {
    "михалыч": "mihalych", "стас": "stas", "янек": "yanek", "ласточка": "lastochka",
    "борода": "boroda", "сорока": "soroka", "студент": "student", "профессор": "professor",
    "петровна": "petrovna", "тень": "ten", "витёк": "vitek", "сова": "sova", "палыч": "ment",
    "кардан": "kardan", "лиса": "lisa", "рустам": "rustam", "бахтияр": "bahti", "вера": "vera",
}
HEADER_RX = re.compile(r"^###\s+\d+\.\s+(.+?)(?:\s*\(|$)")
LINE_RX = re.compile(r"^\d+\.\s+(.+)$")
DROP_RX = re.compile(r"[*_]`")


def parse_draft(path):
    """{actor_id: [text, ...]} — реплики по порядку секций."""
    pools, cur = {}, None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        h = HEADER_RX.match(s)
        if h:
            name = h.group(1).strip().lower()
            cur = NAME2ID.get(name)
            if cur is None:
                sys.exit(f"{path.name}: неизвестный водитель «{h.group(1)}»")
            pools.setdefault(cur, [])
            continue
        m = LINE_RX.match(s)
        if m and cur:
            pools[cur].append(m.group(1).strip())
    return pools


def merge(pools, target, group):
    """Дописать pools в target['reactions'][group] (dict actor -> [lines])."""
    reactions = target.setdefault("reactions", {})
    dst = reactions.setdefault(group, {})
    if not isinstance(dst, dict):
        sys.exit(f"{group}: неожиданный формат {type(dst).__name__}")
    n = 0
    for actor, texts in pools.items():
        lines = dst.setdefault(actor, [])
        existing = {ln.get("text") for ln in lines if isinstance(ln, dict)}
        for t in texts:
            if t not in existing:
                lines.append({"actor": actor, "text": t})
                n += 1
    return n


def main():
    d = json.loads(PHRASES.read_text(encoding="utf-8"))
    total = 0
    for group, draft in (("stream_greet", "drafts_stream_greet_2026-11-16.md"),
                         ("stream_banter", "drafts_stream_banter_2026-11-16.md"),
                         ("stream_ack", "drafts_stream_ack_2026-11-16.md")):
        pools = parse_draft(ROOT / "phrases" / draft)
        n = merge(pools, d, group)
        total += n
        print(f"{group}: +{n} ({sum(len(v) for v in pools.values())} в черновике, "
              f"{len(pools)} водителей)")
    PHRASES.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    personal = parse_draft(ROOT / "phrases" / "drafts_stream_banter_personal_2026-11-16.md")
    pd = {"_comment": "ЛИЧНЫЙ локальный оверлей (Железяка) — не в git, не в релиз. "
                      "Подмёрживается в reactions при загрузке (cb_radio.load_phrases) и при озвучке.",
          "reactions": {}}
    pn = merge(personal, pd, "stream_banter")
    PERSONAL.write_text(json.dumps(pd, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"personal_local.json: +{pn} (stream_banter)")
    print(f"итого в level3_eleven.json: +{total}")


if __name__ == "__main__":
    main()
