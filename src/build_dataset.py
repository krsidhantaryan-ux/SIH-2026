"""
build_dataset.py — Stage 1 of the Cyclone-AI pipeline.

Pairs HURSAT-B1 storm-centered IR satellite images with IBTrACS best-track
labels (Vmax) to produce (image, label) training samples with ZERO manual
annotation.

Output: data/processed/<SID>/  samples.npz  (images uint8 [N,301,301], labels)
        data/processed/index.csv           (one row per sample, all metadata)

Usage:
    python src/build_dataset.py --hursat-dir data/raw/hursat_phailin
    python src/build_dataset.py --hursat-dir data/raw/hursat_*  (glob ok)
"""
from __future__ import annotations
import argparse, glob, os, re, sys
import numpy as np
import pandas as pd
import xarray as xr

IBTRACS_CSV = "data/raw/ibtracs.NI.list.v04r01.csv"
OUT_DIR = "data/processed"

# Demo IMD classification profile (knots). Lower-bound comparisons avoid gaps
# for fractional labels created by time interpolation (for example 27.5 kt).
# This profile remains subject to meteorological-owner approval.
IMD_SCALE = [
    (120.0, "Super Cyclonic Storm"),
    (90.0, "Extremely Severe Cyclonic Storm"),
    (64.0, "Very Severe Cyclonic Storm"),
    (48.0, "Severe Cyclonic Storm"),
    (34.0, "Cyclonic Storm"),
    (28.0, "Deep Depression"),
    (17.0, "Depression"),
    (0.0, "Low Pressure Area"),
]

FNAME_RE = re.compile(
    r"(?P<sid>[0-9A-Z]+)\.(?P<name>[A-Z_0-9-]+)\.(?P<y>\d{4})\.(?P<m>\d{2})\.(?P<d>\d{2})\.(?P<hhmm>\d{4})\.\d+\.(?P<sat>[A-Za-z0-9-]+)\."
)


def imd_category(vmax_kt: float) -> str:
    if not np.isfinite(vmax_kt) or vmax_kt < 0:
        return "Unknown"
    for lower_bound, name in IMD_SCALE:
        if vmax_kt >= lower_bound:
            return name
    return "Unknown"


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
    when = pd.Timestamp(f"{m['y']}-{m['m']}-{m['d']} {m['hhmm'][:2]}:{m['hhmm'][2:]}:00")
    lab = label_for(track, when)
    if lab is None:
        return None
    vmax, lat, lon = lab
    try:
        with xr.open_dataset(path) as ds:
            img = ds["IRWIN"].values[0].astype(np.float32)  # brightness temp, K
            eye_prob = float(ds["eye_prob"].values[0]) if "eye_prob" in ds else np.nan
    except Exception as e:
        print(f"  ! skip {os.path.basename(path)}: {e}", file=sys.stderr)
        return None
    if img.shape != (301, 301) or np.isnan(img).mean() > 0.3:
        return None
    # normalize: clip 180-310 K -> uint8 (inverted: cold cloud tops = bright)
    img = np.nan_to_num(img, nan=310.0)  # missing pixels -> warm/clear sky
    img = np.clip(img, 180.0, 310.0)
    img8 = (255 * (310.0 - img) / 130.0).astype(np.uint8)
    return dict(img=img8, time=when, sat=m["sat"], vmax=vmax, lat=lat, lon=lon,
                eye_prob=eye_prob, sid=m["sid"], name=m["name"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hursat-dir", nargs="+", required=True)
    ap.add_argument("--ibtracs", default=IBTRACS_CSV)
    args = ap.parse_args()

    ib = load_ibtracs(args.ibtracs)
    os.makedirs(OUT_DIR, exist_ok=True)
    index_rows = []

    dirs = sorted(set(d for pat in args.hursat_dir for d in glob.glob(pat)))
    if not dirs:
        ap.error("no directories matched --hursat-dir")

    for d in dirs:
        files = sorted(glob.glob(os.path.join(d, "*.nc")))
        if not files:
            print(f"! no NetCDF files in {d}, skipping")
            continue
        first_match = next(
            (FNAME_RE.search(os.path.basename(path)) for path in files
             if FNAME_RE.search(os.path.basename(path))),
            None,
        )
        if first_match is None:
            print(f"! no recognised HURSAT filenames in {d}, skipping")
            continue
        sid = first_match["sid"]
        track = ib[ib.SID == sid]
        if track.empty:
            print(f"! no IBTrACS track for {sid}, skipping {d}")
            continue
        samples = [s for s in (process_file(f, track) for f in files) if s]
        if not samples:
            continue
        imgs = np.stack([s["img"] for s in samples])
        vmax = np.array([s["vmax"] for s in samples], dtype=np.float32)
        storm_dir = os.path.join(OUT_DIR, sid)
        os.makedirs(storm_dir, exist_ok=True)
        np.savez_compressed(os.path.join(storm_dir, "samples.npz"), images=imgs, vmax=vmax)
        for s in samples:
            index_rows.append({k: s[k] for k in
                               ("sid", "name", "time", "sat", "vmax", "lat", "lon", "eye_prob")}
                              | {"category": imd_category(s["vmax"])})
        print(f"{sid} {samples[0]['name']}: {len(samples)} samples "
              f"(Vmax {vmax.min():.0f}-{vmax.max():.0f} kt)")

    index_columns = [
        "sid", "name", "time", "sat", "vmax", "lat", "lon", "eye_prob", "category"
    ]
    idx = pd.DataFrame(index_rows, columns=index_columns)
    idx_path = os.path.join(OUT_DIR, "index.csv")
    # Append-safe: merge with an existing index and recompute the category using
    # the current versioned demo policy rather than preserving stale labels.
    if os.path.exists(idx_path):
        old = pd.read_csv(idx_path, parse_dates=["time"])
        idx = pd.concat([old, idx], ignore_index=True).drop_duplicates(
            ["sid", "time", "sat"], keep="last"
        )
    if not idx.empty:
        idx["category"] = idx["vmax"].map(imd_category)
        idx = idx.sort_values(["sid", "time", "sat"])
    idx.to_csv(idx_path, index=False)
    print(f"\nTotal samples in index: {len(idx)}  ->  {idx_path}")
    if idx.empty:
        print("No valid samples were produced.")
    else:
        print(idx["category"].value_counts().to_string())


if __name__ == "__main__":
    main()
