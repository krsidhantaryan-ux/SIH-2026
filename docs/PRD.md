# Product Requirements Document (PRD)

## Cyclone-AI — AI-assisted tropical cyclone identification, classification, and short-range prediction

| Document field | Value |
|---|---|
| Product | Cyclone-AI |
| Programme | SIH 2026 — Problem Statement 26070 (IMD / Ministry of Earth Sciences) |
| Document ID | CAI-PRD-001 |
| Version | 1.0 |
| Status | Baseline for review |
| Date | 23 August 2026 |
| Owners | Cyclone-AI product and engineering team |
| Primary reviewers | Meteorological domain lead, ML lead, data lead, frontend lead, platform/security lead |
| Classification | Project documentation — no operational meteorological data or secrets |

> **Important:** Cyclone-AI is a decision-support product. Its outputs are machine-generated estimates, not official IMD forecasts or public warnings. A qualified forecaster remains the final authority for any operational interpretation or dissemination.

---

## 1. Executive summary

Cyclone-AI is an end-to-end decision-support workspace for monitoring tropical cyclones over the North Indian Ocean. It combines multi-source satellite imagery, best-track records, and environmental fields to:

1. identify candidate cyclonic systems in imagery;
2. estimate present intensity and an IMD-aligned category;
3. forecast 6-, 12-, and 24-hour intensity change and rapid-intensification risk;
4. present evidence, uncertainty, provenance, alerts, and storm history in a forecaster-oriented web application; and
5. support reproducible historical analysis and evaluation.

The product is intended to reduce repetitive image inspection, improve consistency, and surface rapidly changing systems earlier. It augments rather than replaces established operational workflows such as Dvorak analysis, numerical weather prediction, and expert review.

This PRD defines the desired product. The repository now contains the initial HURSAT–IBTrACS dataset builder plus a working demonstration MVP: a React analyst console, FastAPI service, Phailin historical replay, past-only trend/RI baselines, report and alert-review flows, and a manifest-driven legacy ONNX intensity model for image uploads. The legacy model is independently unvalidated and explicitly restricted to demonstration use. Features described as shadow, pilot, future, or target state are not claims of current implementation.

---

## 2. Problem and opportunity

### 2.1 Problem statement

Tropical cyclone analysis requires forecasters to reconcile frequent satellite observations, storm-centre fixes, environmental conditions, and prior bulletins under time pressure. Manual cloud-pattern interpretation can vary between analysts, while rapid intensification is uncommon, high impact, and difficult to identify from a single signal.

A useful AI assistant must do more than return a category. It must provide:

- a fast, repeatable estimate;
- the source image and observation time;
- confidence and uncertainty;
- supporting visual evidence;
- comparison with recent estimates and official observations;
- explicit indication of stale, missing, or low-quality inputs; and
- a reviewable audit trail.

### 2.2 Opportunity

Open historical datasets make it possible to develop reproducible baselines before operational INSAT access is available. IBTrACS supplies timestamped labels and locations, while HURSAT-B1 supplies storm-centred infrared imagery. GridSat, INSAT-3D/3DR, ERA5, and optional microwave imagery can subsequently be integrated through source-specific adapters.

The initial product can therefore demonstrate value on historical storms, then progress to shadow-mode monitoring without making public-warning decisions.

---

## 3. Product vision, mission, and principles

### 3.1 Vision

> Give every cyclone analyst a trustworthy, explainable, and continuously available AI co-pilot for the North Indian Ocean.

### 3.2 Mission

Transform heterogeneous Earth-observation data into timely, traceable cyclone detections, intensity estimates, short-range predictions, and concise analytical views while preserving human control.

### 3.3 Product principles

1. **Human authority:** the system recommends; an authorised analyst interprets and decides.
2. **Evidence before assertion:** every output links to source, time, model version, quality flags, and uncertainty.
3. **Fail visibly:** stale data, missing channels, model errors, and out-of-distribution inputs must be obvious.
4. **Meteorological consistency:** units, time bases, category mappings, and terminology are centrally governed and versioned.
5. **Evaluation without leakage:** train, validation, and test partitions are separated by storm, not image frame.
6. **Progressive operationalisation:** historical replay first, then shadow mode, then a controlled pilot after domain acceptance.
7. **Accessible under pressure:** critical status and alerts cannot depend on colour alone; workflows favour clarity over decoration.
8. **Reproducibility:** data lineage, code revision, model artefact, and configuration are retained for every analysis.

