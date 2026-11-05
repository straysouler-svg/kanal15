"""Real-world lat/lon for every city of map/city_list.json via OpenStreetMap Nominatim (1 request/s, as the
service asks). Resumable. -> map/city_geo.json {token: {"lat", "lon", "display"}}"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIST = ROOT / "map" / "city_list.json"
OUT = ROOT / "map" / "city_geo.json"
UA = "cb-radio-ets2-city-mapper/1.0 (personal hobby project)"
ISO = {"uk": "gb", "netherlands": "nl", "belgium": "be", "germany": "de", "switzerland": "ch", "slovakia": "sk",
       "czech": "cz", "france": "fr", "austria": "at", "luxembourg": "lu", "italy": "it", "poland": "pl",
       "romania": "ro", "bulgaria": "bg", "turkey": "tr", "bosnia": "ba", "serbia": "rs", "montenegro": "me",
       "macedonia": "mk", "albania": "al", "slovenia": "si", "croatia": "hr", "kosovo": "xk", "latvia": "lv",
       "finland": "fi", "russia": "ru", "lithuania": "lt", "estonia": "ee", "hungary": "hu", "greece": "gr",
       "spain": "es", "portugal": "pt", "denmark": "dk", "norway": "no", "sweden": "se"}


def query(name, cc):
    q = urllib.parse.urlencode({"q": name, "format": "json", "limit": 1, "countrycodes": cc,
                                "accept-language": "en"})
    req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    cities = [c for c in json.loads(LIST.read_text(encoding="utf-8")) if c["country"].lower() != "halloween"]
    geo = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    miss = []
    for c in cities:
        if c["token"] in geo:
            continue
        cc = ISO.get(c["country"].lower(), "")
        res = []
        for name in (c["name"], c["token"].replace("_", " ")):
            try:
                res = query(name, cc)
            except Exception as e:
                print("error", c["token"], e)
            time.sleep(1.1)
            if res:
                break
        if res:
            geo[c["token"]] = {"lat": float(res[0]["lat"]), "lon": float(res[0]["lon"]),
                               "display": res[0].get("display_name", "")[:80]}
            OUT.write_text(json.dumps(geo, ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            miss.append(c["token"])
    print(f"geocoded {len(geo)} of {len(cities)}; not found: {miss}")


if __name__ == "__main__":
    main()
