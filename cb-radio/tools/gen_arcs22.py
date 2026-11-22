# -*- coding: utf-8 -*-
"""22.11: озвучка пакета «арки вперёд» (56 реплик: kofe-арка, поломки, news_followup, Муся).
EL в гео-блоке (как у утренних партий) — всё через OpenRouter gpt-audio; голоса подобраны
под тембры персонажей (EL-акторы догенерируются на EL при появлении VPN: manifest sig
отличается -> gen_eleven перезапишет дорожки штатно).

  OR_BUDGET=1.0 G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_arcs22.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge          # noqa: E402  (budget guard + save/remix plumbing)
import gen_openrouter as gor     # noqa: E402
import gen_level3 as g           # noqa: E402
import numpy as np               # noqa: E402
import soundfile as sf           # noqa: E402
import remix                     # noqa: E402

ROOT = g.ROOT
BUDGET = float(os.environ.get("OR_BUDGET", "1.0"))

# gpt-audio голоса для EL-актёров (подбор по тембру; совпадения с живыми gpt-голосами — разные стили)
VOICE = {"bahti": "verse", "sova": "shimmer", "mihalych": "ash", "boroda": "onyx",
         "professor": "alloy", "yanek": "sage", "stas": "verse", "rustam": "ballad",
         "vitek": "verse", "petrovna": "sage", "kardan": "echo", "lisa": "marin", "ment": "ash"}

POOLS = [("quest", k) for k in ("kofe_hook", "kofe_support", "kofe_scene", "kofe_after")] \
    + [("breakdown", a) for a in ("mihalych", "boroda", "professor", "vitek", "yanek", "petrovna")] \
    + [("news_followup", k) for k in ("vitek", "stas", "boroda", "kardan", "mihalych", "sova", "general")] \
    + [("story", k) for k in ("musya", "musya_more")]


def main():
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    total = 0.0
    made = 0
    for group, kind in POOLS:
        lines = data["reactions"][group][kind]
        d = ROOT / "audio" / "reactions" / group / kind
        d.mkdir(parents=True, exist_ok=True)
        man_f = d / "manifest.json"
        man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {}
        for i, ln in enumerate(lines, 1):
            n = f"{i:02d}"
            a = data["actors"][ln["actor"]]
            voice = VOICE[ln["actor"]]
            sig = f"arcs22-gpt:{voice}|{ln['text']}"
            if man.get(n) == sig and (d / f"{n}.wav").exists():
                continue
            ge._stress_gate(ln["text"])          # стоп по неподтверждённым ударениям (прогон чист)
            best = None
            for attempt in range(3):
                if ge._or_spent[0] >= BUDGET:
                    print(f"! бюджет {BUDGET}$ исчерпан на {total:.3f}$ — стоп, остальное догенерируем позже")
                    raise SystemExit(2)
                x, cost = gor.tts(ln["text"], voice, a.get("style", ""))
                ge._or_spent[0] += cost
                total += cost
                ok, r, why = gor.check(x, ln["text"], a.get("style", ""))
                print(f"[{group}/{kind}] {ln['actor']} {n} ${cost:.4f} (всего {total:.3f}) "
                      f"{'OK' if ok else why}")
                if best is None or (ok, r) > (best[0], best[1]):
                    best = (ok, r, x)
                if ok:
                    break
            sf.write(d / f"{n}_dry.wav", best[2], g.SR)
            rng = np.random.default_rng(abs(hash((str(d), i))) % 2**32)
            sf.write(d / f"{n}.wav", remix.render(best[2], a, False, rng), g.SR)
            man[n] = sig
            man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
            made += 1
        (d / "index.json").write_text(json.dumps({"actors": [x["actor"] for x in lines]}, ensure_ascii=False),
                                      encoding="utf-8")
    print(f"готово: {made} дорожек, OpenRouter ${total:.3f} (кап {BUDGET}$)")


if __name__ == "__main__":
    main()
