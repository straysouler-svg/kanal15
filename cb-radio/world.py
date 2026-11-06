"""Living highway: every character drives his own route over a road network of the real cities;
you hear only those within radio range. World units = ETS2 world meters (telemetry coordinates).

Road network: each city (map/cities_full.json, 382 cities) is linked to its nearest neighbours (+ links that
join separate pieces, e.g. ferries). Drivers take jobs city -> city along the shortest path, rest on arrival,
drive by their schedule on GAME time (Тень at night).

Encounters are CROSSINGS, not chasing:
  * when the channel has been quiet for a while, a free driver gets a job whose path passes through the
    city ahead of you, timed to get there about when you do (oncoming / crossing), or - sometimes - a job in
    your direction starting near you (a companion, at most one at a time, different speed, own fork later);
  * a driver who left your range is not sent to you again for COOLDOWN_S;
  * a route is never changed while the driver is in range; after the meeting he just follows his job.
"""
import heapq
import json
import math
import random
from pathlib import Path

import sys  # noqa: E402
ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CITIES = ROOT / "map" / "cities_full.json"
STATE = ROOT / "world_state.json"
HAZ = ROOT / "map" / "hazards.json"          # cameras learned from your fines (the 'people's map')


def load_cities():
    try:
        d = json.loads(CITIES.read_text(encoding="utf-8"))
        return {t: (c["name"], c["country"], c["x"], c["z"]) for t, c in d.items()}
    except (OSError, ValueError, KeyError):
        return {}


class Roads:
    def __init__(self, cities, k=4, max_link=26000):
        self.c = cities
        toks = list(cities)
        self.adj = {t: {} for t in toks}
        for t in toks:
            x, z = cities[t][2], cities[t][3]
            near = sorted((math.hypot(cities[u][2] - x, cities[u][3] - z), u) for u in toks if u != t)
            for d, u in near[:k]:
                if d <= max_link or not self.adj[t]:
                    self.adj[t][u] = self.adj[u][t] = d
        self._join_components()

    def _components(self):
        seen, comps = set(), []
        for t in self.adj:
            if t in seen:
                continue
            stack, comp = [t], []
            seen.add(t)
            while stack:
                v = stack.pop()
                comp.append(v)
                for u in self.adj[v]:
                    if u not in seen:
                        seen.add(u)
                        stack.append(u)
            comps.append(comp)
        return comps

    def _join_components(self):
        """Islands / separate pieces get a link to the nearest other piece (= a ferry or a long road)."""
        while True:
            comps = self._components()
            if len(comps) <= 1:
                return
            comps.sort(key=len)
            a = comps[0]
            rest = [t for comp in comps[1:] for t in comp]
            best = min(((math.hypot(self.c[u][2] - self.c[v][2], self.c[u][3] - self.c[v][3]), u, v)
                        for u in a for v in rest))
            d, u, v = best
            self.adj[u][v] = self.adj[v][u] = d

    def path(self, a, b, via=None):
        if via:
            p1, p2 = self.path(a, via), self.path(via, b)
            return p1 + p2[1:] if p1 and p2 else None
        dist, prev, pq = {a: 0.0}, {}, [(0.0, a)]
        while pq:
            d, v = heapq.heappop(pq)
            if v == b:
                break
            if d > dist.get(v, 1e18):
                continue
            for u, w in self.adj[v].items():
                nd = d + w
                if nd < dist.get(u, 1e18):
                    dist[u], prev[u] = nd, v
                    heapq.heappush(pq, (nd, u))
        if b not in dist:
            return None
        out = [b]
        while out[-1] != a:
            out.append(prev[out[-1]])
        return out[::-1]

    def xz(self, t):
        return self.c[t][2], self.c[t][3]

    def nearest(self, x, z):
        return min(self.c, key=lambda t: (self.c[t][2] - x) ** 2 + (self.c[t][3] - z) ** 2)


