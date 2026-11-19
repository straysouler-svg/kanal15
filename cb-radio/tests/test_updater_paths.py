# Тесты валидации manifest-relative путей в updater (промт стабилизации 2026-11-19, P2-11).
# Запуск из корня cb-radio:  python -m unittest discover -s tests -v
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import updater  # noqa: E402


class TestCheckRelPath(unittest.TestCase):
    def assert_bad(self, rel):
        why = updater.check_rel_path(rel)
        self.assertIsNotNone(why, f"{rel!r} должен быть отклонён")

    def assert_ok(self, rel):
        why = updater.check_rel_path(rel)
        self.assertIsNone(why, f"{rel!r} должен проходить: {why}")

    def test_safe_paths(self):
        for rel in ("app/cb_radio.py", "audio/fx/kerchunk.ogg", "README.md", "app/sub/dir/file.txt",
                    "app/", "phrases/level3_eleven.json", "map/cities.json", "version.json",
                    "installer/plugins/scs-telemetry.dll"):
            self.assert_ok(rel)

    def test_absolute_posix(self):
        self.assert_bad("/etc/passwd")
        self.assert_bad("/app/cb_radio.py")

    def test_absolute_windows(self):
        self.assert_bad("C:/Windows/System32/drivers/etc/hosts")
        self.assert_bad("c:\\Windows\\System32\\x.dll")
        self.assert_bad("D:anything.txt")                    # диск без слеша
        self.assert_bad("C:app/file.py")

    def test_unc_and_device_paths(self):
        self.assert_bad("\\\\server\\share\\x.dll")
        self.assert_bad("//server/share/x.dll")
        self.assert_bad("\\\\?\\C:\\Windows\\x")

    def test_parent_traversal(self):
        self.assert_bad("../config.json")
        self.assert_bad("app/../../config.json")
        self.assert_bad("..\\..\\config.json")
        self.assert_bad("app/../../../Windows/x.dll")

    def test_ads_and_colon(self):
        self.assert_bad("app/cb_radio.py:stream")
        self.assert_bad("app/file.txt:$DATA")

    def test_reserved_device_names(self):
        self.assert_bad("CON")
        self.assert_bad("app/NUL")
        self.assert_bad("app/aux.txt")
        self.assert_bad("app/PRN")

    def test_empty_and_garbage(self):
        self.assert_bad("")
        self.assert_bad(None)
        self.assert_bad(42)
        self.assert_bad("app//file.py")                       # пустой сегмент
        self.assert_bad("app/./file.py")
        self.assert_bad("app\x00/file.py")


class TestBadManifestPaths(unittest.TestCase):
    def test_files_and_managed_checked(self):
        m = {"files": {"../evil.py": ["aa", 1]}, "managed": ["app/"]}
        bad = updater.bad_manifest_paths(m)
        self.assertEqual(len(bad), 1)
        self.assertIn("../evil.py", bad[0])

    def test_clean_manifest(self):
        m = {"files": {"app/cb_radio.py": ["aa", 1]}, "managed": list(updater.MANAGED)}
        self.assertEqual(updater.bad_manifest_paths(m), [])


class TestCheckRejectsBadManifest(unittest.TestCase):
    """Интеграция: _check() отклоняет подписанный манифест с небезопасным путём (подпись валидацию не отменяет)."""

    def _check_manifest(self, manifest):
        orig_get, orig_verify = updater._get, updater.ed25519.verify
        try:
            updater.ed25519.verify = lambda *a, **k: True    # подпись «сошлась», путь всё равно ловим
            updater._get = lambda url, timeout=30: (b"ab" * 64 if url.endswith(".sig")
                                                    else json.dumps(manifest).encode("utf-8"))
            with tempfile.TemporaryDirectory() as td:
                (Path(td) / "update" / "staged").mkdir(parents=True)   # _check пишет plan.json туда
                u = updater.Updater(td, {"update": {"url": "https://example.invalid", "channel": "public"}}, "1.0")
                return u._check()
        finally:
            updater._get, updater.ed25519.verify = orig_get, orig_verify

    def test_bad_path_rejected(self):
        m = {"version": "9.9.9", "files": {"../../Windows/evil.dll": ["aa", 1]}, "managed": list(updater.MANAGED)}
        self.assertIn("отклонено", self._check_manifest(m))

    def test_good_manifest_not_rejected_by_paths(self):
        import hashlib
        blob = b"hello"
        m = {"version": "9.9.9", "base": "", "files": {"app/x.txt": [hashlib.sha256(blob).hexdigest(), len(blob)]},
             "managed": list(updater.MANAGED)}

        orig_get, orig_verify = updater._get, updater.ed25519.verify
        try:
            updater.ed25519.verify = lambda *a, **k: True
            updater._get = lambda url, timeout=30: (b"ab" * 64 if url.endswith(".sig")
                                                    else blob if "/blobs/" in url
                                                    else json.dumps(m).encode("utf-8"))
            with tempfile.TemporaryDirectory() as td:
                u = updater.Updater(td, {"update": {"url": "https://example.invalid", "channel": "public"}}, "1.0")
                result = u._check()
        finally:
            updater._get, updater.ed25519.verify = orig_get, orig_verify
        self.assertNotIn("отклонено", result)
        self.assertIn("9.9.9", result)


if __name__ == "__main__":
    unittest.main()
