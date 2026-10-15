"""Trace the route lines drawn on LTA's Annex A maps and georeference them.

LTA published the Punggol routes only as map images (Annex A of the 20 Sep 2025 news
release). This step turns each image into a set of points in SVY21 metres:

1. keep the near-black pixels (the route line and its arrows), drop the right-hand
   legend panel, and drop the numbered stop markers (filled discs, removed with a
   morphological opening);
2. fit an affine pixel->SVY21 transform on the stop markers (control points: the marker
   pixel positions, read by eye, against the OneMap stop positions);
3. refine that transform with an iterative-closest-point fit of the traced pixels to the
   OSM drivable road network, shrinking the match radius from 80 m to 20 m.

The output `data/derived/trace_<route>.csv` is committed. The residuals are written to
`results/trace_fit.json` and reported in the README; they are the honest measure of how
far the traced line can be trusted.

    python -m avready.trace path/to/250920-AV-shuttle-punggol.pdf
"""
from __future__ import annotations

import csv
import json
import sys

import numpy as np

from .common import DATA, RESULTS, routes_config, to_xy
from . import network

# Image index in the PDF (page, image) -> route, legend panel x-limit, and stop-marker
# pixel centres in stop order (read by eye from the images, native resolution).
IMAGES = {
    "PG-R1": {"page": 0, "img": 0, "panel_x": 1055, "markers": [(352, 467), (589, 522), (842, 630), (837, 437)]},
    "PG-R2": {"page": 0, "img": 1, "panel_x": 1035,
              "markers": [(825, 617), (1000, 497), (995, 557), (610, 292), (580, 68), (745, 165), (825, 440)]},
    "PG-R3": {"page": 1, "img": 0, "panel_x": 1055, "markers": [(350, 466), (593, 530), (620, 296), (572, 72), (737, 170)]},
}
DARK = 45          # max channel value for a "route line" pixel
MARKER_OPEN = 6    # opening radius (px) that keeps the ~17 px marker discs but not 3 px lines


def _disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def route_pixels(rgb: np.ndarray, panel_x: int) -> np.ndarray:
    from scipy import ndimage

    dark = (rgb[..., :3].max(axis=2) <= DARK)
    dark[:, panel_x:] = False
    dark[-60:, :80] = False  # scale bar in the bottom-left corner
    blobs = ndimage.binary_opening(dark, structure=_disk(MARKER_OPEN))
    blobs = ndimage.binary_dilation(blobs, structure=_disk(MARKER_OPEN + 6))
    line = dark & ~blobs
    ys, xs = np.nonzero(line)
    return np.c_[xs, ys].astype(float)


def _affine_fit(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    A = np.c_[src, np.ones(len(src))]
    M, *_ = np.linalg.lstsq(A, dst, rcond=None)
    return M  # (3, 2): dst = [src, 1] @ M


def _apply(M, pts):
    return np.c_[pts, np.ones(len(pts))] @ M


def road_samples(net: network.Network, step: float = 4.0) -> np.ndarray:
    pts = []
    seen = set()
    for u, v in net.graph.edges:
        key = (min(u, v), max(u, v))
        if key in seen:
            continue
        seen.add(key)
        (x0, y0), (x1, y1) = net.xy[u], net.xy[v]
        n = max(1, int(np.hypot(x1 - x0, y1 - y0) / step))
        t = np.linspace(0, 1, n + 1)
        pts.append(np.c_[x0 + t * (x1 - x0), y0 + t * (y1 - y0)])
    return np.vstack(pts)


def georeference(pix: np.ndarray, markers, stops_xy, roads: np.ndarray):
    from scipy.spatial import cKDTree

    M0 = _affine_fit(np.asarray(markers, float), np.asarray(stops_xy, float))
    marker_res = np.linalg.norm(_apply(M0, np.asarray(markers, float)) - stops_xy, axis=1)
    tree = cKDTree(roads)

    def icp(M):
        for radius in [80, 80, 60, 60, 45, 45, 35, 35, 25, 25, 20, 20, 20, 20]:
            d, i = tree.query(_apply(M, pix))
            keep = d < radius
            M = _affine_fit(pix[keep], roads[i[keep]])
        d, _ = tree.query(_apply(M, pix))
        return M, d

    # Multi-start: the marker fit can be 50-100 m off, and ICP then locks onto a parallel
    # road. Shift and scale the start around the marker fit and keep the start whose
    # final fit puts the most traced pixels within 15 m of a road.
    centre = pix.mean(axis=0)
    best = None
    for s in (0.95, 1.0, 1.05):
        for dx in (-100, -50, 0, 50, 100):
            for dy in (-100, -50, 0, 50, 100):
                Ms = M0.copy()
                Ms[:2] *= s
                c0, c1 = _apply(M0, centre[None])[0], _apply(Ms, centre[None])[0]
                Ms[2] += (c0 - c1) + np.array([dx, dy])
                M, d = icp(Ms)
                score = float((d < 15).mean())
                if best is None or score > best[0] + 1e-9:
                    best = (score, M, d)
    _, M, d = best
    fit = {
        "marker_rms_m_initial": float(np.sqrt((marker_res ** 2).mean())),
        "icp_median_m": float(np.median(d)),
        "icp_p90_m": float(np.percentile(d, 90)),
        "share_within_15m": float((d < 15).mean()),
        "n_pixels": int(len(pix)),
        "metres_per_pixel": float(np.sqrt(abs(np.linalg.det(M[:2])))),
    }
    return M, fit


def main(pdf_path: str):
    import fitz  # PyMuPDF, only needed for this step

    doc = fitz.open(pdf_path)
    cfg = {r["id"]: r for r in routes_config()["routes"]}
    net = network.build("punggol", "shuttle")
    roads = road_samples(net)
    fits = {}
    for rid, spec in IMAGES.items():
        page = doc[spec["page"]]
        xref = page.get_images(full=True)[spec["img"]][0]
        pm = fitz.Pixmap(doc, xref)
        rgb = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width, pm.n)
        pix = route_pixels(rgb, spec["panel_x"])
        stops = [s for s in network.route_stops(cfg[rid]) if not s.get("shape_point")]
        stops_xy = np.array([to_xy(s["lat"], s["lon"]) for s in stops])
        M, fit = georeference(pix, spec["markers"], stops_xy, roads)
        xy = _apply(M, pix)
        # Thin to one point per 5 m cell; enough to guide routing and much smaller.
        cells = {}
        for x, y in xy:
            cells.setdefault((int(x // 5), int(y // 5)), (round(x, 1), round(y, 1)))
        pts = sorted(cells.values())
        with open(DATA / "derived" / f"trace_{rid}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["x_svy21", "y_svy21"])
            w.writerows(pts)
        fit["n_points_thinned"] = len(pts)
        fits[rid] = fit
        print(rid, {k: round(v, 3) if isinstance(v, float) else v for k, v in fit.items()})
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "trace_fit.json").write_text(json.dumps(fits, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