class Driver:
    def __init__(self, key, speed, schedule):
        self.key, self.base_speed, self.schedule = key, speed, schedule
        self.speed = speed
        self.route = []          # city tokens; the driver is between route[0] and route[1]
        self.x = self.z = None
        self.resting = 0.0
        self.cooldown = 0.0      # seconds until he may be sent to meet you again
        self.companion = False
        self.cargo = None        # real cargo when his job comes from the game's freight market
        self.lanes = []          # his own cities («Направления водителей.md»): the answer to «куда едешь?»
        self.goal, self.goal_for = None, None    # his lane city now + the route end it was chosen for


class World:
    def __init__(self, cfg, actors):
        w = cfg.get("world") or {}
        self.range = float(w.get("range_m", 6500))   # ~5 min for an oncoming truck at 85 km/h each
        self.quiet_s = float(w.get("spawn_after_quiet_s", 150))
        # a new meeting even while 1-2 drivers are near (user 2026-11-04: always Ласточка + Борода, new ones never came)
        self.meet_every_s = float(w.get("meet_every_s", 480))
        self.since_meet = 0.0
        self.cooldown_s = float(w.get("cooldown_s", 3600))
        self.companion_chance = float(w.get("companion_chance", 0.25))
        self.max_inside = 3           # no new meeting while this many are near (the «Эфир» level, set_air)
        self.cooldown_factor = 1.0    # «Эфир»: how soon the same driver may meet you again
        self.cities = load_cities()
        self.ok = len(self.cities) > 50
        self.roads = Roads(self.cities) if self.ok else None
        self.drivers = {}
        self.hour = 12.0
        for key, a in actors.items():
            if a.get("extra"):
                continue                      # nameless passers-by (foreigners) are not simulated drivers
            sched = a.get("schedule", "20-07" if key == "ten" else "06-22")
            drv = Driver(key, float(a.get("speed", random.uniform(19, 24))), sched)
            drv.meet_weight = float(a.get("meet_weight", 1.0))     # < 1: a rare guest (Тень)
            drv.cooldown_s = float(a.get("cooldown_s", self.cooldown_s))
            drv.cooldown_base = drv.cooldown_s
            drv.lanes = [c for c in a.get("lanes", []) if c in self.cities]
            self.drivers[key] = drv
        self.inside, self.entered, self.left = set(), [], []
        self.quiet = 0.0
        self.game_min = 0.0
        self.met = {}                 # key -> {"count": encounters with you, "last": game minute}
        try:
            self.hazards = [dict(h, until=None) for h in json.loads(HAZ.read_text(encoding="utf-8"))]
        except (OSError, ValueError):
            self.hazards = []
        self.px = self.pz = None
        self.hx, self.hz, self.pspeed = 1.0, 0.0, 0.0
        self.dest, self.ppath, self._path_t = None, [], 0.0   # your job: destination city + your way there
        self.company = None          # company.Company: real job offers + your hired drivers (from the save)
        self._hired_t, self.hired_pos = 0.0, {}
        if self.ok:
            self._load()

    # ---------------------------------------------------------------- schedule (game time)
    @staticmethod
    def is_night(game_min):
        h = (game_min % 1440) / 60
        return h >= 21.5 or h < 6

    @staticmethod
    def on_shift(schedule, hour):
        """schedule "HH-HH" in game hours (may wrap midnight, e.g. "20-07"); "any" = always;
        old values "day"/"night" still work."""
        s = str(schedule or "06-22")
        if s == "any":
            return True
        if s in ("day", "night"):
            s = "06-22" if s == "day" else "20-07"
        try:
            a, b = (float(v) for v in s.split("-"))
        except ValueError:
            return True
        return a <= hour < b if a < b else (hour >= a or hour < b)

    def active(self, d, night=None):
        return self.on_shift(d.schedule, self.hour)

    # ---------------------------------------------------------------- jobs
    def _place_at_start(self, d):
        d.x, d.z = self.roads.xz(d.route[0])

    def real_offer(self, near, max_from=40000, to_dir=None, lo=30000, hi=400000):
        """A real freight-market job (from the save) starting at / near city `near`:
        -> (src, dst, cargo) or None. to_dir=(ux, uz): the target must lie that way."""
        offers = getattr(self.company, "offers", None)
        if not offers or near not in self.cities:
            return None
        nx, nz = self.roads.xz(near)
        cand = []
        for src, dst, cargo in offers:
            if src not in self.cities or dst not in self.cities:
                continue
            sx, sz = self.roads.xz(src)
            if math.hypot(sx - nx, sz - nz) > max_from:
                continue
            tx, tz = self.roads.xz(dst)
            dd = math.hypot(tx - sx, tz - sz)
            if not lo < dd < hi:
                continue
            if to_dir and ((tx - sx) * to_dir[0] + (tz - sz) * to_dir[1]) / dd < 0.3:
                continue
            cand.append((src, dst, cargo))
        return random.choice(cand) if cand else None

    def _new_job(self, d, start=None):
        start = start or (d.route[-1] if d.route else random.choice(list(self.cities)))
        off = self.real_offer(start) if random.random() < 0.85 else None
        if off:                                        # a real job from the game's freight market
            p = self.roads.path(start, off[0]) or [start]
            q = self.roads.path(off[0], off[1])
            if q and len(p + q[1:]) > 1:
                d.route, d.cargo = p + q[1:], off[2]
                if d.x is None:
                    self._place_at_start(d)
                d.speed, d.companion = d.base_speed, False
                self._maybe_post(d)
                return
        d.cargo = None
        sx, sz = self.roads.xz(start)
        cands = [t for t in self.cities if 30000 < math.hypot(self.cities[t][2] - sx, self.cities[t][3] - sz) < 140000]
        for _ in range(10):
            p = self.roads.path(start, random.choice(cands or list(self.cities)))
            if p and len(p) > 1:
                d.route = p
                break
        if d.x is None:
            self._place_at_start(d)
        d.speed, d.companion = d.base_speed, False
        self._maybe_post(d)

    def _advance(self, d, dt):
        step = d.speed * dt
        while step > 0 and len(d.route) > 1:
            tx, tz = self.roads.xz(d.route[1])
            rem = math.hypot(tx - d.x, tz - d.z)
            if rem <= step:
                d.x, d.z = tx, tz
                d.route.pop(0)
                step -= rem
            else:
                d.x += (tx - d.x) / rem * step
                d.z += (tz - d.z) / rem * step
                step = 0
        if len(d.route) <= 1:                          # job done: unload / rest, then a new job
            d.resting = random.uniform(180, 900)
            self._new_job(d, d.route[-1] if d.route else None)

    # ---------------------------------------------------------------- your way (job destination from telemetry)
    def set_job(self, dest):
        """dest = destination city id from the telemetry (e.g. "cordoba"); None/unknown = no job / free drive."""
        dest = dest if dest in self.cities else None
        if dest != self.dest:
            self.dest, self._path_t = dest, 0.0
            if not dest:
                self.ppath = []
            return True
        return False

    def _update_path(self, dt):
        """Your way to the destination over our road network, recomputed once a minute (you may take another road)."""
        self._path_t -= dt
        if not self.dest or self.px is None or self._path_t > 0:
            return
        self._path_t = 60.0
        p = self.roads.path(self.roads.nearest(self.px, self.pz), self.dest) or []
        if len(p) > 1:
            x0, z0 = self.roads.xz(p[0])
            if (x0 - self.px) * self.hx + (z0 - self.pz) * self.hz < 0:     # the nearest city is already behind you
                p = p[1:]
        self.ppath = p

    def path_ahead(self):
        """[(distance along your way, city)] from where you are now."""
        out, x, z, acc = [], self.px, self.pz, 0.0
        for t in self.ppath:
            cx, cz = self.roads.xz(t)
            acc += math.hypot(cx - x, cz - z)
            out.append((acc, t))
            x, z = cx, cz
        return out

    def _on_my_way(self, hx_, hz_, max_ahead=40000, tol=2500):
        """Is this point on your way ahead (within tol of the road, up to max_ahead along it)?"""
        x, z, acc = self.px, self.pz, 0.0
        for t in self.ppath:
            cx, cz = self.roads.xz(t)
            sx, sz = cx - x, cz - z
            seg2 = sx * sx + sz * sz
            u = max(0.0, min(1.0, ((hx_ - x) * sx + (hz_ - z) * sz) / seg2)) if seg2 > 0 else 0.0
            if math.hypot(x + u * sx - hx_, z + u * sz - hz_) < tol and (acc > 0 or u > 0.02):
                return True
            acc += math.sqrt(seg2)
            if acc > max_ahead:
                break
            x, z = cx, cz
        return False

    # ---------------------------------------------------------------- encounters
    def _city_ahead(self, lo=4000, hi=20000):
        if self.ppath:                                     # the next city on your way (the road may bend)
            for along, t in self.path_ahead():
                if lo < along < hi:
                    return along, t
        best = None
        for t, (_, _, x, z) in self.cities.items():
            dx, dz = x - self.px, z - self.pz
            dist = math.hypot(dx, dz)
            if lo < dist < hi and (dx * self.hx + dz * self.hz) / dist > 0.75:
                if best is None or dist < best[0]:
                    best = (dist, t)
        return best

    def _city_dir(self, ox, oz, ux, uz, lo=15000, hi=60000, cos_min=0.6):
        """A city lo..hi away from (ox,oz) in direction (ux,uz)."""
        c = []
        for t, (_, _, x, z) in self.cities.items():
            dx, dz = x - ox, z - oz
            dist = math.hypot(dx, dz)
            if lo < dist < hi and (dx * ux + dz * uz) / dist > cos_min:
                c.append(t)
        return random.choice(c) if c else None

    def schedule_meeting(self, night):
        ahead = self._city_ahead()
        free = [d for d in self.drivers.values() if self.active(d, night) and d.key not in self.inside
                and d.cooldown <= 0 and d.resting <= 0 and d.key != getattr(self, "last_sent", None)]
        if not ahead or not free:
            return None
        dist_r, R = ahead
        rx, rz = self.roads.xz(R)
        eta = dist_r / max(self.pspeed, 15.0)
        # drivers you have never met come first (x3): new characters must actually reach the air
        d = random.choices(free, weights=[getattr(x, "meet_weight", 1.0) *
                                          (3.0 if not self.met.get(x.key, {}).get("count") else 1.0) for x in free])[0]
        companion_busy = any(o.companion for o in self.drivers.values())
        if not companion_busy and random.random() < self.companion_chance:
            # same direction: starts at a city near you, goes far ahead along your way
            start = self.roads.nearest(self.px - self.hx * 2000, self.pz - self.hz * 2000)
            on_way = [t for a, t in self.path_ahead() if 20000 < a < 90000]
            goal = random.choice(on_way) if on_way else self._city_dir(rx, rz, self.hx, self.hz, 20000, 90000)
            p = self.roads.path(start, goal) if goal else None
            if not p or len(p) < 3:
                return None
            d.route, d.companion = p, True
            d.x, d.z = self.px - self.hx * self.range * 0.9, self.pz - self.hz * self.range * 0.9
            d.speed = d.base_speed * random.choice((0.85, 1.15))   # drifts away or overtakes in time
            kind = "попутный"
        else:
            # oncoming or crossing: a job FROM a city beyond R THROUGH R to a city behind you / to the side
            if random.random() < 0.7:
                ahead = self.path_ahead()
                a_r = next((a for a, t in ahead if t == R), None)
                beyond = [t for a, t in ahead if a_r is not None and a_r + 12000 < a < a_r + 60000]
                # oncoming: he comes FROM your way ahead (so he has seen what waits for you there)
                src = random.choice(beyond) if beyond else self._city_dir(rx, rz, self.hx, self.hz, 12000, 50000)
                off = self.real_offer(src, max_from=5000, to_dir=(-self.hx, -self.hz), lo=20000) if src else None
                if off:
                    dst, d.cargo = off[1], off[2]          # a real job: from your way ahead to behind you
                else:
                    dst = self._city_dir(self.px, self.pz, -self.hx, -self.hz, 15000, 80000)
                kind = "встречный"
            else:
                side = random.choice((1, -1))
                sx, sz = -self.hz * side, self.hx * side
                src = self._city_dir(rx, rz, sx, sz, 12000, 50000)
                dst = self._city_dir(rx, rz, -sx, -sz, 15000, 80000)
                kind = "наперерез"
            p = self.roads.path(src, dst, via=R) if src and dst else None
            if not p:
                return None
            # put him on his path so that he reaches R about when you do
            d.route = p
            i = p.index(R)
            back = d.speed * eta
            x, z = rx, rz
            j = i
            while j > 0 and back > 0:
                ax, az = self.roads.xz(p[j - 1])
                seg = math.hypot(ax - x, az - z)
                if seg >= back:
                    x, z = x + (ax - x) / seg * back, z + (az - z) / seg * back
                    back = 0
                else:
                    x, z, back = ax, az, back - seg
                    j -= 1
            d.route = p[j - 1:] if j > 0 and back <= 0 else p[j:]
            if back <= 0 and j > 0:
                d.route = [p[j - 1]] + p[j:]
            d.x, d.z = x, z
            d.speed, d.companion = d.base_speed, False
        d.resting = 0.0
        self.last_sent = d.key                 # if this meeting misses, the next try picks somebody else
        return d.key, kind, self.cities[R][0]

    # ---------------------------------------------------------------- main step
    def set_air(self, p):
        """«Эфир» level from the tray (2026-11-05, Kirill's idea, user's numbers): only RATES change —
        how often meetings happen, how many may be near, how soon the same driver returns. The map logic
        (real roads, honest knowledge, own lanes, shifts) stays the same."""
        self.meet_every_s = float(p["meet_every_s"])
        self.quiet_s = float(p["spawn_after_quiet_s"])
        self.max_inside = int(p["max_inside"])
        self.companion_chance = float(p["companion_chance"])
        self.cooldown_factor = float(p["cooldown_factor"])
        for d in self.drivers.values():
            d.cooldown_s = getattr(d, "cooldown_base", self.cooldown_s) * self.cooldown_factor
            d.cooldown = min(d.cooldown, d.cooldown_s)

    def summon(self, key=None):
        """TEST: put a driver right next to you as a companion (2 km behind, your way). -> key or None.
        Only drivers on shift can be heard, so an off-shift key is refused."""
        if self.px is None:
            return None
        night = self.is_night(self.game_min)
        if key:
            cands = [self.drivers[key]] if key in self.drivers and self.active(self.drivers[key], night) else []
        else:
            cands = [d for d in self.drivers.values() if self.active(d, night) and d.key not in self.inside]
        if not cands:
            return None
        d = random.choice(cands)
        for o in self.drivers.values():
            o.companion = False if o is not d else o.companion
        start = self.roads.nearest(self.px - self.hx * 2000, self.pz - self.hz * 2000)
        on_way = [t for a, t in self.path_ahead() if 20000 < a < 90000]
        goal = random.choice(on_way) if on_way else self._city_dir(self.px, self.pz, self.hx, self.hz, 20000, 90000)
        p = self.roads.path(start, goal) if goal else None
        d.route = p if p and len(p) >= 2 else [start, goal or start]
        d.companion, d.resting, d.cooldown = True, 0.0, 0.0
        d.x, d.z = self.px - self.hx * 2000, self.pz - self.hz * 2000
        d.speed = d.base_speed
        return d.key

    def update(self, px, pz, dt, game_min):
        if not self.ok:
            return None
        if self.px is not None:
            mx, mz = px - self.px, pz - self.pz
            m = math.hypot(mx, mz)
            if m > 1:
                self.hx, self.hz = mx / m, mz / m
            self.pspeed = 0.8 * self.pspeed + 0.2 * (m / dt if dt > 0 else 0)
        self.px, self.pz = px, pz
        self._update_path(dt)
        self.game_min = game_min
        self.hour = (game_min % 1440) / 60
        night = self.is_night(game_min)
        for d in self.drivers.values():
            if d.x is None:
                self._new_job(d)
            d.cooldown = max(0.0, d.cooldown - dt)
            if not self.active(d, night):
                continue
            if d.resting > 0:
                d.resting -= dt
                continue
            self._advance(d, dt)
        # hysteresis: you hear him from `range`, you lose him only beyond range*1.15 (no flicker at the edge)
        now_in = {k for k, d in self.drivers.items() if self.active(d, night) and d.resting <= 0
                  and math.hypot(d.x - px, d.z - pz) < self.range * (1.15 if k in self.inside else 1.0)}
        self.entered = sorted(now_in - self.inside)
        self.left = sorted(self.inside - now_in)
        # a companion doesn't stick to you forever: after 10-18 min he pulls into a parking for a break
        for k in now_in:
            d = self.drivers[k]
            if k in self.entered:
                d.in_since, d.stay = 0.0, random.uniform(600, 1080)
            d.in_since = getattr(d, "in_since", 0.0) + dt
            # nobody sticks to you forever: after 10-18 min near you he pulls into a parking for a break
            # (was companions only -> oncoming ones going your way stayed for hours)
            if d.in_since > getattr(d, "stay", 900):
                d.resting, d.companion = random.uniform(600, 1200), False
                d.went_to_rest = True
        for k in self.left:
            self.drivers[k].cooldown = getattr(self.drivers[k], "cooldown_s", self.cooldown_s)
            m = self.met.setdefault(k, {"count": 0, "last": -1e9})
            m["count"] += 1
            m["last"] = game_min
            self.drivers[k].companion = False
        self.inside = now_in
        self.quiet = 0.0 if now_in else self.quiet + dt
        self.since_meet += dt
        if self.pspeed > 5 and (self.quiet > self.quiet_s or (len(now_in) < self.max_inside and self.since_meet > self.meet_every_s)):
            self.quiet = 0.0
            self.since_meet = 0.0
            return self.schedule_meeting(night)
        return None

    def restrict_to(self, owned):
        """Keep only the map the player owns (2026-11-04: a friend without all DLC). owned = city ids that have
        companies in his save; cities without companies (ports, border posts) stay if their country is owned."""
        if getattr(self, "restricted", False) or not owned:
            return False
        try:
            raw = json.loads(CITIES.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        countries = {self.cities[t][1] for t in owned if t in self.cities}
        keep = {t for t in self.cities if t in owned or (raw.get(t, {}).get("no_company") and self.cities[t][1] in countries)}
        self.restricted = True
        if len(keep) >= len(self.cities) or len(keep) < 30:
            return False
        self.cities = {t: self.cities[t] for t in keep}
        self.roads = Roads(self.cities)
        for d in self.drivers.values():
            if any(t not in keep for t in d.route):
                d.route, d.x, d.z = [], None, None        # gets a new job on the owned map next step
            own = [c for c in d.lanes if c in keep]       # «куда едешь?» names only cities on the player's map
            if own:
                d.lanes = own
        self.ppath, self._path_t, self.hired_pos = [], 0.0, {}
        self.__dict__.pop("_hp_cache", None)
        if self.dest not in keep:
            self.dest = None
        return True

    def hired_near(self, dt, every=20.0):
        """Your own hired drivers (from the save) whose estimated position is within radio range:
        [(driver id, info, distance)]. Position = his job route over our roads at the estimated progress."""
        c = self.company
        if not c or not c.hired or self.px is None:
            return []
        self._hired_t -= dt
        if self._hired_t <= 0:
            self._hired_t = every
            pos = {}
            for k, h in c.hired.items():
                f = c.progress(h, self.game_min)
                if f is None or h["src"] not in self.cities or h["dst"] not in self.cities:
                    continue
                key = (h["src"], h["dst"])
                if getattr(self, "_hp_cache", {}).get(k, (None,))[0] != key:
                    self.__dict__.setdefault("_hp_cache", {})[k] = (key, self.roads.path(*key) or [])
                path = self._hp_cache[k][1]
                if len(path) < 2:
                    continue
                pts = [self.roads.xz(t) for t in path]
                segs = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
                goal, acc = f * sum(segs), 0.0
                for (a, b), sl in zip(zip(pts, pts[1:]), segs):
                    if acc + sl >= goal:
                        u = (goal - acc) / sl if sl else 0
                        pos[k] = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
                        break
                    acc += sl
            self.hired_pos = pos
        out = []
        for k, (x, z) in self.hired_pos.items():
            dist = math.hypot(x - self.px, z - self.pz)
            if dist < self.range:
                out.append((k, c.hired[k], dist))
        return sorted(out, key=lambda t: t[2])

    def in_range(self):
        return {k: min(1.0, math.hypot(self.drivers[k].x - self.px, self.drivers[k].z - self.pz) / self.range)
                for k in self.inside}

    def far(self, factor=2.0):
        """Drivers beyond range but within factor*range: too far to start talking to you, but in a
        conversation with somebody near you they come through - barely. {key: distance/range}"""
        if self.px is None:
            return {}
        out = {}
        for k, d in self.drivers.items():
            if k in self.inside or d.x is None or d.resting > 0:
                continue
            r = math.hypot(d.x - self.px, d.z - self.pz) / self.range
            if r < factor:
                out[k] = r
        return out

    def distance(self, key):
        d = self.drivers.get(key)
        if not d or d.x is None or self.px is None:
            return None
        return math.hypot(d.x - self.px, d.z - self.pz) / self.range

    def place_of(self, key):
        d = self.drivers.get(key)
        if not d or d.x is None:
            return None
        t = self.roads.nearest(d.x, d.z)
        return self.cities[t][0], self.cities[t][1]

    # ---------------------------------------------------------------- what drivers know: posts, cameras, you
    def heading(self, d):
        if len(d.route) < 2:
            return 0.0, 0.0
        tx, tz = self.roads.xz(d.route[1])
        m = math.hypot(tx - d.x, tz - d.z) or 1.0
        return (tx - d.x) / m, (tz - d.z) / m

    def _maybe_post(self, d):
        """On a new job a driver may pass a police post somewhere along the first part of his way."""
        if len(d.route) < 2 or random.random() > 0.35:
            return
        i = random.randrange(0, min(len(d.route) - 1, 3))
        (ax, az), (bx, bz) = self.roads.xz(d.route[i]), self.roads.xz(d.route[i + 1])
        f = random.uniform(0.2, 0.8)
        self.hazards.append({"kind": "police", "x": ax + (bx - ax) * f, "z": az + (bz - az) * f,
                             "until": self.game_min + random.uniform(60, 150), "src": "npc"})

    def add_fine(self, offence, x, z):
        """Your fine from telemetry: a camera stays on the 'people's map' for good, a police post for a while."""
        cam = "camera" in offence
        h = {"kind": "camera" if cam else "police", "x": x, "z": z,
             "until": None if cam else self.game_min + 120, "src": "fine:" + offence}
        if cam and any(math.hypot(o["x"] - x, o["z"] - z) < 300 for o in self.hazards if o["kind"] == "camera"):
            return h
        self.hazards.append(h)
        self._save_hazards()
        return h

    def knowledge(self, key):
        """What this driver can honestly tell you: 'camera'/'police' he has just passed that lies AHEAD of you
        (he comes from there), 'clear' if he comes from there and saw nothing, None if he can't know."""
        d = self.drivers.get(key)
        if not d or d.x is None or self.px is None:
            return None
        dhx, dhz = self.heading(d)
        if dhx * self.hx + dhz * self.hz > -0.3:            # not coming towards you: he hasn't been there
            return None
        self.hazards = [h for h in self.hazards if h["until"] is None or h["until"] > self.game_min]
        seen = []
        for h in self.hazards:
            ax, az = h["x"] - self.px, h["z"] - self.pz
            ad = math.hypot(ax, az)
            bx, bz = h["x"] - d.x, h["z"] - d.z
            bd = math.hypot(bx, bz)
            if self.ppath:
                ahead_of_you = self._on_my_way(h["x"], h["z"])
            else:
                ahead_of_you = ad < 35000 and ad > 0 and (ax * self.hx + az * self.hz) / ad > 0.3
            behind_him = bd < 30000 and bd > 0 and (bx * dhx + bz * dhz) / bd < -0.2
            if ahead_of_you and behind_him:
                seen.append(h["kind"])
        if "camera" in seen:
            return "camera"
        if "police" in seen:
            return "police"
        return "clear"

    def near_big_city(self, min_pop=500000, dist=15000):
        """Name of a big city within dist of you (busy channel around it), else None."""
        if self.px is None:
            return None
        if not hasattr(self, "_pop"):
            try:
                raw = json.loads(CITIES.read_text(encoding="utf-8"))
                self._pop = {t: c.get("population", 0) for t, c in raw.items()}
            except (OSError, ValueError):
                self._pop = {}
        for t, (name, _, x, z) in self.cities.items():
            if self._pop.get(t, 0) >= min_pop and math.hypot(x - self.px, z - self.pz) < dist:
                return name
        return None

    def met_before(self, key):
        m = self.met.get(key)
        return bool(m) and m.get("count", 0) >= 1 and self.game_min - m.get("last", -1e9) > 60

    def _save_hazards(self):
        try:
            cams = [h for h in self.hazards if h["kind"] == "camera"]
            HAZ.write_text(json.dumps(cams, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def goal(self, key):
        """His own city he is heading for (2026-11-05, user: drivers must never say «не знаю, куда еду»).
        Routes stay random; the goal is the lane city that lies the way he is going (towards his route end),
        chosen once per route and kept, so asking twice gives the same answer."""
        d = self.drivers.get(key)
        if not d or not d.lanes or d.x is None:
            return None
        end = d.route[-1] if d.route else None
        if d.goal in d.lanes and d.goal_for == end:
            return d.goal
        if end in d.lanes:
            g = end
        else:
            ex, ez = self.roads.xz(end) if end in self.cities else (d.x + self.hx, d.z + self.hz)
            vx, vz = ex - d.x, ez - d.z
            n = math.hypot(vx, vz) or 1.0

            def along(c):
                if c not in self.cities:                 # a lane city outside the player's map (no DLC): last choice
                    return -2.0                          # (was KeyError('kaunas') → silence on «куда едешь?», Kirill 06.11)
                cx, cz = self.cities[c][2] - d.x, self.cities[c][3] - d.z
                return (vx * cx + vz * cz) / (n * (math.hypot(cx, cz) or 1.0))
            g = max(d.lanes, key=along)
        d.goal, d.goal_for = g, end
        return g

    # ---------------------------------------------------------------- persistence
    def save(self):
        try:
            st = {k: {"x": d.x, "z": d.z, "route": d.route, "resting": d.resting, "cooldown": d.cooldown,
                      "goal": d.goal, "goal_for": d.goal_for}
                  for k, d in self.drivers.items()}
            st["_met"] = self.met
            STATE.write_text(json.dumps(st), encoding="utf-8")
        except OSError:
            pass

    def _load(self):
        try:
            st = json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        self.met = st.pop("_met", {}) or {}
        for k, s in st.items():
            d = self.drivers.get(k)
            if d and s.get("route") and all(t in self.cities for t in s["route"]):
                d.x, d.z, d.route = s["x"], s["z"], s["route"]
                d.resting, d.cooldown = s.get("resting", 0), s.get("cooldown", 0)
                d.goal, d.goal_for = s.get("goal"), s.get("goal_for")
