"""Paths, config loading and coordinate helpers shared by every stage."""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

import yaml
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"
DOCS = ROOT / "docs"
RESULTS = ROOT / "results"

# SVY21 / Singapore TM (EPSG:3414) gives metres, which every distance test needs.
_TO_SVY21 = Transformer.from_crs("EPSG:4326", "EPSG:3414", always_xy=True)
_TO_WGS84 = Transformer.from_crs("EPSG:3414", "EPSG:4326", always_xy=True)


def load_yaml(name: str) -> dict:
    with open(CONFIG / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def routes_config() -> dict:
    return load_yaml("routes.yaml")


def scoring_config() -> dict:
    return load_yaml("scoring.yaml")


def to_xy(lat: float, lon: float) -> tuple[float, float]:
    x, y = _TO_SVY21.transform(lon, lat)
    return float(x), float(y)


def to_latlon(x: float, y: float) -> tuple[float, float]:
    lon, lat = _TO_WGS84.transform(x, y)
    return float(lat), float(lon)


def bearing_deg(x0: float, y0: float, x1: float, y1: float) -> float:
    """Compass bearing (0 = north, clockwise) of the vector (x0,y0)->(x1,y1)."""
    return math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360.0


def turn_angle(b_in: float, b_out: float) -> float:
    """Signed heading change in degrees, in (-180, 180]. Positive = clockwise = right turn."""
    d = (b_out - b_in + 180.0) % 360.0 - 180.0
    return 180.0 if d == -180.0 else d


def read_json_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def write_json_gz(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 keeps the gzip bytes identical between runs.
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        gz.write(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8"))
