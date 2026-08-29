# Cyclone-AI — SIH 2026 PS 26070 (IMD / MoES)

A working, human-in-the-loop MVP for historical tropical-cyclone analysis, satellite-image intensity inference, short-range baseline guidance, and rapid-intensification review over the North Indian Ocean.

> **Safety:** Cyclone-AI is a demonstration decision-support system. Its outputs are machine guidance—not official IMD forecasts, warnings, or public safety advice.

## MVP status

The repository now contains an end-to-end prototype:

- **Professional analyst console** with a responsive React/TypeScript interface.
- **Cyclone Phailin historical replay** over 55 valid times and 158 HURSAT/IBTrACS source rows.
- **Interactive track map**, source imagery, intensity timeline, 6/12/24-hour trend guidance, and RI review signal.
- **Real image inference** through a bundled, checksum-verified ONNX CNN.
- **Image upload laboratory** with validation, preprocessing, inference, category mapping, morphology context, and provenance.
- **FastAPI backend**, OpenAPI documentation, report output, alert-review workflow, health/status endpoints, and static production host.
- **Manifest-driven model loading**, allowing a new trained model to replace the legacy baseline without changing the API or UI.
- **Automated backend/domain/model tests**, frontend type checking, production build, and container deployment.

### Honest model qualification

The bundled `cyclonet-insat3d-legacy-onnx@0.1.0` model is converted from the MIT-licensed CycloNet project, whose documentation identifies the Kaggle INSAT-3D imagery dataset as its training source. The public training notebook does not publish cyclone-separated held-out evaluation or calibrated uncertainty. It is therefore labelled **legacy, independently unvalidated, demonstration-only** throughout the product.

See [`models/MODEL_CARD.md`](models/MODEL_CARD.md) for provenance and limitations.

## Run the MVP

### Prerequisites

- Python 3.11+
- Node.js 22+
- npm 10+

### One-time installation

```bash
make install
```

### Production-style local run

```bash
make run
```

Open <http://localhost:8000>. FastAPI serves the compiled frontend and API from one origin.

### Development mode

Run these in separate terminals:

```bash
make dev-api
make dev-web
```

Open <http://localhost:5173>. Vite proxies relative `/api` calls to the backend; browser code never calls localhost directly for a second service.

### Docker

```bash
docker compose up --build
```

Open <http://localhost:8000>.

## Demo walkthrough

1. Open **Storm overview**.
2. Press play or move the lifecycle slider to replay Cyclone Phailin.
3. Click track markers and compare imagery, intensity, trend guidance, archived reference, and RI signal.
4. Generate the printable historical report.
5. Open **Analysis lab** and select **Use sample**.
6. Run the real ONNX model and inspect intensity, category, morphology context, qualification, and provenance.
7. Open **Data & model** to show judges what is implemented, what remains provisional, and how a future model is promoted.

## Replace or improve the model later

Yes—the MVP is deliberately changeable. The application reads the active artefact and preprocessing contract from [`models/active-model.json`](models/active-model.json).

A replacement model should:

1. train on a better, storm-grouped dataset;
2. report held-out RMSE, MAE, bias, category F1, and relevant slices;
3. export an ONNX model returning one scalar `vmax_kt`;
4. provide a model card and immutable SHA-256;
5. update `models/active-model.json`; and
6. pass model, API, golden-image, load, and domain-review gates.

The stable boundary is:

```text
image → manifest-defined preprocessing → ONNX model → vmax_kt
      → versioned category policy → unchanged API/UI
```

The model implementation, input dimensions, colour order, normalisation, filename, and checksum can change through the manifest. The frontend does not need to know which CNN architecture produced the value.

When Kaggle access is available, the selected INSAT-3D dataset can be downloaded and validated without changing the application:

```bash
. .venv/bin/activate
python scripts/fetch_kaggle_data.py
```

Alternatively, the dataset can be committed to the repository at
[`data/kaggle_insat3d/`](data/kaggle_insat3d/README.md) (see that folder's
README for placement rules), then validated offline with no Kaggle
credentials:

```bash
python scripts/fetch_kaggle_data.py --local-root data/kaggle_insat3d
```

The importer writes raw images under ignored `data/raw/` (download mode) and
creates a checksummed label manifest. It deliberately warns that the source
CSV lacks reliable storm identity; a future evaluation must enrich/group
samples before claiming storm-disjoint accuracy.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health` | Liveness and release smoke check |
| `GET /api/v1/status` | Dataset, source, capability, and active-model status |
| `GET /api/v1/models/active` | Active model contract, digest, provenance, and qualification |
| `GET /api/v1/storms` | Historical storm summaries |
| `GET /api/v1/storms/{id}` | Track, imagery, forecasts, RI signals, and alerts |
| `GET /api/v1/storms/{id}/analysis` | Analysis nearest an RFC 3339 valid time |
| `POST /api/v1/analysis/upload` | Validate an image and run active intensity inference |
| `GET /api/v1/alerts` | Demo RI review queue |
| `POST /api/v1/alerts/{id}/transition` | Acknowledge/escalate/dismiss/resolve in demo memory |
| `GET /api/v1/reports/{storm_id}` | Printable historical analysis report |
| `GET /api/docs` | Interactive OpenAPI reference |

Alert review state is intentionally in-memory in this single-process MVP. The SRS specifies persistent append-only audit storage for a later shadow/pilot release.

## Tests and quality checks

```bash
make test
make build
```

The test suite covers:

- continuous category boundaries, including the former 27.5 kt gap;
- historical repository aggregation and past-only forecasts;
- model checksum, input signature, preprocessing, and deterministic inference;
- status, storm, upload, rejection, alert, and report APIs;
- frontend TypeScript production compilation.

## Historical data pipeline

To reproduce the original Phailin samples:

```bash
. .venv/bin/activate
./scripts/fetch_data.sh ibtracs
./scripts/fetch_data.sh hursat 2013 PHAILIN
python -m src.build_dataset --hursat-dir data/raw/hursat_phailin
```

Raw files and large per-storm tensors remain outside Git. The corrected builder handles fractional category boundaries, empty results, unmatched filenames, and stale category values more safely.

## Repository layout

```text
app/                         FastAPI, domain policy, repository, ONNX adapter
web/                         React/TypeScript analyst console
tests/                       Backend, domain, repository, and model tests
models/                      Active manifest, ONNX baseline, licence, model card
src/build_dataset.py         HURSAT–IBTrACS dataset construction
scripts/                     Source fetch and reproducible model conversion
data/processed/              Small tracked historical demonstration artefacts
docs/                        PRD, SRS, architecture, UI/UX, deployment, plan
Dockerfile / compose.yaml    Single-container MVP deployment
```

## Documentation

| Document | Purpose |
|---|---|
| [Product Requirements Document](docs/PRD.md) | Product vision, users, scope, metrics, risks, and acceptance |
| [Software Requirements Specification](docs/SRS.md) | Functional/non-functional requirements, contracts, and verification |
| [Architecture Document](docs/ARCHITECTURE.md) | Components, ML/data flow, security, reliability, and evolution |
| [UI/UX Specification](docs/UI_UX.md) | Screens, states, visualisation, content, and accessibility |
| [Deployment and Operations Guide](docs/DEPLOYMENT.md) | Environments, delivery, rollback, observability, and recovery |
| [Technical Plan](docs/PLAN.md) | Original SIH approach, data plan, evaluation, and team split |

Presence in target-state documentation does not imply operational approval. Scientific policy, model promotion, warning semantics, and pilot use still require named meteorological and programme owners.

## Third-party attribution

- CycloNet upstream code/model: MIT licence retained in `models/legacy/`.
- Kaggle INSAT-3D dataset referenced by upstream: CC0 according to its data card.
- HURSAT-B1 and IBTrACS historical sources: NOAA/NCEI.
- Web map: OpenStreetMap contributors.
