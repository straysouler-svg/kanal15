"""Опрос топ-моделей OpenRouter по voice conversion для «Канала 15» (24.11, по слову Дмитрия).
Текстовые модели, без аудио. Ответы -> reports/openrouter_vc_advice_*.md
"""
import json
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = (ROOT / "openrouter_key.txt").read_text(encoding="utf-8").strip()
URL = "https://openrouter.ai/api/v1/chat/completions"
OUT = ROOT / "reports"
OUT.mkdir(exist_ok=True)

MODELS = ["anthropic/claude-opus-5.5", "openai/gpt-5.6-terra-pro", "x-ai/grok-4.7"]

BRIEF = """Ты — эксперт по обработке аудио и нейросетевому синтезу/конверсии голоса. Помоги с архитектурным решением.

КОНТЕКСТ
Офлайн Python-приложение «Канал 15» — имитация CB-рации дальнобойщиков для симулятора. Голоса ~18 персонажей и ~20 проезжих — заранее сгенерированные wav (ElevenLabs / gpt-audio / XTTS). Поверх работает DSP-модуль на numpy/scipy (16 кГц моно): сдвиг rate БЕЗ компенсации питча («магнитофонная лента»), EQ с резонансом, tanh-клиппинг, пресеты дистанции (near/far/flyby), VOX-обрезка. GPU у пользователей не гарантирован, у разработчика GPU есть. Реплики пре-генерируются на этапе сборки, воспроизведение строго офлайн.

ПРОБЛЕМА
«Магнитофонная лента» меняет питч и тембр вместе: на больших сдвигах получается мультяшная «беличья» речь (был инцидент на стриме — архетип «нервный» с rate 1.06 звучал как ускоренная запись). Хотим ПОЛНУЮ смену тембра голоса (другой человек/возраст/пол) из готовых wav БЕЗ потери качества и произношения, в идеале «модуляция на лету».

ВОПРОСЫ
1. Архитектура: нейросетевая voice conversion (RVC и подобные) на этапе пре-генерации банка реплик VS классический DSP (WORLD vocoder, TD-PSOLA, раздельный pitch/formant shift, Rubber Band) — что даст лучшее качество при нашей офлайн-схеме? Где граница «классики хватает»?
2. Классический путь подробнее: какие именно техники меняют тембр без «беличьей речи» — formant shifting без pitch shift? раздельный pitch+formant (WORLD/Harvest)? LPC-ресинтез? Насколько это уступает нейросетям по натуральности для русской речи?
3. Real-time для живой речи пользователя (локальный Whisper уже стоит): реален ли streaming VC (RVC/w-okada/MeanVC) на CPU? Минимальный GPU? Какой latency-бюджет приемлем для имитации CB-рации (там и так канальный шум и паузы — может, 0.5–1 с терпимо)?
4. Пайплайн в Python: конкретные библиотеки и порядок цепочки (VC -> EQ/клиппинг/дистанция или наоборот?), подводные камни ресемплинга 16/24/48 кГц.
5. Русская речь: особенности (шипящие/сибилянты, ударения, диапазон F0), как быстро валидировать качество конверсии (метрики + слуховой QA чек-лист).
6. Наш текущий план: «RVC-конверсия на этапе сборки релиза (пакетно, на машине разработчика), live-конверсия голоса пользователя — отложенная опция под GPU». Покритикуй, что упускаем? Лицензии: проект бесплатный опенсорс (RVC — MIT подходит, GPL/non-commercial — нет).

Ответ структурируй по вопросам, пиши по-русски, конкретно, с названиями библиотек/репозиториев. Без воды."""


def ask(model):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": BRIEF}],
        "max_tokens": 4000,
    }).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.loads(r.read().decode("utf-8"))
        text = d["choices"][0]["message"]["content"]
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(f"пустой content от {model}: finish={d['choices'][0].get('finish_reason')}")
        name = model.split("/")[1].replace(":", "_")
        (OUT / f"openrouter_vc_advice_{name}_2026-11-24.md").write_text(
            f"# Совет {model} по voice conversion (24.11.2026)\n\n{text}", encoding="utf-8")
        print(f"OK {model}: {len(text)} chars")
    except Exception as e:
        print(f"FAIL {model}: {e}")


def main():
    threads = [threading.Thread(target=ask, args=(m,)) for m in MODELS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