---

## 4. Goals and non-goals

### 4.1 Product goals

| ID | Goal | Intended evidence |
|---|---|---|
| G-01 | Reduce the time needed to inspect a new satellite observation | Median observation-to-result latency and usability study task time |
| G-02 | Provide consistent intensity estimates across repeated analyses | Held-out-storm RMSE/MAE, category metrics, and repeatability |
| G-03 | Surface potentially rapid intensification with usable lead time | Probability quality, recall, false-alarm ratio, and lead-time distribution |
| G-04 | Make every machine output reviewable and reproducible | 100% output lineage coverage and successful replay tests |
| G-05 | Demonstrate portability from open historical data to INSAT data | Adapter conformance tests and cross-source validation |
| G-06 | Give stakeholders a coherent map, timeline, and report workflow | Scenario-based acceptance tests with target users |

### 4.2 Non-goals for the initial product

- Replacing official IMD forecasts, warnings, bulletins, or forecaster judgement.
- Issuing alerts directly to the public or disaster-management agencies.
- Producing a five-day numerical track forecast.
- Modelling storm surge, rainfall, flood, wave, or damage impacts.
- Autonomous retraining or production promotion without review.
- Claiming early cyclogenesis detection without prospective, event-based validation.
- Treating a category boundary as certainty when the estimated wind uncertainty overlaps adjacent categories.
- Guaranteeing uninterrupted operations before an operational service level is formally approved.

---

## 5. Stakeholders and users

### 5.1 Stakeholders

| Stakeholder | Interest | Decision or responsibility |
|---|---|---|
| IMD/RSMC meteorological reviewers | Scientific validity and workflow fit | Approve terminology, thresholds, evaluation, and pilot use |
| Operational forecasters/analysts | Timely, interpretable storm analysis | Review model output and record disposition |
| Research and ML team | Model development and validation | Train, evaluate, document, and version models |
| Data engineering team | Source reliability and lineage | Ingest, validate, normalise, and retain data |
| Platform/SRE team | Secure and dependable operation | Deploy, monitor, recover, and control access |
| Product/design team | Usable end-to-end experience | Prioritise requirements and validate workflows |
| SIH evaluators | Feasibility, novelty, impact, and evidence | Evaluate the prototype and documented plan |

### 5.2 Primary personas

#### P1 — Duty forecaster

- Needs a rapid summary of active systems and what changed since the previous observation.
- Wants imagery, track, intensity, uncertainty, and environmental context in one place.
- Must be able to acknowledge or dismiss an AI alert without altering source evidence.

#### P2 — Satellite analyst

- Examines cloud structure and centre fixes in detail.
- Needs channel/time/source controls, image quality flags, overlays, and explainability views.
- Compares automated output with an independent manual estimate.

#### P3 — ML scientist

- Evaluates models by storm, basin, satellite, intensity, and lifecycle phase.
- Needs immutable dataset/model versions, metrics, slices, and reproducible inference.
- Cannot promote a model solely from aggregate accuracy.

#### P4 — System administrator/SRE

- Monitors source freshness, queues, model-serving health, storage, and failed jobs.
- Needs role-based access, audit logs, runbooks, and safe rollback.

#### P5 — Demonstration/research user

- Replays a historical event or uploads a supported image.
- Needs a clearly labelled non-operational analysis with actual-versus-estimated comparison where truth exists.

---

## 6. Jobs to be done and core journeys

### 6.1 Jobs to be done

- **When a new observation arrives,** help me see which systems were detected and what materially changed so I can prioritise review.
- **When intensity may be changing quickly,** show the estimated trend, uncertainty, RI probability, and supporting inputs so I can judge urgency.
- **When I disagree with an output,** let me record a disposition and reason without overwriting the original inference.
- **When investigating a historical cyclone,** let me replay observations in order and compare machine estimates against the chosen best-track source.
- **When validating a model,** let me reproduce an inference from its data, code, model, and configuration versions.
- **When a data feed is degraded,** tell me what is stale or missing and which outputs are affected.

