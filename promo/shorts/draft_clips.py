"""Черновики шортсов из записей OBS (2026-11-07): profile «Канал 15 — Шортсы» кладёт файлы в raw/,
рация пишет журнал реплик cb-radio/subs/<дата>.jsonl (кто, что, когда). Этот скрипт сводит одно с другим:
    python draft_clips.py            # все новые файлы из raw/ -> specs/drafts/*.json
    python draft_clips.py --all      # пересобрать и уже сделанные
Клип (F9, 90 с) -> один черновик: от первой реплики -3 с до конца последней +2 с.
Полная запись (Scroll Lock) -> по черновику на каждый разговор (реплики с паузами < 20 с).
В черновике уже есть субтитры с именами и цветами; остаётся вписать «hook» (крючок), поправить начало/конец
и запустить make_short.py specs/drafts/<имя>.json."""
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
SUBS = HERE.parents[1] / "cb-radio" / "subs"
DRAFTS = HERE / "specs" / "drafts"
GAP = 20.0          # a pause longer than this ends a conversation
PAD_IN, PAD_OUT = 3.0, 2.0
NOWIN = 0x08000000


def duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, creationflags=NOWIN)
    return float(r.stdout.strip())


def start_of(p, dur):
    """Wall-clock start of the file. A full recording is named by its start time; a replay clip by the moment it
    was saved (= its end), so for clips: modification time minus length."""
    m = re.search(r"(\d{4}-\d\d-\d\d) (\d\d)-(\d\d)-(\d\d)", p.stem)
    if m and not p.stem.startswith("Клип"):
        return datetime.datetime.strptime(" ".join(m.groups()), "%Y-%m-%d %H %M %S").timestamp()
    return p.stat().st_mtime - dur


def journal(t0, t1):
    out = []
    for day in {datetime.date.fromtimestamp(t0), datetime.date.fromtimestamp(t1)}:
        f = SUBS / f"{day:%Y-%m-%d}.jsonl"
        if f.exists():
            for ln in f.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if t0 - 10 <= r["t"] <= t1:
                    out.append(r)
    return sorted(out, key=lambda r: r["t"])


def sub_of(r, t0):
    who, text = r.get("who", ""), r.get("text", "")
    if r["kind"] == "you":                      # t = when he released the PTT; the words came just before
        d = min(5.0, max(1.2, len(text) * 0.065))
        return {"t": round(r["t"] - t0 - d - 0.2, 2), "d": round(d, 2), "who": "player", "text": text}
    d = r.get("d") or min(6.0, max(1.5, len(text) * 0.07))
    s = {"t": round(r["t"] - t0, 2), "d": round(d, 2), "who": who, "text": text}
    if who in ("bond", "foreign"):
        s["name"] = r.get("name", "")
    return s


def groups(subs):
    out, cur = [], []
    for s in subs:
        if cur and s["t"] - (cur[-1]["t"] + cur[-1]["d"]) > GAP:
            out.append(cur)
            cur = []
        cur.append(s)
    return out + ([cur] if cur else [])


def main():
    redo = "--all" in sys.argv
    DRAFTS.mkdir(parents=True, exist_ok=True)
    made = 0
    for p in sorted(RAW.glob("*.mp4")):
        if not redo and any(DRAFTS.glob(f"{p.stem}*.json")):
            continue
        dur = duration(p)
        t0 = start_of(p, dur)
        subs = [sub_of(r, t0) for r in journal(t0, t0 + dur)]
        subs = [s for s in subs if s["t"] + s["d"] > 0 and s["t"] < dur]
        clip = p.stem.startswith("Клип")
        chunks = [subs] if clip else groups(subs)
        if not subs:
            print(f"{p.name}: в журнале рации за это время ничего нет (рация была выключена или оверлей off?)")
            chunks = [[]]
        for i, ch in enumerate(chunks, 1):
            a = max(0.0, min((s["t"] for s in ch), default=0.0) - PAD_IN)
            b = min(dur, max((s["t"] + s["d"] for s in ch), default=dur) + PAD_OUT)
            name = p.stem if len(chunks) == 1 else f"{p.stem} — {i:02d}"
            spec = {"src": str(p), "out": f"{name}.mp4", "layout": "rec", "hook": "",
                    "_note": "впиши hook (2 строки через \\N), поправь parts и запусти make_short.py",
                    "parts": [[round(a, 1), round(b, 1)]], "subs": ch}
            (DRAFTS / f"{name}.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
            made += 1
            print(f"черновик: {name} ({b - a:.0f} с, реплик {len(ch)})")
    print("готово, черновиков:", made)


if __name__ == "__main__":
    main()
