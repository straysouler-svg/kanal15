"""Тесты атомарного хранения JSON (P1-8): сбой до replace, сбой при записи,
повреждённый JSON, восстановление из backup, Unicode, повторные сохранения."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json_store  # noqa: E402


class JsonStoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "state.json"
        self.msgs = []
        self.log = self.msgs.append

    def tearDown(self):
        self.dir.cleanup()

    def test_roundtrip_and_unicode(self):
        obj = {"город": "Петрозаводск", "emoji": "♥♥♥", "n": 3}
        json_store.save_json(self.path, obj, log=self.log)
        self.assertEqual(json_store.load_json(self.path, log=self.log), obj)
        self.assertEqual(self.msgs, [])

    def test_repeated_saves_keep_last_and_backup_previous(self):
        json_store.save_json(self.path, {"v": 1}, log=self.log)
        json_store.save_json(self.path, {"v": 2}, log=self.log)
        json_store.save_json(self.path, {"v": 3}, log=self.log)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"v": 3})
        bak = self.path.with_name("state.json.bak")
        self.assertEqual(json.loads(bak.read_text(encoding="utf-8")), {"v": 2})
        self.assertEqual(json_store.load_json(self.path, log=self.log), {"v": 3})
        self.assertFalse((self.path.parent / "state.json.tmp").exists())

    def test_crash_during_write_leaves_old_file(self):
        json_store.save_json(self.path, {"v": 1}, log=self.log)
        with mock.patch("os.fsync", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                json_store.save_json(self.path, {"v": 2}, log=self.log)
        # старый файл цел, .tmp подчищен, диагностика есть
        self.assertEqual(json_store.load_json(self.path, log=self.log), {"v": 1})
        self.assertFalse(list(self.path.parent.glob("state.json.tmp*")))
        self.assertTrue(any("disk full" in m for m in self.msgs))

    def test_crash_between_replaces_recovers_from_tmp_or_backup(self):
        json_store.save_json(self.path, {"v": 1}, log=self.log)
        orig_replace = os.replace

        def flaky_replace(src, dst):
            if str(dst) == str(self.path):      # последний шаг: «сбой питания»
                raise OSError("power loss")
            return orig_replace(src, dst)

        with mock.patch("os.replace", side_effect=flaky_replace):
            with self.assertRaises(OSError):
                json_store.save_json(self.path, {"v": 2}, log=self.log)
        # новые данные не потерялись полностью: либо .tmp, либо .bak содержит старое
        self.assertTrue(list(self.path.parent.glob("state.json.*")))
        # повторное сохранение после «перезагрузки» проходит чисто
        json_store.save_json(self.path, {"v": 3}, log=self.log)
        self.assertEqual(json_store.load_json(self.path, log=self.log), {"v": 3})

    def test_corrupt_main_recovers_from_backup(self):
        json_store.save_json(self.path, {"v": 0}, log=self.log)
        json_store.save_json(self.path, {"v": 1}, log=self.log)
        self.path.write_text('{"v": 2, обрезано', encoding="utf-8")
        obj = json_store.load_json(self.path, log=self.log)
        self.assertEqual(obj, {"v": 0})     # .bak = предыдущая валидная копия
        self.assertTrue(any("восстановлен" in m for m in self.msgs))

    def test_corrupt_main_and_missing_backup_is_not_silent(self):
        self.path.write_text("not json at all", encoding="utf-8")
        self.assertIsNone(json_store.load_json(self.path, log=self.log))
        self.assertTrue(any("с нуля" in m for m in self.msgs))

    def test_corrupt_both(self):
        json_store.save_json(self.path, {"v": 1}, log=self.log)
        self.path.write_text("xxx", encoding="utf-8")
        self.path.with_name("state.json.bak").write_text("yyy", encoding="utf-8")
        self.assertIsNone(json_store.load_json(self.path, log=self.log))
        self.assertGreaterEqual(len(self.msgs), 2)

    def test_missing_file_returns_none(self):
        self.assertIsNone(json_store.load_json(self.path, log=self.log))
        self.assertEqual(self.msgs, [])


if __name__ == "__main__":
    unittest.main()
