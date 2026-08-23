# Cyclone-AI — SIH 2026 PS 26070 (IMD / MoES)

AI/ML decision-support system for identification, classification, and short-range prediction of tropical cyclone patterns from multi-source satellite data.

> **Project status:** data-foundation prototype. The repository currently implements HURSAT–IBTrACS dataset construction; the detection, model-serving, API, web application, and production infrastructure described in the target-state documents are not yet implemented. Cyclone-AI output is machine guidance, not an official IMD forecast or public warning.

## Product modules

1. **Detection** — find candidate cyclonic systems in broad-area IR imagery (YOLOv8-class baseline).
2. **Classification** — estimate Vmax from a storm-centred IR patch and derive an IMD-aligned category through a versioned policy.
3. **Prediction** — estimate 6–24 hour intensity change and rapid-intensification probability from image history and environmental features.
4. **Analyst workspace** — map, imagery, timeline, uncertainty, alerts, provenance, review, historical replay, and reports.

## Documentation

| Document | Purpose |
|---|---|
| [Product Requirements Document](docs/PRD.md) | Product vision, users, scope, prioritised requirements, success measures, risks, and acceptance scenarios |
| [Software Requirements Specification](docs/SRS.md) | Testable functional and non-functional requirements, canonical data model, API contracts, state models, and verification strategy |
| [Architecture Document](docs/ARCHITECTURE.md) | Current/target architecture, components, data and ML flows, storage, security, reliability, scaling, and decisions |
| [UI/UX Specification](docs/UI_UX.md) | Information architecture, screen and component specifications, states, visualisation, content, accessibility, and research plan |
| [Deployment and Operations Guide](docs/DEPLOYMENT.md) | Environments, configuration, containers, CI/CD, rollout, rollback, monitoring, backup, recovery, and runbooks |
| [Technical Plan](docs/PLAN.md) | Original SIH solution approach, data plan, delivery sequence, evaluation framing, and team split |

The five baseline product documents are versioned `1.0` and dated 23 August 2026. They deliberately distinguish current implementation from proposed target state and include pending approval records for domain, product, engineering, UX, security, and platform owners.

## Quick start — current data pipeline

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt

./scripts/fetch_data.sh ibtracs
./scripts/fetch_data.sh hursat 2013 PHAILIN
python src/build_dataset.py --hursat-dir data/raw/hursat_phailin
```

Raw data is never committed. Everything under `data/raw/` is reproducible through `scripts/fetch_data.sh`; large per-storm NumPy tensors under `data/processed/*/samples.npz` are also ignored.

## Repository layout

```text
data/processed/          small tracked demonstration metadata/visuals
scripts/fetch_data.sh    reproducible source-data download helper
src/build_dataset.py     HURSAT–IBTrACS pairing and normalisation pipeline
docs/                    product, system, architecture, UX, deployment, and plan documents
```

## Documentation governance

- `PRD.md` is the source for product scope and priority.
- `SRS.md` is the source for testable software behaviour.
- `ARCHITECTURE.md` records component boundaries and design decisions.
- `UI_UX.md` defines user-facing workflows and accessibility expectations.
- `DEPLOYMENT.md` defines release and operational controls.
- Presence of a requirement in documentation does not imply implementation or operational approval.
- Changes to P0 requirements, scientific policy, warning semantics, trust boundaries, security controls, or SLOs require a new document version and reviewer approval.