### 6.2 Journey A — Review a new active-storm analysis

1. User opens the operations overview.
2. The system shows the observation freshness and system health.
3. User selects an active storm from the map or queue.
4. Storm detail opens at the latest valid analysis.
5. User inspects image, centre, intensity, category, uncertainty, recent trend, RI probability, and forecast.
6. User opens provenance or evidence overlays if needed.
7. User records `reviewed`, `needs attention`, or `not accepted`, optionally with a reason.
8. The system retains both the immutable machine result and the review event.

### 6.3 Journey B — Investigate a rapid-intensification alert

1. System creates an alert only when the configured rule and data-quality gate pass.
2. Alert identifies storm, valid time, probability, threshold, lead horizon, and model version.
3. User opens the alert and sees the intensity history, predicted distribution, environmental features, and missing-data state.
4. User acknowledges, escalates for review, or dismisses with a reason.
5. Later observations allow the outcome to be evaluated without changing the original alert.

### 6.4 Journey C — Historical replay

1. User chooses a named storm, date range, source preference, and playback speed.
2. Product displays a persistent `HISTORICAL / NOT OPERATIONAL` banner.
3. Each timestamp runs through or retrieves a versioned analysis.
4. User toggles model estimate, selected truth source, and errors.
5. User exports a reproducibility manifest or report.

### 6.5 Journey D — Ad hoc image analysis

1. User uploads a supported file and confirms acquisition time/source when metadata are unavailable.
2. Product validates format, size, georeferencing, and malware policy.
3. User sees a preview and any limitations before starting analysis.
4. Product returns a non-operational result or a clear error; unsupported inputs are never silently coerced.
5. Upload retention follows the configured environment policy.

---

## 7. Product scope and prioritisation

### 7.1 Release stages

| Stage | Purpose | Included capabilities | Exit condition |
|---|---|---|---|
| R0 — Data foundation | Establish reproducible historical samples | IBTrACS/HURSAT fetch and pairing, quality checks, dataset index | Multi-storm dataset and leakage-safe split manifest |
| R1 — Demonstration MVP | Prove the end-to-end concept historically | Baseline intensity model, historical replay, storm detail, provenance, report | Acceptance scenarios pass on held-out historical storms |
| R2 — Integrated prototype | Exercise all three ML modules | Detection, classification, 6/12/24 h prediction, RI alert, source adapters, operations view | Agreed model and product quality gates pass |
| R3 — Shadow mode | Observe near-real-time data without operational authority | Automated ingest, monitoring, analyst reviews, immutable audit trail | Stable shadow operation and domain sign-off |
| R4 — Controlled pilot | Limited institutional use | Approved access controls, SLOs, runbooks, governance, support | Formal owner acceptance; outside SIH demo commitment |

### 7.2 MoSCoW scope for R2

#### Must have

- Data ingestion with timestamps, source metadata, checksums, and validation.
- Candidate storm detection with centre/location, confidence, and model metadata.
- Intensity estimate in knots with uncertainty and a versioned IMD category profile.
- 6-, 12-, and 24-hour intensity-change estimates with uncertainty.
- Configurable 24-hour rapid-intensification probability and alert rule.
- Active-storm overview, storm detail, timeline, imagery, alerts, and data-health state.
- Historical replay for at least one complete event.
- User review/disposition and immutable audit history.
- Report/export that is clearly marked machine-generated and non-official.
- Storm-level evaluation against documented baselines.

#### Should have

- ERA5 environmental feature branch and feature-availability display.
- Grad-CAM or approved evidence overlay, explicitly labelled as explanatory rather than causal.
- Cloud-pattern label such as eye, curved band, shear, or central dense overcast, subject to labelled data.
- Optional short-range track extrapolation with a separate uncertainty envelope.
- Model/data quality dashboard and slice-based evaluation.
- INSAT-3D/3DR source adapter after data-access approval.

#### Could have

- Microwave imagery adapter.
- Side-by-side multi-model comparison.
- Analyst annotation workspace.
- Offline/PWA read-only last-known view.
- Automated draft bulletin text using deterministic templates.

