"""Collect all cities of the standard map from extracted def/city/*.sii (base + map DLCs).
-> map/city_list.json: [{"token","name","country","source"}]"""
import json, re
from pathlib import Path
EX = Path(__file__).resolve().parents[1] / "map" / "extracted"
out, seen = [], set()
for arch in sorted(EX.iterdir()):
    cdir = arch / "def" / "city"
    files = sorted(list(cdir.glob("*.sui")) + list(cdir.glob("*.sii"))) if cdir.is_dir() else []
    if not cdir.is_dir():
        continue
    for f in files:
        t = f.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"city_data\s*:\s*city\.(\w+)\s*\{(.*?)\n\}", t, re.S):
            tok, body = m.group(1), m.group(2)
            name = re.search(r'city_name\s*:\s*"([^"]*)"', body)
            country = re.search(r"country\s*:\s*(\w+)", body)
            if tok in seen:
                continue
            seen.add(tok)
            out.append({"token": tok, "name": name.group(1) if name else tok,
                        "country": country.group(1) if country else "?", "source": arch.name})
(EX.parent / "city_list.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
from collections import Counter
print(len(out), "cities;", dict(Counter(c["source"] for c in out)))
print(dict(Counter(c["country"] for c in out)))
