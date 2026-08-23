"""
build_dataset.py — Stage 1 of the Cyclone-AI pipeline.

Pairs HURSAT-B1 storm-centered IR satellite images with IBTrACS best-track
labels (Vmax) to produce (image, label) training samples with ZERO manual
annotation.

Output: data/processed/<SID>/  samples.npz  (images uint8 [N,301,301], labels)
        data/processed/index.csv           (one row per sample, all metadata)

Usage:
    python -m src.build_dataset --hursat-dir data/raw/hursat_phailin
    python -m src.build_dataset --hursat-dir data/raw/hursat_*  (glob ok)
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

import numpy as np
import pandas as pd
import xarray as xr

from app.domain import imd_category

IBTRACS_CSV = "data/raw/ibtracs.NI.list.v04r01.csv"
OUT_DIR = "data/processed"

FNAME_RE = re.compile(
    r"(?P<sid>[0-9A-Z]+)\.(?P<name>[A-Z_0-9-]+)\.(?P<y>\d{4})\.(?P<m>\d{2})\.(?P<d>\d{2})\.(?P<hhmm>\d{4})\.\d+\.(?P<sat>[A-Za-z0-9-]+)\."
)


def load_ibtracs(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, skiprows=[1], low_memory=False)
    df["ISO_TIME"] = pd.to_datetime(df["ISO_TIME"])
    for col in ("USA_WIND", "WMO_WIND", "LAT", "LON"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # prefer USA_WIND (1-min, most complete), fall back to WMO_WIND (IMD 3-min)
    df["VMAX"] = df["USA_WIND"].fillna(df["WMO_WIND"])
    return df[["SID", "NAME", "ISO_TIME", "LAT", "LON", "VMAX"]].dropna(subset=["VMAX"])


def label_for(track: pd.DataFrame, when: pd.Timestamp, max_gap_h: float = 3.0):
    """Nearest-in-time best-track fix; linear interp between the two nearest."""
    t = track.sort_values("ISO_TIME")
    dt = (t["ISO_TIME"] - when).dt.total_seconds().abs() / 3600.0
    i = dt.idxmin()
    if dt.loc[i] > max_gap_h:
        return None
    # simple interpolation between neighbours for smoother labels
    exact = t.set_index("ISO_TIME")[["VMAX", "LAT", "LON"]]
    exact = exact[~exact.index.duplicated()]
    union = exact.reindex(exact.index.union([when])).interpolate("time")
    row = union.loc[when]
    return float(row.VMAX), float(row.LAT), float(row.LON)


def process_file(path: str, track: pd.DataFrame):
    m = FNAME_RE.search(os.path.basename(path))
    if not m:
        return None
    when = pd.Timestamp(
        f"{m['y']}-{m['m']}-{m['d']} {m['hhmm'][:2]}:{m['hhmm'][2:]}:00"
    )
    lab = label_for(track, when)
    if lab is None:
        return None
    vmax, lat, lon = lab
    try:
        with xr.open_dataset(path) as ds:
            img = ds["IRWIN"].values[0].astype(np.float32)  # brightness temp, K
            eye_prob = float(ds["eye_prob"].values[0]) if "eye_prob" in ds else np.nan
    except (OSError, KeyError, IndexError, TypeError, ValueError) as exc:
        print(f"  ! skip {os.path.basename(path)}: {exc}", file=sys.stderr)
        return None
    if img.shape != (301, 301) or np.isnan(img).mean() > 0.3:
        return None
    # normalize: clip 180-310 K -> uint8 (inverted: cold cloud tops = bright)
    img = np.nan_to_num(img, nan=310.0)  # missing pixels -> warm/clear sky
    img = np.clip(img, 180.0, 310.0)
    img8 = (255 * (310.0 - img) / 130.0).astype(np.uint8)
    return {
        "img": img8,
        "time": when,
        "sat": m["sat"],
        "vmax": vmax,
        "lat": lat,
        "lon": lon,
        "eye_prob": eye_prob,
        "sid": m["sid"],
        "name": m["name"],
    }


INDEX_COLUMNS = [
    "sid",
    "name",
    "time",
    "sat",
    "vmax",
    "lat",
    "lon",
    "eye_prob",
    "category",
]


def process_directory(directory: str, ib: pd.DataFrame) -> list[dict]:
    files = sorted(glob.glob(os.path.join(directory, "*.nc")))
    if not files:
        print(f"! no NetCDF files in {directory}, skipping")
        return []
    first_match = next(
        (
            match
            for path in files
            if (match := FNAME_RE.search(os.path.basename(path))) is not None
        ),
        None,
    )
    if first_match is None:
        print(f"! no recognised HURSAT filenames in {directory}, skipping")
        return []

    sid = first_match["sid"]
    track = ib[ib.SID == sid]
    if track.empty:
        print(f"! no IBTrACS track for {sid}, skipping {directory}")
        return []
    samples = [
        sample for sample in (process_file(path, track) for path in files) if sample
    ]
    if not samples:
        return []

    images = np.stack([sample["img"] for sample in samples])
    vmax = np.array([sample["vmax"] for sample in samples], dtype=np.float32)
    storm_dir = os.path.join(OUT_DIR, sid)
    os.makedirs(storm_dir, exist_ok=True)
    np.savez_compressed(
        os.path.join(storm_dir, "samples.npz"), images=images, vmax=vmax
    )
    print(
        f"{sid} {samples[0]['name']}: {len(samples)} samples "
        f"(Vmax {vmax.min():.0f}-{vmax.max():.0f} kt)"
    )
    return [
        {key: sample[key] for key in INDEX_COLUMNS if key != "category"}
        | {"category": imd_category(sample["vmax"])["name"]}
        for sample in samples
    ]


def write_index(index_rows: list[dict]) -> None:
    index = pd.DataFrame(index_rows, columns=INDEX_COLUMNS)
    index_path = os.path.join(OUT_DIR, "index.csv")
    # Append-safe: merge with an existing index and recompute the category using
    # the current demo policy rather than preserving stale labels.
    if os.path.exists(index_path):
        old = pd.read_csv(index_path, parse_dates=["time"])
        index = pd.concat([old, index], ignore_index=True).drop_duplicates(
            ["sid", "time", "sat"], keep="last"
        )
    if not index.empty:
        index["category"] = index["vmax"].map(lambda value: imd_category(value)["name"])
        index = index.sort_values(["sid", "time", "sat"])
    index.to_csv(index_path, index=False)
    print(f"\nTotal samples in index: {len(index)}  ->  {index_path}")
    print(
        "No valid samples were produced."
        if index.empty
        else index["category"].value_counts().to_string()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hursat-dir", nargs="+", required=True)
    parser.add_argument("--ibtracs", default=IBTRACS_CSV)
    args = parser.parse_args()

    directories = sorted(
        {directory for pattern in args.hursat_dir for directory in glob.glob(pattern)}
    )
    if not directories:
        parser.error("no directories matched --hursat-dir")

    os.makedirs(OUT_DIR, exist_ok=True)
    ib = load_ibtracs(args.ibtracs)
    index_rows = [
        row for directory in directories for row in process_directory(directory, ib)
    ]
    write_index(index_rows)


if __name__ == "__main__":
    main()
