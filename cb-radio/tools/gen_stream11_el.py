# -*- coding: utf-8 -*-
"""Догон EL-части партии стрима #11 (20.11): reactions (остались EL-строки) + сцена sova_ahmatova.
Если ElevenLabs отдаёт geo-restriction — стоп по протоколу, gpt-audio уже готово.

  OR_BUDGET=3 G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_stream11_el.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402


def main():
    data = ge.load_phrases()
    used = ge.reactions(data)
    print(f"reactions готово; EL символов: {used}; OpenRouter: ${ge._or_spent[0]:.3f}")
    used2 = ge.scenes(data)
    print(f"scenes готово; EL символов: {used2}; OpenRouter: ${ge._or_spent[0]:.3f}")


if __name__ == "__main__":
    main()