#### Will not have in R2

- Autonomous official bulletin publication.
- Public push notifications.
- Long-range deterministic track guidance.
- Fully automated model promotion.

---

## 8. Product requirements

Priority uses `P0` (release blocking), `P1` (important), and `P2` (desirable).

### 8.1 Observation and data management

| ID | Requirement | Priority | Acceptance summary |
|---|---|---:|---|
| PRD-DATA-01 | Ingest supported satellite and track sources through independently versioned adapters. | P0 | A source can be replaced without changing the canonical observation contract. |
| PRD-DATA-02 | Preserve source URI/identifier, acquisition time, ingest time, checksum, licence, spatial metadata, and quality flags. | P0 | Every derived result resolves to a provenance record. |
| PRD-DATA-03 | Normalise times to UTC internally and display `UTC` explicitly. | P0 | No unlabelled or local-time timestamp appears in an analytical view. |
| PRD-DATA-04 | Detect duplicate, corrupt, stale, incomplete, or spatially invalid input. | P0 | Invalid data are quarantined and do not silently trigger inference. |
| PRD-DATA-05 | Retain immutable raw objects and versioned derived products according to policy. | P1 | Reprocessing does not overwrite prior evidence. |
| PRD-DATA-06 | Build train/validation/test manifests split by storm identity. | P0 | Automated validation rejects cross-split storm leakage. |

### 8.2 Detection

| ID | Requirement | Priority | Acceptance summary |
|---|---|---:|---|
| PRD-DET-01 | Detect zero or more candidate cyclonic systems in a supported georeferenced scene. | P0 | Result contains geospatial centre, optional bounding geometry, score, valid time, and version IDs. |
| PRD-DET-02 | Permit thresholding and non-maximum-suppression policy to be configured per approved model. | P1 | Threshold changes are versioned and audited. |
| PRD-DET-03 | Show low-confidence detections as candidates, not confirmed storms. | P0 | UI and export use non-authoritative language. |
| PRD-DET-04 | Associate detections with known storm tracks using a documented spatiotemporal rule while retaining unmatched candidates. | P1 | Match method and distance/time are visible in provenance. |

### 8.3 Intensity and classification

| ID | Requirement | Priority | Acceptance summary |
|---|---|---:|---|
| PRD-INT-01 | Estimate maximum sustained wind in knots from supported storm-centred imagery. | P0 | Value is accompanied by interval/uncertainty, model, valid time, and quality status. |
| PRD-INT-02 | Derive a category from a centrally configured, versioned classification profile. | P0 | A mapping change never rewrites prior outputs. |
| PRD-INT-03 | Display adjacent-category ambiguity when uncertainty crosses a category boundary. | P1 | UI does not imply false categorical precision. |
| PRD-INT-04 | Provide approved explanatory evidence, such as an image saliency overlay, with limitations. | P1 | Overlay can be toggled and cannot obscure the original image. |
| PRD-INT-05 | Optionally estimate a Dvorak cloud-pattern class where labelled evaluation supports it. | P2 | Unsupported output is absent, not guessed. |

### 8.4 Prediction and rapid intensification

| ID | Requirement | Priority | Acceptance summary |
|---|---|---:|---|
| PRD-PRED-01 | Predict intensity change and/or resulting intensity at 6, 12, and 24 hours. | P0 | Each horizon has central estimate, uncertainty, valid time, and input window. |
| PRD-PRED-02 | Compare prediction against a persistence baseline in evaluation views. | P0 | A model is not promoted if it fails the approved baseline gate. |
| PRD-PRED-03 | Produce a calibrated RI probability for the configured event definition. | P0 | Event threshold and horizon are shown with the probability. |
| PRD-PRED-04 | Gate predictions when history or mandatory quality criteria are insufficient. | P0 | Product reports `insufficient data`; it does not fabricate a forecast. |
| PRD-PRED-05 | Keep experimental track guidance visually and semantically distinct from intensity guidance. | P2 | Track output carries its own uncertainty and experimental label. |

### 8.5 Workspace, alerting, and reporting

