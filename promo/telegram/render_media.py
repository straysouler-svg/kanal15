"""Собирает аудио для постов канала из уже озвученных реплик рации (ничего не генерирует, кредиты не тратит).

    python render_media.py            # всё из списка ниже -> media/
Сценка: реплики audio/scenes/<id>/NN.wav (уже со звуком рации) + паузы из scene.json -> mp3.
Бухгалтерия: audio/reactions/buh/<kind>/NN.wav -> ogg opus (Telegram покажет как голосовое).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RADIO = HERE.parents[1] / "cb-radio" / "audio"
OUT = HERE / "media"

SCENES = ["domashka", "lisa_kardan", "zhenih", "gudok", "plov_salo"]
BUH = [("speeding", "01"), ("escalation", "01")]


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def scene(sid):
    d = RADIO / "scenes" / sid
    meta = json.loads((d / "scene.json").read_text(encoding="utf-8"))
    pauses = meta.get("pauses", [])
    wavs = sorted(p for p in d.glob("[0-9][0-9].wav"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts = []
        # 0.5 с тишины в начале, дальше пауза перед каждой репликой, 0.8 с в конце
        lead = [0.5] + [pauses[i] if i < len(pauses) else 0.8 for i in range(1, len(wavs))] + [0.8]
        for i, w in enumerate(wavs):
            s = tmp / f"s{i}.wav"
            ffmpeg("-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", str(lead[i]), s)
            parts += [s, w]
        end = tmp / "end.wav"
        ffmpeg("-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", str(lead[-1]), end)
        parts.append(end)
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        out = OUT / f"scene_{sid}.mp3"
        ffmpeg("-f", "concat", "-safe", "0", "-i", lst, "-ar", "48000", "-ac", "1", "-b:a", "128k", out)
    return out


def buh(kind, n):
    src = RADIO / "reactions" / "buh" / kind / f"{n}.wav"
    out = OUT / f"buh_{kind}_{n}.ogg"
    ffmpeg("-i", src, "-c:a", "libopus", "-b:a", "48k", "-ac", "1", "-ar", "48000", out)
    return out


def main():
    OUT.mkdir(exist_ok=True)
    for sid in SCENES:
        print("сценка:", scene(sid).name)
    for kind, n in BUH:
        print("бухгалтерия:", buh(kind, n).name)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
