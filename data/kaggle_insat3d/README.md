# INSAT-3D dataset drop point

Commit the Kaggle INSAT-3D 2013–2021 dataset here so the team can train the
replacement intensity model without re-downloading it.

**Dataset:** `sshubam/insat3d-infrared-raw-cyclone-images-20132021` (CC0 per its data card)

## How to add the dataset

1. Download the dataset from Kaggle (or `kaggle datasets download sshubam/insat3d-infrared-raw-cyclone-images-20132021`).
2. **Unzip it** — do not commit the `.zip`/`.tar.gz` itself (`.tar.gz` is
   gitignored and the importer expects unpacked files).
3. Place the unpacked contents directly in this directory
   (`data/kaggle_insat3d/`). Folder nesting is fine — the importer scans
   recursively for the label CSV and the image files.
4. Keep every individual file under 100 MB (GitHub's limit).
5. Commit and push to any branch (`main` is fine).

## After pushing

Run the validation/importer from the repo root (no Kaggle credentials needed):

```bash
python scripts/fetch_kaggle_data.py --local-root data/kaggle_insat3d
```

This verifies every labelled image, writes checksums and `vmax_kt` labels to
`data/processed/kaggle_insat3d_manifest.csv` (a derived artefact that stays
out of Git by design), and reminds you that the source CSV lacks reliable
storm identity — a future evaluation must enrich/group samples before
claiming storm-disjoint accuracy.
