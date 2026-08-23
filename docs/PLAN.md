# SIH 2026 — PS 26070: AI/ML Tropical Cyclone Identification, Classification & Prediction
**Org:** Ministry of Earth Sciences · India Meteorological Department (IMD)
**Category:** Software · **Team plan & technical approach**

---

## 1. The One-Line Idea

> An end-to-end "AI Cyclone Analyst" that watches multi-source satellite imagery over the Indian Ocean and automatically: **(a) detects** cyclonic systems, **(b) classifies** their intensity (automated Dvorak), and **(c) predicts** short-term intensity change & movement — all surfaced on a live dashboard.

The core insight to pitch: IMD forecasters today apply the **Dvorak technique manually** — a human inspects cloud patterns in IR imagery and assigns a T-number (intensity). This is subjective and analyst-dependent. A CNN trained on 40+ years of labelled storm imagery does this objectively, in seconds, 24×7. Published research already shows deep models matching/beating human Dvorak estimates. We build that, for the North Indian Ocean, on Indian (INSAT) data.

---

## 2. System Architecture (3 modules + dashboard)

```
                        ┌──────────────────────────────────────────┐
  Satellite sources     │              DATA PIPELINE               │
  ─────────────────     │  download → calibrate → regrid → crop    │
  INSAT-3D/3DR (IR/VIS) │  storm-centered 301×301 px IR patches    │
  HURSAT / GridSat (IR) │  + ERA5 environment (shear, SST, RH)     │
  Microwave (SSMI/AMSR) │  + IBTrACS labels (lat, lon, Vmax)       │
  ERA5 reanalysis       └───────────────┬──────────────────────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          ▼                             ▼                             ▼
 ┌─────────────────┐          ┌──────────────────┐          ┌──────────────────┐
 │ M1: DETECTION    │          │ M2: CLASSIFICATION│          │ M3: PREDICTION    │
 │ Find cyclones in │          │ Intensity from    │          │ 6–24 h intensity  │
 │ full-disk image  │          │ storm-centred IR  │          │ trend + track     │
 │ (YOLOv8 / RetinaNet)│       │ CNN regression →  │          │ ConvLSTM / GRU on │
 │ → bbox + centre  │          │ Vmax + IMD category│         │ image sequence +  │
 └────────┬────────┘          └────────┬─────────┘          │ tabular features  │
          │                            │                    └────────┬─────────┘
          └────────────┬───────────────┴─────────────────────────────┘
                       ▼
             ┌───────────────────────────┐
             │  DASHBOARD (web app)       │
             │  Map + latest imagery      │
             │  Detected storms, category,│
             │  intensity curve, forecast │
             │  cone, alerts, PDF report  │
             └───────────────────────────┘
```

### Module 1 — Identification (detection)
- **Input:** full-disk / sector IR image (INSAT-3D TIR1 channel).
- **Model:** YOLOv8 (fast, easy) fine-tuned to detect cyclonic vortices; label boxes auto-generated from IBTrACS storm centres (no manual annotation needed — a huge time saver).
- **Output:** bounding box + centre fix (lat/lon) + confidence.
- **Bonus:** detects *cyclogenesis* — flags low-pressure systems before they are officially named.

### Module 2 — Classification (automated Dvorak / intensity estimation)
- **Input:** 301×301 px IR patch centred on the storm (≈ 8°×8°).
- **Model:** CNN (ResNet-18/EfficientNet backbone) trained as **regression on Vmax (max sustained wind)**, then mapped to IMD categories:
  Depression → Deep Depression → Cyclonic Storm → Severe CS → Very Severe CS → Extremely Severe CS → Super Cyclonic Storm.
- **Why regression not classification:** smooth output, category boundaries come free, and RMSE in knots is the metric IMD understands.
- **Target accuracy:** published CNN-Dvorak models reach ~8–12 kt RMSE; anything under ~14 kt already rivals human analysts.
- Also classify the **cloud pattern type** (curved band / shear / eye / CDO) — this is literally the Dvorak vocabulary and will impress IMD judges.

### Module 3 — Prediction
Scope it to what is winnable:
- **Primary:** 6/12/24-h **intensity change** forecast, incl. a binary **Rapid Intensification (RI) alert** (≥30 kt increase in 24 h — the single hardest and most valuable forecast problem; a hot research topic).
- **Model:** ConvLSTM over the last 4–8 IR frames + tabular branch (ERA5 shear, SST, latitude, current Vmax, 12-h Vmax trend) → fusion head.
- **Secondary (stretch):** 12–24 h track nowcast by extrapolating deep-feature motion; overlay as a cone on the map. Do NOT promise 5-day tracks — that is NWP territory.

### Dashboard
- Web app: map (Leaflet) of Bay of Bengal / Arabian Sea, latest satellite layer, detected storms with category chips, intensity time-series, RI alert banner, auto-generated bulletin (PDF).
- "Analysis mode": upload any historical cyclone image → instant detection + intensity, side-by-side with actual IBTrACS truth (great demo moment: run it on Cyclone Amphan/Biparjoy/Fani).

---

## 3. Data Plan (the make-or-break part)

