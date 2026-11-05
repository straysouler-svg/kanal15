"""Build the full city table from a few known cities: real lat/lon -> ETS2 world (x, z).

ETS2 draws Europe in a conformal conic projection, scaled and shifted (the UK is shifted on its own). So:
project lat/lon with Lambert conformal conic, then fit an affine transform (rotation+scale+shift, optionally
quadratic) per region on the control points. Control points = verified cities (map/cities.json) + those
records of the failed tour (cities_unverified_backup.json) that agree with the model (they were real camera
placements, only some got the wrong label). Output: map/cities_full.json with "src": verified|confirmed|fit.
"""
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
M = ROOT / "map"
R = 6371.0


def lcc(lat, lon, lat0=50.0, lon0=15.0, sp1=37.0, sp2=65.0):
    f = math.radians
    p1, p2, p0, l0 = f(sp1), f(sp2), f(lat0), f(lon0)
    n = math.log(math.cos(p1) / math.cos(p2)) / math.log(math.tan(math.pi / 4 + p2 / 2) / math.tan(math.pi / 4 + p1 / 2))
    F = math.cos(p1) * math.tan(math.pi / 4 + p1 / 2) ** n / n
    rho0 = R * F / math.tan(math.pi / 4 + p0 / 2) ** n
    rho = R * F / math.tan(math.pi / 4 + f(lat) / 2) ** n
    th = n * (f(lon) - l0)
    return rho * math.sin(th), rho0 - rho * math.cos(th)


def feats(P, order):
    x, y = P[:, 0], P[:, 1]
    cols = [x, y, np.ones_like(x)]
    if order >= 2:
        cols += [x * x, x * y, y * y]
    return np.stack(cols, 1)


def fit(P, G, order):
    A = feats(P, order)
    coef, *_ = np.linalg.lstsq(A, G, rcond=None)
    return coef


def predict(coef, P, order):
    return feats(P, order) @ coef


def loo(P, G, order):
    errs = []
    for i in range(len(P)):
        m = np.ones(len(P), bool)
        m[i] = False
        c = fit(P[m], G[m], order)
        errs.append(np.hypot(*(predict(c, P[i:i + 1], order)[0] - G[i])))
    return np.array(errs)


def main():
    lst = {c["token"]: c for c in json.loads((M / "city_list.json").read_text(encoding="utf-8"))}
    geo = json.loads((M / "city_geo.json").read_text(encoding="utf-8"))
    ver = json.loads((M / "cities.json").read_text(encoding="utf-8"))
    unv = json.loads((M / "cities_unverified_backup.json").read_text(encoding="utf-8"))
    proj = {t: lcc(g["lat"], g["lon"]) for t, g in geo.items()}
    region = lambda t: "uk" if lst[t]["country"].lower() == "uk" else "eu"  # noqa: E731

    ctrl = {t: (c["x"], c["z"], "verified") for t, c in ver.items() if t in proj}
    models = {}
    for it in range(3):                                   # grow the control set with agreeing records
        models = {}
        for reg in ("eu", "uk"):
            ts = [t for t in ctrl if region(t) == reg]
            P = np.array([proj[t] for t in ts])
            G = np.array([ctrl[t][:2] for t in ts])
            order = 2 if reg == "eu" and len(ts) >= 40 else 1
            models[reg] = (fit(P, G, order), order)
            e = loo(P, G, order)
            print(f"it{it} {reg}: {len(ts)} points, order {order}, leave-one-out error median {np.median(e):.0f} m, "
                  f"90% {np.percentile(e, 90):.0f} m, max {e.max():.0f} m")
        added = 0
        for t, c in unv.items():
            if t in ctrl or t not in proj:
                continue
            coef, order = models[region(t)]
            pr = predict(coef, np.array([proj[t]]), order)[0]
            if math.hypot(pr[0] - c["x"], pr[1] - c["z"]) < 1500:
                ctrl[t] = (c["x"], c["z"], "confirmed")
                added += 1
        print(f"   +{added} confirmed from the failed tour")
        if not added:
            break
    out = {}
    for t, c in lst.items():
        if c["country"].lower() == "halloween":
            continue
        if t in ctrl:
            x, z, src = ctrl[t]
        elif t in proj:
            coef, order = models[region(t)]
            x, z = predict(coef, np.array([proj[t]]), order)[0]
            src = "fit"
        else:
            continue
        out[t] = {"name": c["name"], "country": c["country"].lower(), "x": round(float(x), 1),
                  "z": round(float(z), 1), "src": src}
    (M / "cities_full.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print("cities_full:", len(out), dict(Counter(v["src"] for v in out.values())))
    cov = Counter(lst[t]["country"].lower() for t in ctrl)
    print("control points by country:", dict(cov))


if __name__ == "__main__":
    main()
