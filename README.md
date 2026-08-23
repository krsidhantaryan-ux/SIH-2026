# Cyclone-AI — SIH 2026 PS 26070 (IMD / MoES)

AI/ML system for identification, classification, and prediction of tropical
cyclone patterns from multi-source satellite data.

## Modules
1. **Detection** — find cyclonic systems in full-disk IR imagery (YOLOv8)
2. **Classification** — automated Dvorak: storm-centered IR patch → Vmax + IMD category (CNN regression)
3. **Prediction** — 6–24 h intensity change + rapid-intensification alert (ConvLSTM + environment)

## Quick start
```bash
pip install -r requirements.txt
./scripts/fetch_data.sh ibtracs                # labels (IBTrACS, NOAA)
./scripts/fetch_data.sh hursat 2013 PHAILIN    # satellite imagery (HURSAT-B1)
python src/build_dataset.py --hursat-dir data/raw/hursat_phailin
```
Raw data is never committed — everything under `data/raw/` is reproducible
via `scripts/fetch_data.sh`.