| Dataset | What it gives | Access |
|---|---|---|
| **IBTrACS** (NOAA) | Ground-truth labels: every storm's position + Vmax every 3–6 h, 1840s–present. | Open CSV/NetCDF, instant download |
| **HURSAT-B1** (NOAA) | Storm-centred IR satellite patches, 1978–2015, already cropped & gridded. **Train here first.** | Open, instant |
| **GridSat-B1** (NOAA) | Global merged IR every 3 h, 1980–present → build full-disk detection training set. | Open, instant |
| **INSAT-3D/3DR** (MOSDAC/ISRO) | Indian operational imagery — the "deployment" data source; needed for authenticity with IMD. | Free but registration + approval delay → start Day 1 |
| **ERA5** (Copernicus) | Environmental predictors: wind shear, SST, mid-level humidity. | Open API |
| **Microwave (SSMIS/AMSR-2)** | Sees through cirrus → inner-core structure. Covers the "multi-source" requirement. | Open (NASA GES DISC) |

**Key trick:** IBTrACS gives timestamped storm centres → auto-crop training patches and auto-generate detection boxes. Zero manual labelling. Thousands of labelled samples for the North Indian Ocean alone; ~200k+ globally (train global, fine-tune on NIO).

**Risk hedge:** prototype entirely on HURSAT/GridSat (instant access). Treat MOSDAC/INSAT as an integration layer added once approval arrives.

---

## 4. Tech Stack

- **ML:** Python, PyTorch, torchvision, Ultralytics YOLOv8; xarray + netCDF4 for satellite files; scikit-learn for baselines.
- **Pipeline:** Python scripts + a small job scheduler (cron/Prefect); data cached as NumPy/Zarr tensors.
- **Backend:** FastAPI serving model inference (ONNX export for speed).
- **Frontend:** React + Leaflet (or plain HTML/JS + Leaflet for speed); Recharts for intensity curves.
- **Infra:** free-tier GPU (Kaggle/Colab) for training; models are small enough (ResNet-18) to train in hours.

---

## 5. How the Work Starts — Step-by-Step Kickoff

### Week 0 (now): groundwork
1. **Register on MOSDAC** immediately (approval lag). Also make Copernicus + NASA Earthdata accounts.
2. **Read 3 things** (one teammate each, 1-page summary to the group):
   - Dvorak technique basics (WMO/IMD description) — you must speak the judges' language.
   - One CNN-Dvorak paper (e.g., "Deep learning for tropical cyclone intensity estimation" — the DeepMicroNet / Pradhan et al. CNN papers).
   - IMD cyclone classification scale + how RSMC New Delhi issues bulletins.
3. **Download IBTrACS + a sample of HURSAT** for 5 known cyclones (Fani, Amphan, Tauktae, Biparjoy, Phailin). Get comfortable opening NetCDF with xarray.

### Week 1: data pipeline + baseline
4. Script: IBTrACS → for each NIO storm fix, pull the matching HURSAT IR patch → save (image, Vmax) pairs. Target: ~10–20k samples.
5. Train the **dumbest possible baseline** (small CNN regression on Vmax). Get an RMSE number on a held-out set of *storms* (split by storm, never by frame — else leakage).
6. This baseline IS your proof-of-concept for the idea-submission PPT.

### Week 2–3: the three modules
7. Upgrade M2: ResNet backbone, augmentation (rotation is valid — cyclones spin), report RMSE + category accuracy + confusion matrix.
8. Build M1: auto-generate boxes on GridSat sectors from IBTrACS, fine-tune YOLOv8.
9. Build M3: start with tabular-only RI/intensity-change model (gradient boosting on ERA5 + history — strong baseline), then add ConvLSTM if time allows.

### Week 4: integration + demo
10. FastAPI inference service + dashboard; wire the historical "analysis mode" demo.
11. INSAT-3D integration if MOSDAC access has arrived (even one live image through the pipeline = massive credibility).
12. Record fallback demo video; prepare the pitch.

---

## 6. Evaluation & Demo Metrics (what you show judges)

- **M2:** Vmax RMSE (kt), IMD-category accuracy, confusion matrix; comparison vs published human-Dvorak error (~10–15 kt).
- **M1:** detection precision/recall on held-out storms; example of early cyclogenesis detection X hours before official naming.
- **M3:** RI alert POD/FAR; 24-h intensity-change MAE vs persistence baseline (must beat persistence — say this explicitly, judges respect it).
- **Live demo:** replay Cyclone Amphan day-by-day → watch the system detect, classify (curve tracking truth), and fire the RI alert.

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| MOSDAC access delayed | Prototype on HURSAT/GridSat; INSAT is an adapter, not a dependency |
| Track prediction too hard | Scope to intensity change + RI alert; track cone is stretch-only |
| Data volume too big | NIO-only subset first (~few GB); train global later if needed |
| Overfitting / leakage | Split train/test **by storm**, report per-storm metrics |
| GPU limits | ResNet-18-class models, mixed precision, Kaggle 30 h/week free GPU |

---

## 8. Team Split (6 people)

- **2 × ML (imagery):** M1 detection + M2 intensity CNN
- **1 × ML (time series):** M3 prediction / RI
- **1 × Data engineer:** pipeline, MOSDAC/ERA5 ingestion, storage
- **1 × Full-stack:** FastAPI + dashboard
- **1 × Research/pitch:** Dvorak domain study, metrics, PPT, video (floats as tester)

---

## 9. Pitch Framing (for the SIH PPT)

- **Problem:** Manual Dvorak = subjective, slow, analyst-dependent; RI events still surprise forecasters (cite Ockhi 2017 as the classic missed-RI disaster).
- **Solution:** Objective, instant, multi-source AI analyst that augments (not replaces) IMD forecasters.
- **Novelty:** trained/fine-tuned for the North Indian Ocean on INSAT data; cyclogenesis early-warning; RI alerting; explainability via Grad-CAM overlays showing *which cloud features* drove the estimate (judges love this).
- **Impact:** faster warnings for 100M+ coastal Indians; drop-in tool for RSMC New Delhi.
