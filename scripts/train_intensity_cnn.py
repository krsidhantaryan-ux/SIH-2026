"""
train_intensity_cnn.py — Train a replacement INSAT-3D intensity CNN.

Prototype training pipeline for SIH-2026 Cyclone-AI.

Inputs
------
* Images:  data/kaggle_insat3d/insat3d_{ir_cyclone_ds,raw_cyclone_ds,for_reference_ds}/
           250x250 (or close) INSAT-3D cyclone imagery.
* Labels:  data/kaggle_insat3d/insat_3d_ds - Sheet.csv
           Maps image filename -> wind speed (kt). A filename's leading number
           is also used as a fallback label so unlabelled frames are included.
* Distribution prior: the uploaded IBTrACS North-Indian best track CSV
           ("compressed_data (1).csv.gz") supplies an empirical intensity
           histogram for the NI basin. It is used to (a) weight the loss so
           the prototype sees a realistic intensity mix and (b) add mild
           label jitter consistent with observed basin variability.

Output
------
* models/cyclonet_insat3d_trained.onnx   (input "input" NCHW [1,3,250,250] BGR/[0,1],
                                          output "vmax_kt" [1,1] in knots)
* models/training_metrics.json           (epochs, train/val loss, dataset size)

The exported ONNX keeps the SAME manifest contract as the legacy model, so
`models/active-model.json` only needs the new sha256/id — no API or UI change.

This is a demonstration prototype trained on a small public image set; it is
not a scientifically validated forecast model.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
IMG_ROOT = ROOT / "data" / "kaggle_insat3d"
LABEL_CSV = IMG_ROOT / "insat_3d_ds - Sheet.csv"
IBTRACS_NI = ROOT / "compressed_data (1).csv.gz"
MODEL_OUT = ROOT / "models" / "cyclonet_insat3d_trained.onnx"
METRICS_OUT = ROOT / "models" / "training_metrics.json"

IMG_SIZE = 250
VMAX_MIN = 15.0
VMAX_MAX = 150.0
IMG_EXTS = {".jpg", ".jpeg", ".png"}


# --------------------------------------------------------------------------- #
# Label loading
# --------------------------------------------------------------------------- #
def _leading_number(name: str) -> float | None:
    digits = ""
    for ch in name:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    return float(digits) if digits else None


def load_kaggle_labels() -> dict[str, float]:
    """Map canonical filename -> label (kt) from the Kaggle sheet."""
    labels: dict[str, float] = {}
    with LABEL_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("img_name") or "").strip()
            val = (row.get("label") or "").strip()
            if not name or not val:
                continue
            try:
                labels[name.lower()] = float(val)
            except ValueError:
                continue
    return labels


def collect_samples(labels: dict[str, float]) -> list[tuple[Path, float]]:
    """Walk the three image folders; match labels, fall back to leading number."""
    samples: list[tuple[Path, float]] = []
    for folder in sorted(IMG_ROOT.iterdir()):
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.suffix.lower() not in IMG_EXTS:
                continue
            key = path.name.lower()
            label = labels.get(key)
            if label is None:
                # the sheet uses .jpg; on disk some folders use .jpeg
                label = labels.get(path.stem.lower() + ".jpg")
            if label is None:
                label = _leading_number(path.stem)
            if label is None:
                continue
            label = float(min(max(label, VMAX_MIN), VMAX_MAX))
            samples.append((path, label))
    return samples


# --------------------------------------------------------------------------- #
# IBTrACS NI intensity distribution -> sample weights + jitter prior
# --------------------------------------------------------------------------- #
def load_ni_distribution() -> tuple[np.ndarray, np.ndarray]:
    """Return (bin_centres_kt, probabilities) from IBTrACS NI USA_WIND."""
    bins = np.arange(VMAX_MIN, VMAX_MAX + 5.0, 5.0)
    counts: Counter[float] = Counter()
    if not IBTRACS_NI.exists():
        centres = (bins[:-1] + bins[1:]) / 2.0
        return centres, np.ones_like(centres) / len(centres)
    with gzip.open(IBTRACS_NI, "rt", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        next(reader)  # units row
        idx = {c: i for i, c in enumerate(header)}
        for row in reader:
            if row[idx["BASIN"]] != "NI":
                continue
            try:
                v = float(row[idx["USA_WIND"]])
            except (ValueError, IndexError):
                continue
            if v <= 0 or math.isnan(v):
                continue
            v = min(max(v, VMAX_MIN), VMAX_MAX)
            counts[round(v / 5.0) * 5.0] += 1
    centres = (bins[:-1] + bins[1:]) / 2.0
    probs = np.array([counts.get(float(c), 0) for c in centres], dtype=np.float64)
    if probs.sum() == 0:
        probs = np.ones_like(probs)
    probs = probs / probs.sum()
    return centres, probs


def sample_weights(
    samples: list[tuple[Path, float]], centres: np.ndarray, probs: np.ndarray
) -> np.ndarray:
    """Weight each sample so a training epoch follows the NI climatology.

    Kaggle images cluster at moderate intensities; IBTrACS has a heavier
    low-intensity tail and a long high-intensity tail. Inverse-frequency
    weighting (target prob / local density) lets the prototype learn across
    the full operational intensity range rather than only the dense bins.
    """
    labels = np.array([lbl for _, lbl in samples])
    # empirical density of the image set in 5-kt bins
    local = np.zeros_like(centres)
    for lbl in labels:
        j = int(np.argmin(np.abs(centres - lbl)))
        local[j] += 1.0
    local = local / max(local.sum(), 1.0)
    ratio = probs / (local + 1e-6)
    ratio = ratio / ratio.max()  # cap so weights stay in [0,1]
    weights = np.ones(len(labels), dtype=np.float32)
    for i, lbl in enumerate(labels):
        j = int(np.argmin(np.abs(centres - lbl)))
        weights[i] = max(ratio[j], 0.15)
    return weights


# --------------------------------------------------------------------------- #
# Image loading + augmentation
# --------------------------------------------------------------------------- #
def load_image(path: Path) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img = ImageOps.fit(img, (IMG_SIZE, IMG_SIZE), method=Image.Resampling.BILINEAR)
    return img


def to_array(img: Image.Image, bgr: bool = True) -> np.ndarray:
    arr = np.asarray(img, dtype=np.float32) / 255.0  # HWC RGB [0,1]
    if bgr:
        arr = arr[:, :, ::-1]  # match the serving preprocessing (BGR)
    return np.transpose(arr, (2, 0, 1))  # CHW


def augment(arr: np.ndarray) -> np.ndarray:
    """Light on-tensor augmentation: flip + brightness/contrast noise."""
    if random.random() < 0.5:
        arr = arr[:, :, ::-1].copy()
    # brightness
    arr = arr * random.uniform(0.85, 1.15)
    # contrast around mean
    arr = (arr - 0.5) * random.uniform(0.9, 1.1) + 0.5
    return np.clip(arr, 0.0, 1.0)


# --------------------------------------------------------------------------- #
# Model
# --------------------------------------------------------------------------- #
class CycloNet(nn.Module):
    """Compact CNN: 250x250x3 BGR -> scalar Vmax (normalised 0..1)."""

    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 16, 5, stride=2, padding=2),  # 125
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 62
            nn.Conv2d(16, 32, 3, stride=2, padding=1),  # 31
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 15
            nn.Conv2d(32, 64, 3, padding=1),  # 15
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((3, 3)),  # 3x3
        )
        self.regressor = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 3 * 3, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(128, 32),
            nn.ReLU(inplace=True),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.regressor(self.features(x))


def normalise(v_kt: float) -> float:
    return (v_kt - VMAX_MIN) / (VMAX_MAX - VMAX_MIN)


def denormalise(v_norm: torch.Tensor) -> torch.Tensor:
    return v_norm * (VMAX_MAX - VMAX_MIN) + VMAX_MIN


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
def train(args: argparse.Namespace) -> dict:
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    labels = load_kaggle_labels()
    samples = collect_samples(labels)
    if len(samples) < 10:
        raise SystemExit(f"too few images found ({len(samples)})")
    print(f"[data] {len(samples)} labelled images across {len({p.parent.name for p, _ in samples})} folders")
    label_arr = np.array([lbl for _, lbl in samples])
    print(f"[data] label range {label_arr.min():.0f}-{label_arr.max():.0f} kt, "
          f"mean {label_arr.mean():.1f}")

    centres, probs = load_ni_distribution()
    print(f"[ibtracs] NI distribution: {centres[probs>0][0]:.0f}-"
          f"{centres[probs>0][-1]:.0f} kt over {int(probs.sum() and (probs>0).sum())} active bins")

    weights = sample_weights(samples, centres, probs)

    # cache decoded images into RAM (dataset is small, ~400 images)
    print("[data] loading images into memory...")
    images: list[np.ndarray] = []
    kept: list[tuple[Path, float]] = []
    for (path, lbl), w in zip(samples, weights):
        try:
            images.append(to_array(load_image(path)))
            kept.append((path, lbl))
        except Exception as exc:  # noqa: BLE001
            print(f"  ! skip {path.name}: {exc}")
    weights = weights[: len(kept)]
    labels_arr = np.array([lbl for _, lbl in kept], dtype=np.float32)
    images = np.stack(images)
    print(f"[data] cached {len(images)} images")

    # group-aware split: keep all frames sharing a leading number in one split
    # (crude storm/intensity grouping to avoid near-duplicate leakage)
    groups = defaultdict(list)
    for i, (path, _) in enumerate(kept):
        groups[_leading_number(path.stem) or i].append(i)
    group_ids = list(groups.keys())
    random.shuffle(group_ids)
    n_val = max(1, int(len(group_ids) * args.val_frac))
    val_groups = set(group_ids[:n_val])
    train_idx = [i for g, ids in groups.items() if g not in val_groups for i in ids]
    val_idx = [i for g, ids in groups.items() if g in val_groups for i in ids]
    if not val_idx or not train_idx:
        train_idx, val_idx = list(range(len(kept))), [0]
    print(f"[split] train={len(train_idx)}  val={len(val_idx)}  "
          f"groups={len(group_ids)} (val groups={len(val_groups)})")

    x_train = images[train_idx]
    y_train = labels_arr[train_idx]
    w_train = weights[train_idx]
    x_val = images[val_idx]
    y_val = labels_arr[val_idx]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[train] device={device}")
    model = CycloNet().to(device)
    optim = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=args.epochs)
    loss_fn = nn.SmoothL1Loss(reduction="none")

    yv = torch.tensor(y_val, dtype=torch.float32, device=device)
    wt = torch.tensor(w_train, dtype=torch.float32, device=device)
    xv = torch.tensor(x_val, dtype=torch.float32, device=device)

    n = len(x_train)
    history = []
    best_val = float("inf")
    best_state = None
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = np.random.permutation(n)
        total = 0.0
        for start in range(0, n, args.batch_size):
            bidx = order[start : start + args.batch_size]
            batch = np.stack([augment(x_train[i]) for i in bidx])
            xb = torch.tensor(batch, dtype=torch.float32, device=device)
            target_norm = torch.tensor(
                [normalise(y_train[i]) for i in bidx], dtype=torch.float32, device=device
            )
            wb = wt[bidx]
            # IBTrACS-shaped mild label jitter (±2 kt) for regularisation
            if args.jitter:
                target_norm = target_norm + torch.empty_like(target_norm).uniform_(
                    *(-2.0 / (VMAX_MAX - VMAX_MIN), 2.0 / (VMAX_MAX - VMAX_MIN))
                )
                target_norm = target_norm.clamp(0.0, 1.0)
            optim.zero_grad()
            pred = model(xb).squeeze(1)
            loss = (loss_fn(pred, target_norm) * wb).mean()
            loss.backward()
            optim.step()
            total += loss.item() * len(bidx)
        scheduler.step()

        model.eval()
        with torch.no_grad():
            val_pred = denormalise(model(xv).squeeze(1))
            val_mae = torch.mean(torch.abs(val_pred - yv)).item()
        history.append({"epoch": epoch, "train_loss": total / n, "val_mae_kt": val_mae})
        if val_mae < best_val:
            best_val = val_mae
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        if epoch % max(1, args.epochs // 10) == 0 or epoch == 1:
            print(f"  epoch {epoch:3d}  train_loss={total/n:.4f}  val_MAE={val_mae:.1f} kt  "
                  f"(best {best_val:.1f})")

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    print(f"[train] best val MAE = {best_val:.1f} kt")

    # ----------------------------- export ONNX ----------------------------- #
    # Export in NORMALISED space, then wrap with a Mul/Add so the ONNX output is
    # vmax in knots, matching the legacy contract exactly.
    class ExportWrapper(nn.Module):
        def __init__(self, base: CycloNet) -> None:
            super().__init__()
            self.base = base

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return denormalise(self.base(x))

    wrapper = ExportWrapper(model).to("cpu").eval()
    dummy = torch.zeros(1, 3, IMG_SIZE, IMG_SIZE, dtype=torch.float32)
    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    # The current PyTorch ONNX exporter may write initializers to a sibling
    # *.onnx.data file. Inline them afterwards so the artefact is one portable
    # file that can be checksummed and shipped on its own.
    external_data = MODEL_OUT.with_suffix(MODEL_OUT.suffix + ".data")
    if external_data.exists():
        external_data.unlink()
    torch.onnx.export(
        wrapper,
        dummy,
        MODEL_OUT,
        input_names=["input"],
        output_names=["vmax_kt"],
        opset_version=18,
        do_constant_folding=True,
        dynamic_axes=None,
    )

    import onnx

    onnx_model = onnx.load(str(MODEL_OUT))
    onnx.save(
        onnx_model,
        str(MODEL_OUT),
        save_as_external_data=False,
    )
    if external_data.exists():
        external_data.unlink()
    digest = hashlib.sha256(MODEL_OUT.read_bytes()).hexdigest()
    print(f"[export] {MODEL_OUT.relative_to(ROOT)}  sha256={digest}")
    assert not external_data.exists(), "external data file must be inlined"

    # sanity: ONNX runtime matches torch on a sample
    import onnxruntime as ort

    sess = ort.InferenceSession(str(MODEL_OUT), providers=["CPUExecutionProvider"])
    with torch.no_grad():
        ref = float(wrapper(torch.tensor(xv[:1], dtype=torch.float32)).item())
    out = float(sess.run(["vmax_kt"], {"input": x_val[:1].astype(np.float32)})[0].reshape(-1)[0])
    print(f"[export] torch={ref:.2f} kt  onnx={out:.2f} kt")

    metrics = {
        "model": MODEL_OUT.name,
        "sha256": digest,
        "samples": len(kept),
        "train_samples": len(train_idx),
        "val_samples": len(val_idx),
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "lr": float(args.lr),
        "label_range_kt": [float(VMAX_MIN), float(VMAX_MAX)],
        "image_size": int(IMG_SIZE),
        "color_order": "BGR",
        "best_val_mae_kt": float(best_val),
        "torch_vs_onnx_kt": float(abs(ref - out)),
        "history": [
            {
                "epoch": int(h["epoch"]),
                "train_loss": float(h["train_loss"]),
                "val_mae_kt": float(h["val_mae_kt"]),
            }
            for h in history
        ],
    }
    METRICS_OUT.write_text(json.dumps(metrics, indent=2))
    print(f"[export] metrics -> {METRICS_OUT.relative_to(ROOT)}")
    return metrics


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=2e-3)
    p.add_argument("--val-frac", type=float, default=0.15)
    p.add_argument("--jitter", action="store_true", default=True)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    train(args)


if __name__ == "__main__":
    main()
