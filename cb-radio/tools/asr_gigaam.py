"""GigaAM v3 (sherpa-onnx, Сбер) — распознавание для QA сухих TTS-треков.

Только для dry-записей: на звуке с радиоэффектом кабины сыплется (там — faster-whisper).
Веса и параметры init (feature_dim=64, model_type="nemo_transducer") проверены 18.11.
"""
from pathlib import Path

import numpy as np

WS_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = WS_ROOT / "build" / "sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16"

_REC = None


def find_model_dir(explicit=""):
    """-> папка модели или None. explicit — из конфига; иначе ищем cb-radio/models/gigaam-v3,
    затем build/sherpa-onnx-... (дев-дерево). Решение о бандле модели в установщик — на релизе."""
    if explicit:
        d = Path(explicit)
        return d if (d / "encoder.int8.onnx").exists() else None
    here = Path(__file__).resolve()
    for cand in (here.parents[1] / "models" / "gigaam-v3",
                 WS_ROOT / "build" / "sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16"):
        if (cand / "encoder.int8.onnx").exists():
            return cand
    return None


def recognizer(model_dir=""):
    global _REC
    if _REC is None:
        import sherpa_onnx
        d = find_model_dir(model_dir)
        if d is None:
            raise FileNotFoundError(f"модель GigaAM не найдена (gigaam_model_dir={model_dir!r})")
        _REC = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(d / "encoder.int8.onnx"),
            decoder=str(d / "decoder.onnx"),
            joiner=str(d / "joiner.onnx"),
            tokens=str(d / "tokens.txt"),
            num_threads=4,
            sample_rate=16000,
            feature_dim=64,
            decoding_method="greedy_search",
            model_type="nemo_transducer",
        )
    return _REC


def unload():
    """Выгрузка по простою (тот же механизм IDLE_UNLOAD_S, что у whisper)."""
    global _REC
    _REC = None


def heard_text(x, model_dir=""):
    """x — float32 mono 16 кГц (диапазон [-1,1]) -> распознанный текст."""
    rec = recognizer(model_dir)
    stream = rec.create_stream()
    stream.accept_waveform(16000, np.clip(x, -1.0, 1.0).astype(np.float32))
    rec.decode_stream(stream)
    return stream.result.text