| ID | Requirement | Priority | Acceptance summary |
|---|---|---:|---|
| PRD-UX-01 | Provide an overview of active storms, latest status, alerts, and source freshness. | P0 | Critical state is understandable without relying only on colour. |
| PRD-UX-02 | Provide a storm detail view with map, imagery, intensity history, forecast, evidence, and provenance. | P0 | User can reach source and model metadata within two interactions. |
| PRD-UX-03 | Support historical event search and chronological replay. | P0 | Historical mode is persistently and clearly labelled. |
| PRD-UX-04 | Support alert acknowledge, escalate, and dismiss actions with actor, time, and reason. | P0 | Review events append to an immutable history. |
| PRD-UX-05 | Generate a machine-analysis report and reproducibility manifest. | P1 | Report includes disclaimer, valid time, sources, versions, uncertainty, and quality flags. |
| PRD-UX-06 | Provide empty, loading, stale, partial, denied, and error states. | P0 | No blank panel can be mistaken for a zero-risk state. |
| PRD-UX-07 | Support keyboard operation, screen-reader semantics, and 200% zoom for critical tasks. | P0 | Agreed WCAG 2.2 AA checks pass. |

### 8.6 Administration and governance

| ID | Requirement | Priority | Acceptance summary |
|---|---|---:|---|
| PRD-GOV-01 | Enforce role-based permissions for viewers, analysts, researchers, and administrators. | P0 for pilot | Unauthorised actions return a denial and are logged. |
| PRD-GOV-02 | Record immutable audit events for inference, review, export, configuration, and model promotion. | P0 for pilot | Audit queries identify who/what/when and correlation ID. |
| PRD-GOV-03 | Show the currently deployed model, data-adapter, and category-profile versions. | P1 | Versions are visible in system status and output provenance. |
| PRD-GOV-04 | Require documented approval before a model becomes the default for shadow or pilot use. | P0 | Registry stage transition includes approver and evaluation report. |

---

## 9. Data sources and policy

| Source | Product use | Initial status | Product constraint |
|---|---|---|---|
| IBTrACS | Historical position/intensity labels and evaluation reference | Dataset script supported | Preserve agency-specific wind fields and averaging-period metadata; do not present as live truth |
| HURSAT-B1 | Historical storm-centred infrared imagery | Dataset script supported | Respect source coverage and quality limitations |
| GridSat-B1 | Broad-area historical IR scenes for detection | Planned | Adapter must preserve georeferencing and source metadata |
| INSAT-3D/3DR via MOSDAC | Operationally relevant Indian satellite imagery | Planned; access dependent | Licence/access approval and calibration validation required |
| ERA5 | Environmental predictors such as shear, SST, and humidity | Planned | Reanalysis latency means it may not represent a real-time operational feed |
| Microwave sensors | Inner-core structural evidence | Optional | Irregular overpasses and licensing/access must be visible |

### 9.1 Meteorological policy controls

The following are configuration governed, not scattered constants:

- wind averaging period and source preference;
- IMD category boundaries and labels;
- rapid-intensification event definition (prototype default: at least 30 kt increase in 24 hours);
- acceptable observation age and temporal matching window;
- longitude convention, coordinate reference system, and basin geometry;
- unit conversion and rounding rules; and
- minimum quality requirements for each model.

The current `src/build_dataset.py` mapping is a prototype convenience and requires meteorological review before any operational interpretation.

---

## 10. Success measures and quality gates

Targets below are proposed product gates for review; they are not current measured performance.

### 10.1 Scientific/model metrics

| Capability | Metric | Proposed R2 target/gate | Evaluation rule |
|---|---|---|---|
| Detection | Precision and recall | Each ≥ 0.85 at the approved operating point | Held-out storms/scenes; report by basin/source/intensity |
| Centre fix | Median geodesic error | ≤ 50 km for matched detections | Event-level matching policy fixed before evaluation |
| Intensity | RMSE | ≤ 14 kt; aspiration ≤ 12 kt | Held-out storms; confidence interval via storm bootstrap |
| Intensity | MAE and bias | Report overall and by category/source | No aggregate-only approval |
| Category | Macro F1 | ≥ 0.75 proposed | Versioned category profile; include confusion matrix |
| 24 h change | MAE skill vs persistence | ≥ 10% relative improvement proposed | Same samples and missing-data policy |
| RI | Recall, precision/FAR, PR-AUC, Brier score | Threshold selected with forecaster input; no single accuracy gate | Event-based, class-imbalance-aware evaluation |
| Probability | Calibration | Reliability curve and calibration error within approved tolerance | Tested on untouched storms |

