# QA озвучки 150 рекламных роликов: whisper small по языку ролика, порог 0.8.
# Запуск из корня репо: venv с faster-whisper (coop-buddy) → qa_report.json в build/ads150.
import difflib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
ADS = REPO / "build" / "ads150"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def norm(s):
    s = re.sub(r"[^\w\s]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def main():
    ads = {a["n"]: a for a in json.load((ADS / "ads_150.json").open(encoding="utf-8"))}
    manifest = json.load((ADS / "manifest.json").open(encoding="utf-8"))
    only = set(map(int, sys.argv[1].split(","))) if len(sys.argv) > 1 else None

    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")

    report = {}
    fails = []
    for n in sorted(ads):
        if only and n not in only:
            continue
        if manifest.get(str(n), {}).get("status") != "ok":
            continue
        mp3 = ADS / "audio" / f"{n:03d}.mp3"
        if not mp3.exists():
            continue
        lang = ads[n]["lang"]
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t:
            wav = t.name
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
                        "-ar", "16000", "-ac", "1", wav], check=True)
        import soundfile as sf
        data, _ = sf.read(wav, dtype="float32")
        segs, _ = model.transcribe(data, language=lang)
        heard = " ".join(s.text for s in segs)
        ratio = difflib.SequenceMatcher(None, norm(ads[n]["foreign"]), norm(heard)).ratio()
        report[n] = {"ratio": round(ratio, 3), "heard": heard[:200]}
        mark = "OK " if ratio >= 0.8 else "FAIL"
        if ratio < 0.8:
            fails.append(n)
        print(f"#{n:03d} [{lang}] {mark} {ratio:.3f}")
    (ADS / "qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    print(f"\nпровалено: {len(fails)} -> {fails}")


if __name__ == "__main__":
    main()
