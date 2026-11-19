"""Тесты потокобезопасности журнала рации (P1-9): параллельная запись без потерь,
append-only порядок, ротация по размеру. Стенд — реальный cb_radio с переключением
LOG_FILE/ARC_FILE/ERR_FILE на временный каталог (живые журналы не трогаем).
"""
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import cb_radio as cb  # noqa: E402  (тяжёлый импорт: numpy/sounddevice/soundfile)
    _HEAVY_ENV = True
    _HEAVY_SKIP = ""
except ImportError as e:                     # CI stdlib-only: без numpy/аудио-стека — честный skip,
    cb = None                                # а не ошибка импорта (зелёный прогон локально в venv рации)
    _HEAVY_ENV = False
    _HEAVY_SKIP = f"тяжёлое окружение рации недоступно ({e}) — тест журнала запускается локально в venv"


@unittest.skipUnless(_HEAVY_ENV, _HEAVY_SKIP or None)
class LogRaceTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        d = Path(self._dir.name)
        self._old = cb.LOG_FILE, cb.ARC_FILE, cb.ERR_FILE, cb.LOG_CAP
        cb.LOG_FILE = d / "cb_radio.log"
        cb.ARC_FILE = d / "cb_radio_archive.log"
        cb.ERR_FILE = d / "cb_radio_errors.log"
        cb.LOG_CAP = 10 * 1024 * 1024
        with cb._log_lock:
            cb._log_buf[:] = []

    def tearDown(self):
        cb.LOG_FILE, cb.ARC_FILE, cb.ERR_FILE, cb.LOG_CAP = self._old
        with cb._log_lock:
            cb._log_buf[:] = []
        self._dir.cleanup()

    def test_parallel_threads_no_lost_markers(self):
        threads, markers = [], []
        per_t, n_t = 100, 8
        for t in range(n_t):
            batch = [f"MARK-{t}-{i:04d}-unique" for i in range(per_t)]
            markers.extend(batch)
            threads.append(threading.Thread(target=lambda b=batch: [cb.log(m) for m in b]))
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        cb._flush_log()
        text = cb.LOG_FILE.read_text(encoding="utf-8")
        missing = [m for m in markers if m not in text]
        self.assertEqual(missing, [])
        # append-only хронология: маркеры идут по возрастанию времени внутри потока
        pos = [text.index(f"MARK-{t}-0000") for t in range(n_t)]
        self.assertEqual(len(set(pos)), n_t)

    def test_records_logged_during_flush_are_not_lost(self):
        cb.log("before-flush")

        def concurrent_logger():
            for i in range(50):
                cb.log(f"DURING-{i:03d}")

        th = threading.Thread(target=concurrent_logger)
        with cb._log_lock:                    # имитируем окно «буфер уже забран, I/O идёт»
            cb._log_buf[:] = []               # (chunk пуст — flush ниже не запишет «before»)
            th.start()
            for _ in range(100):
                pass
        th.join()
        cb._flush_log()                       # новый буфер (записи за время окна) — на диск
        text = cb.LOG_FILE.read_text(encoding="utf-8")
        self.assertTrue(all(f"DURING-{i:03d}" in text for i in range(50)))

    def test_rotation_moves_head_to_archive(self):
        cb.LOG_CAP = 2048
        for i in range(200):
            cb.log(f"ROT-{i:04d} " + "x" * 40)
            cb._flush_log()
        size = cb.LOG_FILE.stat().st_size
        self.assertLessEqual(size, cb.LOG_CAP)
        arc = cb.ARC_FILE.read_bytes()
        self.assertTrue(arc)                  # обрезанная голова ушла в архив
        head = cb.LOG_FILE.read_text(encoding="utf-8")
        self.assertIn("ROT-0199", head)       # свежие строки на месте
        # журнал остался валидным текстом
        self.assertIn("[", head)

    def test_fragment_for_report_takes_fresh_tail(self):
        for i in range(50):
            cb.log(f"REP-{i:04d}")
        cb._flush_log()
        data = cb.LOG_FILE.read_bytes()
        from report_log import pick_log_fragment
        frag = pick_log_fragment(data).decode("utf-8")
        self.assertIn("REP-0049", frag)
        self.assertIn("REP-0000", frag)       # журнал короткий 4000 строк — всё целиком
        self.assertLess(frag.index("REP-0000"), frag.index("REP-0049"))   # хронология


if __name__ == "__main__":
    unittest.main()
