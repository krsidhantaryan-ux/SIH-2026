# Model Card — CycloNet INSAT-3D Trained Prototype

| Field | Value |
|---|---|
| Model ID | `cyclonet-insat3d-trained-onnx@0.2.0` |
| Task | Single-image tropical cyclone intensity regression in knots |
| Runtime | ONNX Runtime, CPU |
| Input | One 250 × 250, three-channel image using the BGR/[0,1] pipeline |
| Output | One scalar Vmax estimate in knots |
| Status | Prototype trained in-repo; **demonstration only, not validated** |
| Operational use | Prohibited |

## Origin and training

This artefact is a fresh, compact CNN trained by
`scripts/train_intensity_cnn.py` on the INSAT-3D imagery already present in
[`data/kaggle_insat3d/`](../data/kaggle_insat3d/README.md):

- **Inputs:** 419 images across the `insat3d_ir_cyclone_ds`,
  `insat3d_raw_cyclone_ds`, and `insat3d_for_reference_ds` folders
  (250 × 250, three-channel, centre-fit, BGR / [0,1] — identical to the
  serving preprocessing).
- **Labels:** wind speeds (kt) from `insat_3d_ds - Sheet.csv`, with the
  leading number in each filename used as a fallback so unlabelled frames are
  included. Range 25–128 kt.
- **Distribution shaping:** the uploaded IBTrACS North-Indian best track
  (`compressed_data (1).csv.gz`, basin `NI`, 1842–2025) supplies an empirical
  intensity histogram (USA_WIND, ~16k fixes). The loss is reweighted so each
  training epoch follows the NI climatological intensity mix rather than the
  image set's dense moderate bins, and ±2 kt label jitter is applied for
  regularisation.

Training uses a group-aware split (frames sharing a leading number stay in
one fold), AdamW + cosine schedule, Smooth-L1 loss, and random flip /
brightness / contrast augmentation. The best checkpoint (by validation MAE)
is exported to ONNX with the final scaling folded in, so the graph output is
already in knots.

| Metric | Value (small held-out group split) |
|---|---|
| Samples | 419 (357 train / 62 val) |
| Best validation MAE | ~15 kt |
| Epochs | 80 |

These numbers come from a **tiny, non-storm-disjoint** image set and are
reported for transparency only — they are not a scientific accuracy claim.

## Intended use

- SIH demonstration of the upload → validate → preprocess → infer → categorise workflow.
- A concrete, in-repo example of replacing the legacy baseline with a newly
  trained ONNX model through `models/active-model.json`.
- UI prototyping and stakeholder feedback.

## Prohibited or unsupported use

- Official IMD analysis, forecast, warning, or public communication.
- Safety-critical or operational decisions.
- Claims of validated accuracy, calibrated uncertainty, or generalisation.
- Broad-area cyclone detection, track forecasting, RI prediction, rainfall, or surge.

## Known limitations

1. The source image set is small (~400 images), with intensity labels that
   encode category more than exact best-track fixes; duplicate/near-duplicate
   frames exist.
2. The group split reduces leakage but is not a true storm-disjoint, sensor-
   disjoint, or year-disjoint evaluation.
3. No RMSE/bias-by-category, calibration, confidence interval, or uncertainty
   estimate is produced.
4. Inputs outside the visual conventions of INSAT-3D IR cyclone imagery may
   produce arbitrary values.
5. The API clamps output to a safe display range, but that does not make the
   prediction scientifically valid.

## Integrity and interface

- ONNX SHA-256: `8b75f7dc7cbd29c7c39d9b4b2429fbabb6760eb97c074752a6dde34a16e42093`
- Active manifest: `models/active-model.json`
- API contract: scalar `vmax_kt`, followed by a separately versioned category policy.
- Training metrics: `models/training_metrics.json`

## Reproduce

```bash
python3 -m venv .venv-train
. .venv-train/bin/activate
pip install torch onnx onnxruntime onnxscript pillow numpy pandas
python scripts/train_intensity_cnn.py --epochs 80
```

The script prints the new SHA-256; update `models/active-model.json` and this
card's digest after promotion.

## Legacy baseline

The previous `cyclonet-insat3d-legacy-onnx@0.1.0` artefact (converted from the
MIT-licensed CycloNet project) remains in `models/legacy/` for reference.