### 10.2 Product and operational measures

| Measure | Proposed target |
|---|---|
| Observation-to-visible-result latency | p95 ≤ 5 minutes in shadow mode, excluding upstream source delay |
| Interactive API latency | p95 ≤ 500 ms for metadata/history requests; image tiles excluded |
| Single supported image inference | p95 ≤ 60 seconds under declared reference hardware |
| Provenance completeness | 100% of published machine outputs |
| Critical accessibility task completion | 100% of agreed keyboard/screen-reader scenarios |
| Historical replay reproducibility | Same model/config/input yields result within declared numeric tolerance |
| Review workflow | ≥ 90% scenario completion without facilitator in formative usability test |
| Service availability | Proposed 99.5% monthly for shadow mode after service implementation |

### 10.3 Guardrails

- Never optimise alert recall without reporting false alarms and workload.
- Never approve based on random frame splits.
- Never silently mix 1-minute and 3-minute wind labels.
- Never show a prediction without its valid time and uncertainty/quality state.
- Never interpret an unavailable feed or empty result as “no cyclone.”

---

## 11. Release acceptance scenarios

An R2 candidate is product-acceptable only when all P0 scenarios pass:

1. **Multi-candidate scene:** a scene with zero, one, and multiple candidates returns correctly structured, traceable results.
2. **Historical event:** an authorised user replays an entire held-out cyclone, pauses at any timestamp, and compares estimate with the selected reference.
3. **Insufficient history:** prediction is withheld with an actionable explanation.
4. **Stale source:** overview and storm detail show staleness and suppress affected alerts as configured.
5. **Boundary uncertainty:** an intensity interval crossing category boundaries shows ambiguity rather than one unqualified label.
6. **RI review:** user opens an alert, sees threshold/horizon/evidence, acknowledges it, and later retrieves the audit event.
7. **Reproducibility:** a scientist resolves result → source checksum → preprocessing version → model artefact → configuration and reruns it.
8. **Accessibility:** a keyboard-only user identifies the highest-priority alert and reaches storm evidence without a trap.
9. **Authorisation:** a viewer cannot change alert disposition, configuration, or model stage.
10. **Failure recovery:** a failed inference is retried safely without duplicate alerts or overwritten evidence.
11. **Report safety:** exported report contains non-official disclaimer, timestamp, units, sources, versions, quality flags, and uncertainty.
12. **Leakage check:** CI rejects a dataset split containing the same storm in more than one partition.

---

## 12. Dependencies, assumptions, and constraints

### 12.1 Dependencies

- Approval and reliable access for MOSDAC/INSAT data.
- Licence-compatible access to each external dataset.
- Domain review of category, wind, RI, matching, and evaluation policies.
- Sufficient representative storms across intensity classes and satellite eras.
- Compute suitable for model training and production inference.
- A map/tile strategy permitted in the target network environment.

### 12.2 Assumptions

- The initial deployment is an institutional or demonstration environment, not a public warning system.
- UTC is the canonical internal and display time unless a future user preference explicitly adds local time.
- North Indian Ocean coverage is prioritised; global data may support pretraining.
- Raw scientific data remain in object/file storage, not Git.
- The model may be unavailable or abstain; the UI treats abstention as a valid state.

### 12.3 Constraints

- Raw satellite datasets are large and must remain outside the repository.
- Historical labels can be revised and differ by agency; label provenance is mandatory.
- Source cadence and availability differ, so the system must tolerate partial inputs.
- Class imbalance is severe for RI and extreme categories.
- The repository has a container-ready single-process demonstration API/frontend and a legacy model artefact, but no approved live-source deployment, trained detection/prediction models, persistent operational data services, institutional identity, or production infrastructure.

---

## 13. Risks and mitigations

| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| Source access or latency prevents live integration | Demo/operations blocked | Keep open-data historical path; isolate adapters; cache only where allowed | Data lead |
| Temporal/spatial leakage inflates metrics | Unsafe model selection | Split by storm; deduplicate near-identical multi-satellite samples; automated leakage checks | ML lead |
| Wind averaging periods are mixed | Biased labels and category errors | Preserve source fields; define conversion/source policy; domain review | Domain + data leads |
| Distribution shift across sensors/eras | Degraded inference | Source-specific validation, drift monitoring, fine-tuning, abstention | ML lead |
| RI alert creates excess workload | Users ignore alerts | Calibrate probabilities; tune operating point with users; show evidence; track FAR | Product + domain leads |
| Explainability overlay is misread as causality | False confidence | Plain-language limitation, original-image toggle, user training | UX + ML leads |
| Map or feed outage looks like “all clear” | Dangerous misinterpretation | Explicit degraded state, last-updated time, no-data messaging | Frontend + SRE |
| Unauthorised model/config change | Integrity loss | RBAC, signed artefacts, approval workflow, audit log | Security + ML platform |
| Prototype category mapping is treated as authoritative | Incorrect interpretation | Central versioned profile and domain sign-off gate | Domain lead |
| Demo scope expands into impact forecasting | Delivery risk | Enforce non-goals and staged roadmap | Product owner |

---

## 14. Roadmap and indicative milestones

Dates are set during sprint planning; sequence is authoritative, not duration.

1. **Foundation:** harden data fetch, add checksums/licence metadata, build multiple-storm manifests, and validate storm-level splits.
2. **Baseline science:** intensity baseline, persistence prediction baseline, documented evaluation report.
3. **Service contracts:** canonical schemas, inference API, job state, provenance, and audit events.
4. **Historical UX:** overview, replay, storm detail, report, and all degraded states.
5. **Module integration:** broad-area detection, temporal prediction, RI probability, and explainability.
6. **Source integration:** GridSat, ERA5, then INSAT subject to approval.
7. **Shadow readiness:** identity, RBAC, monitoring, SLOs, backups, runbooks, security review.
8. **Pilot review:** scientific validation, user acceptance, governance approval, and controlled rollout.

---

## 15. Decisions required before operational pilot

| Decision | Options/considerations | Decision owner |
|---|---|---|
| Authoritative category profile | Current IMD profile and treatment of depressions/low-pressure systems | Meteorological owner |
| Wind target | WMO/IMD field, USA_WIND, conversion policy, averaging period | Meteorological + ML owners |
| RI event definition | Wind increase, horizon, eligible lifecycle phases | Meteorological owner |
| Alert operating point | Balance recall, false alarms, and analyst workload | Product + forecaster group |
| Raw/derived retention | Scientific replay, licence, storage cost, institutional policy | Data governance |
| Deployment boundary | Demonstration, internet-connected institutional, or restricted network | Security + platform |
| Mapping provider | Offline tiles, institutional GIS, or approved public provider | Platform + legal |
| Model approval authority | Required evidence and named approver(s) | Programme owner |

---

## 16. Traceability and related documents

- [Software Requirements Specification](SRS.md) — testable system requirements derived from this PRD.
- [Architecture Document](ARCHITECTURE.md) — target components, data flows, trust boundaries, and design decisions.
- [UI/UX Specification](UI_UX.md) — information architecture, screens, states, accessibility, and interaction rules.
- [Deployment and Operations Guide](DEPLOYMENT.md) — environments, delivery, observability, rollback, and recovery.
- [Technical Plan](PLAN.md) — original project approach and SIH execution plan.

Requirement implementation status must be tracked separately (for example, in issues or a requirements matrix). Presence in this document does not imply completion.

---

## 17. Approval record

| Role | Name | Decision | Date | Notes |
|---|---|---|---|---|
| Product owner | TBD | Pending | — | — |
| Meteorological reviewer | TBD | Pending | — | — |
| ML lead | TBD | Pending | — | — |
| Engineering lead | TBD | Pending | — | — |
| Security/platform reviewer | TBD | Pending | — | — |

A change to a P0 requirement, scientific quality gate, safety disclaimer, or operational scope requires a new document version and reviewer approval.
