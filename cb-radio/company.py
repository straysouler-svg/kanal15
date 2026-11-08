"""The player's company and the game's job market, from his own save (read-only, 2026-11-04).

The game autosaves while driving every ~7-10 min (save/autosave_drive). On every new save:
  * offers  - real job offers of the freight market: (source city, target city, cargo)  -> our drivers take
              REAL jobs (живые маршруты);
  * hired   - the player's own hired drivers with their current job -> estimated position on the map;
  * deliveries - new entries in their profit logs since the last save -> the accountant can report them.
Parsing takes ~0.3 s and runs in a background thread; the radio never waits for it."""
import threading
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))   # (frozen: savegame is bundled)
import savegame  # noqa: E402

AVG_KMH = 60.0          # hired drivers' average incl. breaks (game km/h); good enough to place them on a leg


def _city_of(company_id):
    """company.volatile.<company>.<city> -> city id"""
    parts = (company_id or "").split(".")
    return parts[3] if len(parts) >= 4 else ""


class Company:
    def __init__(self, log=print, check_every=30.0):
        self.log, self.check_every = log, check_every
        self.offers, self.hired, self.deliveries = [], {}, []
        self.cities = set()
        self.game_time = None
        self._mtime, self._next, self._busy = None, 0.0, False
        self._profit_counts = None
        self.ok = savegame.SAVES.exists()

    def poll(self):
        """Call often; starts a background re-read when a newer save appears."""
        if not self.ok or self._busy or time.monotonic() < self._next:
            return
        self._next = time.monotonic() + self.check_every
        try:
            p = savegame.newest_save()
            m = p.stat().st_mtime
        except (OSError, ValueError):
            return
        if m == self._mtime:
            return
        self._busy = True
        threading.Thread(target=self._read, args=(p, m), daemon=True).start()

    def _read(self, p, m):
        try:
            time.sleep(2.0)                                  # let the game finish writing the file
            units = savegame.parse(savegame.decrypt(p.read_bytes()))
            self._digest(units)
            self._mtime = m
            n = len(self.hired)
            drv = "твой водитель" if n == 1 else ("твоих водителя" if 2 <= n <= 4 else "твоих водителей")
            self.log(f"компания: сохранение {p.parent.name} — {len(self.offers)} рейсов на бирже, "
                     f"{n} {drv} в рейсах")
        except Exception as e:                               # half-written file, new format...: try next time
            self.log(f"компания: не прочитал сохранение ({e!r})")
        finally:
            self._busy = False

    def _digest(self, u):
        jobs = {j["_id"]: j for j in u.get("job_info", [])}
        offers_by_id = {o["_id"]: o for o in u.get("job_offer_data", [])}
        offers = []
        for c in u.get("company", []):
            src = _city_of(c["_id"])
            for oid in c.get("job_offer") or []:
                o = offers_by_id.get(oid)
                if o and o.get("target") and o.get("cargo"):
                    dst = o["target"].split(".")[-1]
                    if dst and dst != src:
                        offers.append((src, dst, o["cargo"].split(".")[-1]))
        player = (u.get("player") or [{}])[0]
        mine = set(player.get("drivers") or [])
        econ = (u.get("economy") or [{}])[0]
        self.game_time = econ.get("game_time")
        hired, counts, new_deliv = {}, {}, []
        logs = {pl["_id"]: pl for pl in u.get("profit_log", [])}
        entries = {e["_id"]: e for e in u.get("profit_log_entry", [])}
        for d in u.get("driver_ai", []):
            if d["_id"] not in mine:
                continue
            j = jobs.get(d.get("driver_job")) or {}
            src, dst = _city_of(j.get("source_company")), _city_of(j.get("target_company"))
            hired[d["_id"]] = {
                "hometown": d.get("hometown"), "city": d.get("current_city"), "state": d.get("state"),
                "src": src or d.get("current_city"), "dst": dst or d.get("hometown"),
                "cargo": (j.get("cargo") or "").split(".")[-1], "start": j.get("start_time"),
                "km": j.get("planned_distance_km") or 0, "ferry": j.get("ferry_time") or 0,
            }
            pl = logs.get(d.get("profit_log")) or {}
            ents = pl.get("stats_data") or pl.get("entries") or []
            counts[d["_id"]] = len(ents)
            if self._profit_counts is not None and len(ents) > self._profit_counts.get(d["_id"], len(ents)):
                last = entries.get(ents[-1]) if ents else None
                if last:
                    new_deliv.append({"driver": d["_id"], "hometown": d.get("hometown"),
                                      "from": last.get("source_city"), "to": last.get("destination_city"),
                                      "revenue": last.get("revenue", 0), "cargo": last.get("cargo")})
        self.cities = {_city_of(c["_id"]) for c in u.get("company", [])} - {""}   # the map the player owns
        self.offers, self.hired = offers, hired
        self._profit_counts = counts
        self.deliveries.extend(new_deliv)

    def progress(self, h, game_min):
        """0..1 along his job, estimated from the start time and the planned distance."""
        if not h.get("start") or not h.get("km"):
            return None
        total = h["km"] / AVG_KMH * 60 + h.get("ferry", 0)
        return max(0.0, min(1.0, (game_min - h["start"]) / max(total, 1)))
