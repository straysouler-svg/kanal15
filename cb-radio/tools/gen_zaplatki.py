# -*- coding: utf-8 -*-
"""22.11: озвучка раздела 7 «Заплатки экзамена-50» (63 реплики, intent/* пулы).
EL-актёры — ElevenLabs v3 (штатные voice_id), gpt-audio актёры (vitek, petrovna, kardan, lisa,
ment, ten) — через OpenRouter своими gpt-голосами (OR_BUDGET, дефолт 0.5$), Сорока — XTTS-клон.
QA: стресс-гейт + whisper-обратный контроль (ретраи до 3).

  OR_BUDGET=0.5 G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_zaplatki.py
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge          # noqa: E402
import gen_openrouter as gor     # noqa: E402
import gen_level3 as g           # noqa: E402
import remix                     # noqa: E402

ROOT = g.ROOT
BUDGET = float(os.environ.get("OR_BUDGET", "0.5"))
KINDS = ("flare", "alert_other", "road_ask", "life_route", "radio_tech", "truck_market")


def main():
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    or_spent, el_used, made, bad = 0.0, 0, 0, []
    for kind in KINDS:
        lines = data["reactions"]["intent"][kind]
        d = ROOT / "audio" / "reactions" / "intent" / kind
        d.mkdir(parents=True, exist_ok=True)
        man_f = d / "manifest.json"
        man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {}
        for i, ln in enumerate(lines, 1):
            n = f"{i:02d}"
            a = data["actors"][ln["actor"]]
            sig = ge._sig(a, ln["text"])
            if man.get(n) == sig and (d / f"{n}.wav").exists():
                continue
            ge._stress_gate(ln["text"])
            if a.get("engine") == "gpt-audio":
                # gpt-актёр — свой gpt-голос через OpenRouter
                best = None
                for attempt in range(3):
                    if or_spent >= BUDGET:
                        raise SystemExit(f"OR бюджет {BUDGET}$ исчерпан ({or_spent:.3f}) — стоп, догенерируем позже")
                    x, cost = gor.tts(ln["text"], a["voice"], a.get("style", ""))
                    or_spent += cost
                    ok, r, why = gor.check(x, ln["text"], a.get("style", ""))
                    print(f"[intent/{kind}] {ln['actor']} {n} OR ${cost:.4f} {'OK' if ok else why}")
                    if best is None or (ok, r) > (best[0], best[1]):
                        best = (ok, r, x)
                    if ok:
                        break
                mp3, x = None, best[2]
                if not best[0]:
                    bad.append(f"{kind}/{n}")
            else:
                mp3, x, spent = ge.voice(a, ln["text"])     # EL (или XTTS-клон у Сороки)
                el_used += spent
                ok, r, why = gor.check(x, ln["text"], a.get("style", ""))
                print(f"[intent/{kind}] {ln['actor']} {n} {len(x) / g.SR:4.1f}c "
                      f"(+{spent} сим) {'OK' if ok else why}")
                if not ok:
                    bad.append(f"{kind}/{n}")
            if mp3:
                (d / f"{n}.mp3").write_bytes(mp3)
            sf.write(d / f"{n}_dry.wav", x, g.SR)
            rng = np.random.default_rng(abs(hash((str(d), i))) % 2**32)
            sf.write(d / f"{n}.wav", remix.render(x, a, False, rng), g.SR)
            man[n] = sig
            man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
            made += 1
        (d / "index.json").write_text(json.dumps({"actors": [x["actor"] for x in lines]}, ensure_ascii=False),
                                      encoding="utf-8")
    print(f"готово: {made} дорожек, EL {el_used:,} сим, OR ${or_spent:.3f}")
    if bad:
        print("послушать вручную:", "; ".join(bad))


if __name__ == "__main__":
    main()
