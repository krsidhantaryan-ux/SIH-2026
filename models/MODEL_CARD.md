# Model Card — CycloNet INSAT-3D Legacy Baseline

| Field | Value |
|---|---|
| Model ID | `cyclonet-insat3d-legacy-onnx@0.1.0` |
| Task | Single-image tropical cyclone intensity regression in knots |
| Runtime | ONNX Runtime, CPU |
| Input | One 250 × 250, three-channel image using the legacy BGR/[0,1] pipeline |
| Output | One scalar Vmax estimate in knots |
| Status | Demonstration-only legacy baseline; independently unvalidated |
| Operational use | Prohibited |

## Origin and licence

The artefact is a format conversion of `saved_modelcyclone` from the MIT-licensed
[`cycloneintensity/CrossKnotHacks-Cyclonet`](https://github.com/cycloneintensity/CrossKnotHacks-Cyclonet)
project. The upstream project states that it trained the model on the Kaggle
[INSAT-3D Infrared & Raw Cyclone Imagery (2012–2021)](https://www.kaggle.com/datasets/sshubam/insat3d-infrared-raw-cyclone-images-20132021)
dataset. The upstream MIT notice is retained in `models/legacy/`.

The original PyTorch state dictionary was converted to ONNX without changing
weights. `scripts/convert_legacy_cyclonet.py` reconstructs the published
architecture and performs the conversion without requiring PyTorch.

## Intended use

- SIH demonstration of the upload → validate → preprocess → infer → categorise workflow.
- Integration testing for a replaceable model-serving contract.
- UI prototyping and stakeholder feedback.

## Prohibited or unsupported use

- Official IMD analysis, forecast, warning, or public communication.
- Safety-critical or operational decisions.
- Claims of validated accuracy, calibrated uncertainty, or generalisation.
- Broad-area cyclone detection, track forecasting, RI prediction, rainfall, or surge.

## Known limitations

1. The public upstream notebook appears to train on all loaded samples and does
   not publish a cyclone-separated held-out evaluation.
2. No RMSE, MAE, bias, calibration, confidence interval, or source-slice report
   accompanies the checkpoint.
3. The small source dataset and image naming may permit duplication or leakage.
4. Inputs outside the visual conventions of the training imagery may produce
   arbitrary values.
5. The output is clamped to a safe display range by the API, but that does not
   make the prediction scientifically valid.

## Integrity and interface

- ONNX SHA-256: `bc564085d0ceea1ba684839b44fc189c20a4bb0ea2057fdf81da8ff410b495ea`
- Active manifest: `models/active-model.json`
- API contract: scalar `vmax_kt`, followed by a separately versioned category policy.

## Replacement path

The application reads model artefact, checksum, dimensions, colour order,
normalisation, and output name from `models/active-model.json`. A future model
can replace this baseline without changing the frontend or API when it:

1. exports an ONNX model with one scalar wind estimate;
2. supplies a new immutable artefact and checksum;
3. supplies a manifest with its preprocessing contract;
4. includes a proper storm-separated evaluation and model card; and
5. passes API, golden-input, performance, and domain-review gates.
