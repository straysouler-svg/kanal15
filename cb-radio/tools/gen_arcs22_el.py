# -*- coding: utf-8 -*-
"""22.11: переозвучка пакета «арки вперёд» (56 реплик) настоящими EL-голосами актёров
(EL снова доступен через VPN UK). Штатные voice_id/model/stability актёров из level3_eleven.json,
те же тексты. gpt-версии (манифест arcs22-gpt:*) уходят в бакап-дерево _arcs22_gpt_backup/ рядом
с audio/reactions/. QA: стресс-гейт до синтеза + whisper-обратный контроль (ретраи до 3).

  G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_arcs22_el.py
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge          # noqa: E402
import gen_openrouter as gor     # noqa: E402  (check() = whisper-контроль, без сети)
import gen_level3 as g           # noqa: E402
import remix                     # noqa: E402

ROOT = g.ROOT
POOLS = [("quest", k) for k in ("kofe_hook", "kofe_support", "kofe_scene", "kofe_after")] \
    + [("breakdown", a) for a in ("mihalych", "boroda", "professor", "vitek", "yanek", "petrovna")] \
    + [("news_followup", k) for k in ("vitek", "stas", "boroda", "kardan", "mihalych", "sova", "general")] \
    + [("story", k) for k in ("musya", "musya_more")]
BACKUP = ROOT / "audio" / "reactions" / "_arcs22_gpt_backup"


def main():
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    made, used, bad = 0, 0, []
    for group, kind in POOLS:
        lines = data["reactions"][group][kind]
        d = ROOT / "audio" / "reactions" / group / kind
        man_f = d / "manifest.json"
        man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {}
        # бакап gpt-версий (тех, что ещё не переписаны)
        need_backup = [n for n, sig in man.items() if isinstance(sig, str) and sig.startswith("arcs22-gpt:")]
        if need_backup:
            bd = BACKUP / group / kind
            bd.mkdir(parents=True, exist_ok=True)
            for n in need_backup:
                for f in (d / f"{n}.wav", d / f"{n}_dry.wav"):
                    if f.exists():
                        shutil.copy2(f, bd / f.name)
            print(f"[{group}/{kind}] бакап gpt-версий: {len(need_backup)} дорожек -> {bd.relative_to(ROOT)}")
        for i, ln in enumerate(lines, 1):
            n = f"{i:02d}"
            a = data["actors"][ln["actor"]]
            sig = ge._sig(a, ln["text"])
            if man.get(n) == sig and (d / f"{n}.wav").exists():
                continue
            if a.get("engine") == "gpt-audio":
                # штатный голос этих актёров И ЕСТЬ gpt-audio — первый OR-прогон озвучил их
                # своими голосами; аудио оставляем, манифест переподписываем на EL-стиль sig,
                # чтобы дальнейшие штатные прогоны не перегенерировали их заново
                man[n] = sig
                man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"[{group}/{kind}] {ln['actor']} {n} — gpt-audio актёр, голос уже штатный: переподпись")
                continue
            ge._stress_gate(ln["text"])          # стоп по неподтверждённым ударениям
            best = None
            for attempt in range(3):
                mp3, x, spent = ge.voice(a, ln["text"])     # EL-v3, штатный голос актёра
                used += spent
                ok, r, why = gor.check(x, ln["text"], a.get("style", ""))
                print(f"[{group}/{kind}] {ln['actor']} {n} {len(x) / g.SR:4.1f}c "
                      f"(+{spent} сим, всего {used}) {'OK' if ok else why}")
                if best is None or (ok, r) > (best[0], best[1]):
                    best = (ok, r, mp3, x)
                if ok:
                    break
            if not best[0]:
                bad.append(f"{group}/{kind}/{n}")
                print("   ! так и не чисто — послушать")
            (d / f"{n}.mp3").write_bytes(best[2])
            sf.write(d / f"{n}_dry.wav", best[3], g.SR)
            rng = np.random.default_rng(abs(hash((str(d), i))) % 2**32)
            sf.write(d / f"{n}.wav", remix.render(best[3], a, False, rng), g.SR)
            man[n] = sig
            man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
            made += 1
        (d / "index.json").write_text(json.dumps({"actors": [x["actor"] for x in lines]}, ensure_ascii=False),
                                      encoding="utf-8")
    print(f"готово: {made} дорожек переписано, EL символов потрачено: {used:,}")
    if bad:
        print("послушать вручную:", "; ".join(bad))


if __name__ == "__main__":
    main()
