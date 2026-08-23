# Deployment and Operations Guide

## Cyclone-AI

| Document field | Value |
|---|---|
| Document ID | CAI-OPS-001 |
| Version | 1.0 |
| Status | Target deployment design and runbook baseline |
| Date | 23 August 2026 |
| Related documents | [Architecture](ARCHITECTURE.md), [SRS](SRS.md), [PRD](PRD.md), [UI/UX](UI_UX.md) |
| Audience | Developers, release engineers, SRE/platform, security, ML operations, and technical reviewers |

> **Readiness notice:** the repository currently contains a Python dataset builder, not a deployable API/web/ML platform. There are no Dockerfiles, Compose manifests, Kubernetes charts, Terraform modules, database migrations, trained model packages, CI workflows, or production runbooks yet. Commands marked **current** apply now; sections marked **target** define the deployment contract to implement.

---

## 1. Purpose

This guide defines how Cyclone-AI should be built, configured, deployed, verified, monitored, backed up, recovered, rolled back, and retired across local, demonstration, shadow, and controlled-pilot environments.

It is intentionally provider-neutral. Concrete infrastructure may use managed services or self-hosted equivalents if it satisfies the interfaces and controls in the architecture and SRS.

This guide does not authorise operational meteorological use. Deployment readiness and scientific/operational approval are separate gates.

---

## 2. Deployment profiles

| Profile | Purpose | Data | Identity | Availability expectation |
|---|---|---|---|---|
| Local batch (**current**) | Build historical dataset samples | Downloaded open historical data | Developer account on workstation | None |
| Local application (**target**) | Develop/test full vertical slice | Fixtures or approved local historical data | Dev identity or disabled only on loopback/restricted preview | Best effort |
| CI (**target**) | Build, test, scan, validate contracts | Synthetic/small licensed fixtures | Workload identity; no personal credentials | Ephemeral |
| Demo (**target**) | SIH demonstration and stakeholder review | Historical and explicitly approved sample data | Restricted demo access | Best effort with rehearsal |
| Staging/shadow (**target**) | Near-real-time validation without authority | Approved feeds and isolated metadata | Institutional OIDC + RBAC | Proposed 99.5% after readiness |
| Controlled pilot (**target**) | Limited decision support under approved procedure | Approved institutional data | Institutional OIDC + least privilege | Formally agreed SLO/RTO/RPO |

### 2.1 Environment isolation

Each non-local environment SHALL use separate:

- cloud account/project/subscription or equivalent strong boundary where feasible;
- Kubernetes namespace/cluster policy or container-host boundary;
- database and credentials;
- object buckets/prefixes and encryption keys according to policy;
- queue/broker virtual host or equivalent;
- OIDC client and redirect URIs;
- secret scope;
- observability labels/dashboards/alert routes;
- model deployment stage and policy configuration; and
- DNS name and TLS certificate.

Production/pilot data SHALL NOT be copied to demo or local environments without explicit approval and sanitisation/licence review.

---

## 3. Current local batch setup

This is the only implemented execution path at this document revision.

### 3.1 Prerequisites

- Git.
- Bash, `curl`, `tar`.
- Python 3.10+ recommended (the repository does not yet declare an exact supported version).
- Enough disk for downloaded NetCDF files and generated NumPy archives.
- Network access to the NOAA endpoints used by `scripts/fetch_data.sh`.

### 3.2 Installation

```bash
git clone https://github.com/krsidhantaryan-ux/SIH-2026.git
cd SIH-2026
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` is currently unpinned. For reproducible releases, pin direct/transitive dependencies with hashes or use a lockfile before relying on this setup in CI.

### 3.3 Fetch and build data

```bash
./scripts/fetch_data.sh ibtracs
./scripts/fetch_data.sh hursat 2013 PHAILIN
python src/build_dataset.py --hursat-dir data/raw/hursat_phailin
```

Expected tracked/small output:

```text
data/processed/index.csv
```

Expected untracked/ignored large output:

```text
data/raw/**
data/processed/<SID>/samples.npz
```

### 3.4 Current validation

```bash
python - <<'PY'
import pandas as pd
p = "data/processed/index.csv"
df = pd.read_csv(p)
required = {"sid", "name", "time", "sat", "vmax", "lat", "lon", "category"}
missing = required - set(df.columns)
assert not missing, f"missing columns: {sorted(missing)}"
assert len(df) > 0, "dataset index is empty"
print(f"OK: {len(df)} rows, {df['sid'].nunique()} storm(s)")
PY
```

This is a smoke check only. It does not satisfy the SRS requirements for checksums, licence metadata, storm-disjoint splits, scientific validation, or test coverage.

### 3.5 Local data safety

- Do not commit `data/raw`, per-storm `samples.npz`, credentials, provider cookies, or access tokens.
- Review `git status` before every commit.
- Do not put provider credentials directly in shell history or scripts.
- Verify source licence and redistribution terms before sharing derived samples.
- Remove temporary downloaded archives if a script fails before cleanup.

---

## 4. Target deployable units

The target architecture builds the following OCI images (names are illustrative):

| Image | Contents | Runtime profile |
|---|---|---|
| `cyclone-ai-web` | Compiled React/TypeScript assets and minimal static server, or assets served at edge | CPU, stateless |
| `cyclone-ai-api` | FastAPI application/BFF, domain modules, migrations client | CPU, stateless except connections |
| `cyclone-ai-ingest` | Scheduler and approved source adapters | CPU/network, persistent cursor in DB |
| `cyclone-ai-worker` | Workflow, preprocessing, report tasks | CPU/memory; no public ingress |
| `cyclone-ai-detection` | Detection runtime and one pinned model | CPU/GPU profile |
| `cyclone-ai-intensity` | Intensity runtime and one pinned model | CPU/GPU profile |
| `cyclone-ai-prediction` | Temporal model runtime and one pinned model | CPU/GPU profile |
| `cyclone-ai-migrate` | Exact application migration bundle | One-shot job |

A smaller demonstration may combine ingest and worker or serve static assets from the API, but model packages, privileges, queues, and contracts remain separable.

### 4.1 Image requirements

Every release image SHALL:

- use a pinned base image by digest;
- include OCI labels for source repository, revision, version, build time, and licence;
- install locked dependencies without runtime package downloads;
- run as a non-root numeric UID/GID;
- define a read-only root filesystem where practical and writable ephemeral mounts explicitly;
- drop unnecessary Linux capabilities and avoid privileged mode;
- include a minimal init only if needed for signal handling;
- expose no embedded credentials, `.env`, raw data, test secrets, or SSH tools;
- include or link an SBOM and provenance/attestation;
- pass critical vulnerability policy or carry a time-bounded documented exception;
- support graceful SIGTERM and stop accepting work before termination; and
- be addressed by immutable digest in staging/pilot manifests.

Separate builder/runtime stages should keep compilers and package managers out of runtime images where practical.

### 4.2 Release versioning

Use a coherent release version plus immutable component details:

```text
Application release: 0.4.0
OCI tag for convenience: 0.4.0
OCI deployment reference: registry.example/cyclone-ai-api@sha256:<digest>
Git revision: <full SHA>
Model version: intensity-resnet18@1.2.0
Model artefact: sha256:<digest>
Policy version: ri-alert@1.3.0
Dataset manifest: dataset-nio-hursat@2026.08.1
```

Do not deploy `latest` or a mutable model path in staging/pilot. Rollback targets are exact digests.

---

## 5. Target runtime dependencies

| Dependency | Minimum capability | Pilot preference |
|---|---|---|
| PostgreSQL + PostGIS | Transactions, geospatial types/indexes, backups/PITR | Managed HA where available |
| S3-compatible object store | Versioning, encryption, lifecycle, checksums, scoped IAM | Multi-zone/replicated according to RPO |
| Queue/broker | Durable messages, leases/visibility timeout, retry/dead-letter, priorities | Managed or HA deployment |
| Model/artefact registry | Immutable digest, metadata, stage/approval, object integration | MLflow-compatible or approved equivalent |
| OIDC identity provider | Standard discovery/JWKS, groups/claims, MFA policy externally governed | Institutional IdP |
| Secret manager | Workload identity, rotation, audit, no plaintext Git state | Institutional/cloud secret store |
| Telemetry backend | Metrics, logs, traces, alert routing, retention | Existing institutional stack |
| Map/tile service | Licensed, attributed, works in network boundary | Approved internal/offline tiles for restricted network |

The application must not require a public SaaS at runtime unless that dependency is explicitly approved and included in availability/privacy analysis.

---

## 6. Configuration contract

Configuration is loaded from environment variables and/or mounted non-secret files. Secrets come from a secret manager or local untracked environment. Exact names become stable once implementation starts; the proposed contract below prevents hidden defaults.

### 6.1 Core application

| Variable | Secret | Example shape | Rule |
|---|:---:|---|---|
| `APP_ENV` | No | `local`, `ci`, `demo`, `shadow`, `pilot` | Required; controls labels, never security by itself |
| `APP_RELEASE` | No | `0.4.0` | Injected at build/deploy |
| `APP_GIT_SHA` | No | Full commit SHA | Required outside local |
| `PUBLIC_BASE_URL` | No | `https://cyclone.example.gov` | Absolute external origin; no path ambiguity |
| `API_PREFIX` | No | `/api/v1` | Browser uses relative URL |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` prohibited by default in pilot |
| `LOG_FORMAT` | No | `json` | Structured JSON outside local |
| `DEFAULT_MODE` | No | `historical` or `shadow` | Must match approved environment |
| `DISCLAIMER_PROFILE` | No | `shadow-en@1.0` | Required and versioned |
| `TIME_ZONE` | No | `UTC` | Must be UTC for services |

### 6.2 Database and queue

| Variable | Secret | Rule |
|---|:---:|---|
| `DATABASE_URL` | Yes | TLS and least-privilege application account |
| `DATABASE_POOL_MIN` / `DATABASE_POOL_MAX` | No | Sized against DB connection budget |
| `DATABASE_STATEMENT_TIMEOUT_MS` | No | Bounded interactive timeout |
| `QUEUE_URL` | Yes | Scoped virtual host/account |
| `QUEUE_INTERACTIVE_NAME` | No | Separate from replay/batch |
| `QUEUE_BATCH_NAME` | No | Lower priority/quota |
| `QUEUE_DEAD_LETTER_NAME` | No | Monitored and access-controlled |
| `JOB_VISIBILITY_TIMEOUT_SECONDS` | No | Greater than expected stage duration with heartbeat |
| `JOB_MAX_ATTEMPTS` | No | Bounded and error-class aware |

### 6.3 Object storage

| Variable | Secret | Rule |
|---|:---:|---|
| `OBJECT_STORE_ENDPOINT` | No | Internal HTTPS endpoint where applicable |
| `OBJECT_STORE_REGION` | No | Explicit for signing/client behaviour |
| `OBJECT_STORE_RAW_BUCKET` | No | Separate policy from derived/reports |
| `OBJECT_STORE_DERIVED_BUCKET` | No | Versioning/lifecycle configured |
| `OBJECT_STORE_MODEL_BUCKET` | No | Read-only to model runtime |
| `OBJECT_STORE_REPORT_BUCKET` | No | Signed-download policy |
| `OBJECT_STORE_ACCESS_KEY` | Yes | Avoid static keys when workload identity exists |
| `OBJECT_STORE_SECRET_KEY` | Yes | Secret manager only |
| `SIGNED_URL_TTL_SECONDS` | No | Short, policy-approved duration |

### 6.4 Identity and web security

| Variable | Secret | Rule |
|---|:---:|---|
| `OIDC_ISSUER_URL` | No | Exact approved issuer |
| `OIDC_CLIENT_ID` | No | Environment-specific |
| `OIDC_CLIENT_SECRET` | Yes | Required for confidential client pattern only |
| `OIDC_AUDIENCE` | No | Strictly validated |
| `OIDC_GROUP_ROLE_MAP_FILE` | No | Mounted, code-reviewed mapping; no broad wildcard |
| `SESSION_SECRET` | Yes | High entropy and rotated with session plan |
| `ALLOWED_ORIGINS` | No | Exact allowlist; `*` prohibited with credentials |
| `TRUSTED_HOSTS` | No | Include public proxy hostname(s) |
| `FORWARDED_PROXY_CIDRS` | No | Trust only known ingress proxies |
| `COOKIE_SECURE` | No | `true` outside local HTTP |
| `COOKIE_SAMESITE` | No | Chosen for OIDC flow and CSRF design |
| `CSRF_SECRET` | Yes | If cookie/session state-changing design requires it |
| `MAX_REQUEST_BYTES` | No | Edge and API consistent |

### 6.5 Scientific and model configuration

| Variable | Secret | Rule |
|---|:---:|---|
| `CATEGORY_PROFILE_ID` | No | Immutable approved version |
| `WIND_POLICY_ID` | No | Immutable approved version |
| `RI_DEFINITION_ID` | No | Immutable event definition |
| `RI_ALERT_RULE_ID` | No | Immutable operating threshold/rule |
| `SOURCE_FRESHNESS_PROFILE_ID` | No | Per-source thresholds |
| `DETECTION_MODEL_ID` | No | Exact registry version/digest via deployment manifest |
| `INTENSITY_MODEL_ID` | No | Exact registry version/digest |
| `PREDICTION_MODEL_ID` | No | Exact registry version/digest |
| `MODEL_REGISTRY_URI` | May be | Private endpoint; credentials separate |
| `MODEL_CACHE_DIR` | No | Ephemeral/read-only mounted location as designed |
| `ENABLE_EXPERIMENTAL_TRACK` | No | `false` unless explicitly approved |
| `ENABLE_EXTERNAL_NOTIFICATIONS` | No | Default `false` |

Scientific policy variables must resolve to database/packaged versioned objects. Raw numeric thresholds should not be editable as undocumented environment drift.

### 6.6 Source adapters

Each adapter has:

- enabled flag;
- provider endpoint and dataset/product ID;
- credential/secret reference;
- poll schedule and lookback window;
- rate/concurrency limits;
- target raw bucket/prefix policy;
- adapter/calibration profile version;
- freshness threshold profile;
- licence/citation record reference.

Secrets are never represented in status endpoints. A disabled adapter reports `disabled by configuration`, not `healthy`.

### 6.7 Startup validation

Services SHALL fail readiness (and fail fast for nonrecoverable errors) when:

- required variable is absent or malformed;
- environment/mode/disclaimer are inconsistent;
- DB schema is incompatible;
- model digest or input signature does not match deployment manifest;
- category/RI/wind policy cannot resolve;
- bucket/queue access lacks required operation;
- OIDC issuer/audience configuration is invalid in an authenticated profile; or
- external notifications are enabled without an approved channel/rule profile.

Do not silently fall back to insecure defaults outside local development.

---

## 7. Networking, DNS, and edge

### 7.1 Public routes

Preferred single-origin layout:

```text
https://<host>/                 web application
https://<host>/assets/*        immutable versioned static assets
https://<host>/api/v1/*        application API
https://<host>/downloads/*     authorised API redirect/stream or signed object URL
```

The web bundle uses relative `/api/v1` URLs. This avoids cross-origin complexity and ensures remote preview/proxy environments work. Browser code must never call `localhost` or private service DNS.

### 7.2 Ingress controls

- TLS 1.2+ (or institutional baseline) with automated certificate rotation.
- HTTP→HTTPS redirect outside local development.
- Exact host allowlist; accept the approved preview host only in development/demo configuration.
- Request body limits by route; upload limits enforced at both edge and application.
- Rate limits separated for read, state change, login callback, upload, and job creation.
- Connection/header/timeouts configured against slow-client abuse and legitimate scientific uploads.
- Security headers: HSTS where safe, CSP, frame-ancestors, nosniff, referrer policy, permissions policy.
- Forwarded headers trusted only from known proxy CIDRs.
- Compression disabled for already compressed imagery and reviewed for secret-bearing responses.

### 7.3 Internal networking

- Database, object store, broker, registry, model servers, and management endpoints are private.
- Default-deny network policy where supported.
- API may reach DB/object/queue/IdP/audit, not arbitrary external hosts.
- Ingest may reach allowlisted providers plus internal data services.
- Workers reach object/queue/DB/model servers; upload worker is more restricted.
- Model servers read pinned artefacts and serve internal inference; no public ingress/general egress.
- Report renderer runs without unrestricted egress.

### 7.4 CORS and CSRF

Single origin is preferred. If CORS is required:

- exact environment origins only;
- no wildcard with credentials;
- narrow methods/headers;
- preflight cache bounded;
- server still validates authentication/authorisation.

Cookie-based state changes use CSRF protection consistent with the OIDC/session pattern. Bearer-token storage in browser local storage should be avoided where a secure BFF/session design is available.

---

## 8. Target local application workflow

This section becomes executable once the referenced files exist. It is the desired developer experience, not a current command guarantee.

### 8.1 Planned prerequisites

- Docker Engine with Compose v2 or approved compatible runtime.
- Python and Node versions declared in repository tool files.
- CPU-only fixture model packages checked by hash or fetched by a safe setup task.
- At least 8 GB RAM recommended for a small stack; exact profile measured later.

### 8.2 Planned commands

```bash
cp .env.example .env.local        # contains no real secrets
make bootstrap                    # lock-aware dependency/tool checks
make dev-infra                    # PostGIS, object store, queue, local OIDC fixture if used
make migrate
make seed-fixtures
make dev                          # API/web/workers bind through one previewable gateway
make test
make down
```

The gateway/dev server must bind to `0.0.0.0` for remote preview and allow the explicitly configured preview host/origin. The UI still calls relative `/api` routes.

### 8.3 Local profiles

- `core`: DB/object/queue/API/web with fixture inference.
- `ml-cpu`: small real CPU models.
- `observability`: local metrics/logs/traces.
- `integration`: fixture source server and test identity provider.

External provider credentials should not be necessary for the default development/test path.

---

## 9. Reference Kubernetes deployment

Kubernetes is a reference for shadow/pilot, not a requirement for the initial demo.

### 9.1 Namespaces and service accounts

Example environment namespace: `cyclone-ai-shadow`.

Distinct service accounts:

- `web` (usually no data permissions);
- `api`;
- `ingest`;
- `worker`;
- `report-worker`;
- `detection-serving`;
- `intensity-serving`;
- `prediction-serving`;
- `migration-job`;
- `backup-job` if platform-managed backup is unavailable.

Do not use the default service account for workloads. Disable automatic service-account token mount where not needed.

### 9.2 Workload types

| Component | Kubernetes type | Notes |
|---|---|---|
| Web | Deployment | ≥2 replicas for pilot; static readiness |
| API | Deployment + Service | HPA on CPU/request/latency as validated |
| Ingest scheduler | Deployment or CronJobs | Leader election or singleton lease to avoid duplicate schedule |
| CPU workers | Deployment | Scale on queue age/depth using approved autoscaler |
| GPU model servers | Deployment | GPU requests/limits, node affinity/taint, controlled rollout |
| Prediction/intensity CPU servers | Deployment | Separate resource profiles |
| Report workers | Deployment | Isolated queue and sandbox limits |
| Migrations | Pre-deploy Job | Exact image digest; never auto-run independently in every API pod |
| Reconciliation/retention | CronJob | Idempotent, audited, concurrency policy `Forbid` where needed |

### 9.3 Pod security

Target pod/container security context:

```yaml
runAsNonRoot: true
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
seccompProfile:
  type: RuntimeDefault
```

Set numeric user/group, resource requests/limits, ephemeral storage limits, writable `emptyDir` only where needed, and no host networking/PID/IPC/path. Exceptions require threat review.

### 9.4 Availability and scheduling

- API/web replicas spread across nodes/zones via topology constraints.
- Pod disruption budgets are compatible with replica count and maintenance.
- Readiness prevents traffic until dependency/schema/model compatibility passes.
- Startup probes allow large model load without liveness restart loop.
- GPU model rollout uses surge capacity only if the cluster can host both versions; otherwise use explicit blue/green or maintenance plan.
- Grace period accommodates job lease release/checkpoint policy.
- HPA minimums avoid complete cold start for required capabilities.

### 9.5 Resource management

Every container sets measured requests and limits. Initial values are hypotheses and must be load-tested. Watch:

- API CPU/memory and DB pools;
- parser/preprocessor memory and ephemeral disk for large scientific files;
- model RAM/VRAM and warm-up time;
- worker lease duration and OOM retry loops;
- report renderer CPU/memory;
- node disk pressure from model/image layers.

OOM is classified as a resource failure; automatic retries are bounded to prevent a poison job loop.

---

## 10. Database deployment and migrations

### 10.1 Roles

- `app_runtime`: CRUD only on required application objects, no schema ownership.
- `migration`: time-bound role with schema-change permissions.
- `readonly_support`: audited, limited diagnostic views.
- `backup`: platform-specific minimum backup permission.
- `audit_writer`: append-only path for audit events where separated.

Credentials are distinct per environment/service. Shared superuser credentials are prohibited.

### 10.2 Migration strategy

Use versioned migrations and the **expand → migrate/backfill → switch → contract** pattern:

1. **Expand:** add backward-compatible tables/columns/indexes.
2. Deploy code capable of old/new shape.
3. **Backfill:** bounded, resumable, observable job.
4. Switch reads/writes through configuration/release.
5. Validate counts/checksums/queries.
6. **Contract:** remove old shape only in a later release after rollback window.

Migrations SHALL:

- be tested against a production-like anonymised/schema fixture;
- declare expected duration/locks/storage growth;
- use lock/statement timeouts;
- be backed up or have a tested reverse/forward recovery plan;
- run once from an exact release image;
- block application readiness if schema is incompatible;
- avoid irreversible destructive changes in the same release as the dependent code change.

### 10.3 Deployment ordering

Typical compatible release:

```text
backup/check → expand migration → workers/model servers → API → web
→ smoke/verification → backfill if any → observe → later contract migration
```

Stop and roll back application routing if migration or invariant checks fail. Do not improvise manual SQL without recording/review during a release.

---

## 11. Object storage and data lifecycle

### 11.1 Buckets/policies

Separate raw, derived, models, reports, and quarantine by bucket or strong policy prefix. Configure:

- server-side encryption;
- versioning for immutable/critical classes where supported;
- public access blocked;
- bucket ownership and least-privilege IAM;
- lifecycle to approved storage/archive/delete tiers;
- object lock/WORM only where governance requires it;
- access logging if permitted and useful;
- replication according to RPO/region policy;
- incomplete multipart-upload cleanup; and
- CORS only if direct signed browser transfer is approved.

### 11.2 Integrity

- Compute SHA-256 while ingesting.
- Store digest in canonical metadata and object metadata.
- Verify upload completion before marking available.
- Validate digest when promoting model artefacts and during sampled integrity scans.
- A provider correction produces a new content revision.
- Never overwrite an object addressed by digest.

### 11.3 Retention

Retention policy is approved per data class/source licence. Lifecycle jobs report planned and completed counts/bytes, respect legal/scientific holds, and avoid deleting an input/model needed by a retained analysis. User uploads have a short disclosed default and separate prefix/policy.

---

## 12. Model packaging and release

### 12.1 Promotion prerequisites

A model is deployable only when its registry package contains:

- immutable artefact digest;
- model and preprocessing versions;
- exact input/output signature;
- training dataset manifest and code revision;
- test/validation evaluation report with storm/sample counts and slices;
- required baseline comparison;
- calibration artefact where applicable;
- model card, limitations, intended/excluded use;
- resource/latency profile;
- golden inference fixture and tolerance;
- dependency/runtime/SBOM reference;
- ML and meteorological approval; security/platform approval where required.

### 12.2 Build-time vs startup download

For pilot, prefer either:

1. model embedded in a model-server OCI image and verified at build/start; or
2. immutable model artefact mounted/injected by deployment tooling, pinned by digest and fully downloaded/verified before readiness.

Do not fetch a mutable `latest` model from the internet during normal startup.

### 12.3 Model rollout

1. Register candidate; never overwrite existing version.
2. Validate signature against target preprocessor contract.
3. Deploy in staging and run golden, load, OOD, and failure tests.
4. Shadow against the same incoming observations without user-default routing where feasible.
5. Compare scientific/system metrics and alert workload.
6. Record approval.
7. Deploy canary/blue-green to a bounded percentage of **new** jobs using deterministic routing.
8. Observe predefined window and gates.
9. Promote default or roll back route.
10. Retain old model while any retained result or rollback window requires it.

Existing analyses never change after model promotion.

### 12.4 Compatibility

Deployment fails readiness when:

- preprocessor output signature does not match model input;
- output schema is incompatible with API/rules;
- calibration/category/RI policy dependencies cannot resolve;
- model digest differs;
- runtime lacks required operator/device;
- golden fixture exceeds numeric tolerance.

---

## 13. CI/CD pipeline

### 13.1 Pull-request checks

Target checks:

1. repository hygiene: no large data/model/secret files;
2. formatting, linting, type/static analysis;
3. Python and frontend unit/component tests;
4. scientific golden/property tests;
5. API/event/manifest schema and compatibility checks;
6. storm-split leakage validation for committed fixture manifests;
7. accessibility automated tests;
8. SAST, dependency licence/vulnerability, secret scanning;
9. Dockerfile/container lint and image scan;
10. migration forward/backward compatibility tests;
11. infrastructure/Helm policy and schema validation;
12. documentation link and Mermaid/Markdown checks;
13. ephemeral integration tests with fixture sources and no production credentials.

Required checks and review approvals protect the main release branch. Scientific or policy code paths should request domain/ML code owners.

### 13.2 Build

On approved merge/tag:

- build once from clean checkout;
- generate version metadata;
- create deterministic/locked web and Python artefacts;
- build multi-stage OCI images;
- run tests against built images;
- generate SBOM, provenance/attestation, signatures if platform supports them;
- push to private registry under version and immutable digest;
- publish migrations and deployment chart tied to same release;
- never bake environment secrets into artefacts.

### 13.3 Promotion

Promote the same image digest through environments; do not rebuild per environment. Environment configuration and secrets are separate, reviewed artefacts. Suggested flow:

```text
PR checks → build/sign → ephemeral integration → demo → staging/shadow
→ automated smoke + manual scientific/product approval → controlled pilot
```

Pilot deployment requires a human approval gate and a linked change record. CI identity receives only the permissions required for the target environment and preferably uses short-lived workload federation.

### 13.4 Supply-chain controls

- Pin GitHub Actions by full commit SHA for sensitive workflows.
- Restrict pull-request workflows from accessing deployment secrets.
- Use protected environments and branch/ruleset approvals.
- Verify signatures/attestations at admission when available.
- Mirror dependencies/base images for restricted deployment.
- Record exceptions with owner, justification, expiry, and compensating control.

---

## 14. Deployment procedure

### 14.1 Pre-deployment checklist

- [ ] Change/release record identifies Git SHA, image/model/policy digests, and target environment.
- [ ] Required CI, security, scientific, API compatibility, migration, and accessibility gates pass.
- [ ] Model card/evaluation and approvals are attached for model changes.
- [ ] Scientific policy diff and domain approval are attached for policy changes.
- [ ] Capacity exists for surge/blue-green and DB connection budget.
- [ ] Backup/PITR state is healthy; restore procedure is current.
- [ ] Migration lock/duration/backfill plan reviewed.
- [ ] Rollback target and commands/manifests are known and retained.
- [ ] Monitoring dashboards and release annotations are ready.
- [ ] On-call owner and stakeholder communication window confirmed.
- [ ] Provider maintenance/active storm risk reviewed before timing a pilot change.

### 14.2 Deployment steps

1. Announce start and freeze conflicting administrative changes.
2. Snapshot/export current deployment, model routes, policy versions, and schema version.
3. Verify backup status and dependency health.
4. Apply backward-compatible configuration/secrets and validate references without logging values.
5. Run expand migration job; verify schema and invariants.
6. Deploy new model servers in non-serving/canary state; wait for startup/readiness and golden check.
7. Deploy workers/ingest with leases drained or compatible rolling strategy.
8. Deploy API replicas; verify readiness and API contract smoke tests.
9. Deploy web assets; verify single-origin relative API routing and CSP.
10. Route a bounded canary of new requests/jobs if supported.
11. Run post-deployment verification below.
12. Observe predefined window; compare with baseline.
13. Complete promotion or initiate rollback.
14. Annotate dashboards, close change record, and publish outcome.

### 14.3 Post-deployment verification

**Platform**

```text
- All expected workloads ready; no restart/OOM loop.
- Correct image digests and release metadata.
- Liveness and readiness behave independently.
- DB migration at expected version; no long locks.
- Queue depth/oldest age/retry/dead letter normal.
- Object read/write/checksum probe succeeds with scoped identity.
- Model load/golden inference succeeds on intended device.
```

**Application**

```text
- Sign-in and role matrix for viewer/analyst/admin test identities.
- GET /api/v1/status exposes correct safe versions/freshness.
- Storm list/detail and exact historical timestamp route.
- Submit idempotent fixture job twice; one logical result.
- Partial/invalid fixture displays correct state.
- Alert transition produces immutable review/audit event.
- Report contains disclaimer, mode, UTC, units, versions, quality, attribution.
- Browser makes no localhost/private-service request.
```

**Scientific**

```text
- Golden preprocess tensor checksum/tolerance.
- Detection/intensity/prediction outputs within approved numeric tolerance.
- Category boundary and RI rule fixtures resolve to expected policy versions.
- Source valid time and wind averaging metadata preserved.
- Provenance resolves every source/derived/model/policy digest.
```

**Observability/security**

```text
- Trace/correlation ID crosses API, queue, worker, model server.
- No token/signed URL/secret in sampled logs.
- Release annotation and test alert route work.
- Unauthorised state changes return denial and audit as approved.
- TLS/security headers/host/CORS/upload limits match environment.
```

### 14.4 Acceptance window

Define before deployment, for example:

- minimum observation count and/or 60-minute technical window;
- no elevated 5xx/worker failure/dead-letter rate;
- latency/queue age within SLO;
- no golden/scientific contract violation;
- no unexpected alert-volume increase beyond declared tolerance;
- no source-freshness regression caused by deployment.

Do not declare success based only on pods being “green.”

---

## 15. Rollback

### 15.1 Rollback triggers

- incompatible or incorrect scientific output;
- provenance/manifest incompleteness;
- elevated error, timeout, queue age, or resource exhaustion beyond gate;
- incorrect alert creation/deduplication;
- authentication/authorisation/audit regression;
- data corruption, schema invariant failure, or source-ingest duplication;
- browser/API route/CSP outage;
- critical exploitable security issue.

### 15.2 Application rollback

1. Pause automatic/canary routing if necessary; preserve queued work.
2. Route new jobs/traffic to the last approved image/model/policy digests.
3. Confirm old version is schema-compatible (enabled by expand/contract strategy).
4. Drain or terminate affected workers safely; leases make work retryable.
5. Verify core, scientific, security, and telemetry smoke checks.
6. Keep failed release artefacts/logs/manifests for investigation.
7. Record rollback, impact window, affected analyses/jobs, and owner.

Analyses already created by the new version remain immutable and clearly versioned. Do not rewrite them; mark affected versions for review through governance if needed.

### 15.3 Database rollback

Prefer application rollback/forward fix over destructive down migrations. If a DB restore is unavoidable:

- declare incident and stop writes;
- assess metadata RPO and object/queue reconciliation;
- restore to separate instance first where possible;
- validate schema, counts, checksums, latest IDs/times, outbox/audit continuity;
- reconcile object orphans and broker messages idempotently;
- approve cutover and document lost/replayed writes.

### 15.4 Model/policy rollback

- Change default routing to exact prior approved version.
- Do not delete failed model/policy.
- Stop alert eligibility from the affected version if safety demands; preserve alert history.
- Identify all analyses created in impact window by version/digest.
- Re-analysis creates linked new records; it does not overwrite.

---

## 16. Health checks and graceful lifecycle

### 16.1 Endpoints

| Endpoint | Audience | Meaning |
|---|---|---|
| `/health/live` | Internal orchestrator | Process event loop is responsive; no broad dependency checks |
| `/health/ready` | Internal orchestrator | Can accept work/traffic: config, schema, mandatory dependency, and model signature ready |
| `/api/v1/status` | Authenticated product users; safe subset | Capability/source freshness/version/incident summary |
| `/metrics` | Monitoring network only | Prometheus/OpenMetrics-compatible telemetry; no secrets/high-cardinality user data |

Never expose stack traces, credentials, raw DSNs, internal host inventory, or signed URLs.

### 16.2 Service-specific readiness

- **API:** configuration valid, DB schema compatible, mandatory DB/queue access available, identity metadata available per caching policy.
- **Ingest:** DB/object/queue access and adapter configuration; external provider outage may mark capability degraded rather than restart-loop the process.
- **Worker:** queue, object store, DB, required preprocessing resources.
- **Model server:** exact model loaded, digest and input signature verified, golden warm-up passed, device memory healthy.
- **Web:** static asset and configuration integrity; API health is shown to user but not necessarily a static-server readiness dependency.

### 16.3 Shutdown

On SIGTERM:

1. mark not ready;
2. stop accepting API work or leasing jobs;
3. finish in-flight short requests within grace period;
4. heartbeat/checkpoint/release long job lease according to idempotency design;
5. flush bounded telemetry/outbox buffers;
6. close pools and exit before termination deadline.

---

## 17. Observability and alerting

### 17.1 Required dashboards

1. **Service overview:** request rate/error/duration, replicas/restarts, dependency health.
2. **Pipeline:** source lag, observations ingested, DQ outcomes, queue age/depth, retries/dead letters, end-to-end latency.
3. **Model serving:** request/latency/error, batch size, CPU/GPU utilisation/memory, load time, abstention, version.
4. **Product:** active/open alerts, review age, report job outcomes, mode; no personal/free-text data.
5. **Data stores:** DB connections/locks/replication/storage, object error/capacity, broker memory/delivery.
6. **ML monitoring:** source/input/output drift and delayed quality/calibration slices when reference data arrive.
7. **Release:** deployment markers and before/after comparison.

### 17.2 Proposed SLOs for shadow mode

| SLI | Objective | Exclusions/notes |
|---|---|---|
| API availability | 99.5% monthly | Agreed maintenance excluded only if policy says so |
| Metadata API latency | p95 ≤ 500 ms | Declared reference request mix; binary transfer excluded |
| Observation-to-result | p95 ≤ 5 min | Upstream provider delay excluded; clock points defined |
| Inference job success | Target set after load/scientific fixtures | User-invalid/quarantined input counted separately |
| Source freshness | Per adapter profile | Valid observation time, not just successful polling |
| Provenance completeness | 100% for published results | Hard quality gate, not best effort |

Pilot SLOs are agreed with the service owner after shadow evidence. Model accuracy is monitored separately from service reliability.

### 17.3 Operational alert tiers

| Tier | Example | Response |
|---|---|---|
| Page/critical | Provenance corruption, all analysis unavailable during agreed coverage, unauthorised change, sustained mandatory feed/pipeline outage | Immediate on-call according to agreed policy |
| Urgent/ticket | Queue age approaching SLO, one model capability unavailable, backup failure, certificate near expiry | Prompt owned response |
| Review | Input/output drift, alert volume shift, increasing abstention, storage growth | ML/data/platform review, not automatic page unless severe |
| Informational | Deployment complete, optional source delayed | Dashboard/change record |

Meteorological RI alerts are product records, not SRE pages. Keep these channels and semantics separate.

### 17.4 Logging

Structured fields:

```text
timestamp, severity, service, environment, release, event_code,
trace_id, correlation_id, route/job_attempt (when required), outcome,
duration_ms, safe_error_code
```

Prohibited:

- access/refresh tokens and cookies;
- passwords, provider credentials, full DSNs;
- full signed object URLs;
- raw user upload content;
- review free text by default;
- unrestricted personal identity;
- massive arrays or full provider payloads.

Use event codes and trace IDs to retrieve authorised detail from systems of record.

---

## 18. Backup, restore, and disaster recovery

### 18.1 Data criticality

| Data | Backup/replication objective |
|---|---|
| PostgreSQL metadata/workflow/reviews | PITR-capable backups for pilot; encrypted and cross-failure-domain per policy |
| Raw source objects | Versioning/replication or reproducible redownload based on licence, cost, and source stability |
| Derived objects | Rebuildable only if manifest/input/model retained; otherwise back up as critical |
| Model artefacts/cards/evaluation | Immutable replicated registry/object backup |
| Reports | Back up if required by retention/audit; otherwise reproducible only from retained exact template/runtime |
| Audit records | Protected long-retention copy according to institutional policy |
| Configuration/IaC | Git plus protected deployment state/secret references; not secret values in Git |
| Secrets | Secret-manager backup/replication and recovery process; rotation preferred after incident |

### 18.2 Proposed recovery objectives

For shadow mode/pilot baseline review:

- Metadata RPO: ≤ 24 hours; improve where managed PITR supports it.
- Service RTO: ≤ 4 hours.
- Audit/model artefact loss: no accepted loss within configured durable system; exact commitment depends on platform.
- Raw data RPO: source/licence/storage-class specific.

These are proposed, not promised until measured restore tests and ownership approval.

### 18.3 Restore test

At least quarterly for pilot, and before first readiness sign-off:

1. provision isolated recovery environment;
2. restore database to selected point;
3. restore/mount object, model, and audit copies;
4. deploy matching application/model/policy digests;
5. validate schema, counts, object references/checksums, roles, and latest valid times;
6. replay representative analysis and compare within tolerance;
7. validate no external product notifications are enabled;
8. measure RPO/RTO;
9. destroy recovery environment securely;
10. document findings and remediate gaps.

A successful backup job without restore evidence is not a completed recovery control.

### 18.4 Regional/site disaster

If multi-region/site recovery is required:

- pre-provision or codify network/DNS/identity/data dependencies;
- define authoritative writer and prevent split brain;
- replicate object/model data and database according to approved consistency/RPO;
- use DNS/ingress TTL and certificate strategy;
- keep external notifications disabled until data freshness/integrity and owner approval are confirmed;
- run a controlled failover exercise.

---

## 19. Operational runbooks

### 19.1 Source is stale

**Signal:** latest valid observation exceeds source-specific threshold.

1. Confirm valid time versus ingest/poll time; avoid mistaking a successful empty poll for freshness.
2. Check provider status, credentials, rate limit, DNS/TLS, adapter errors, and clock.
3. Identify affected models/alerts and verify UI shows degraded state.
4. Pause blind retries if provider is throttling; follow provider policy.
5. Do not manually fabricate/retime an observation.
6. Backfill with adapter idempotency when source recovers.
7. Verify no duplicate analyses/alerts and freshness returns.
8. Record incident and source gap.

### 19.2 Queue backlog

**Signal:** oldest eligible job age or depth breaches threshold.

1. Segment interactive, automatic, replay, report queues.
2. Check worker readiness, OOM/restarts, leases, DB/object/model latency, and poison jobs.
3. Pause/restrict replay batch first; preserve interactive/automatic capacity.
4. Scale only after confirming downstream capacity and provider limits.
5. Move permanent failures to dead-letter; do not infinite-retry.
6. Verify end-to-end latency recovery and inspect delayed alerts for relevance policy.

### 19.3 Model server unavailable

1. Confirm readiness reason: artefact, signature, device, memory, dependency, golden warm-up.
2. Keep affected product capability explicitly unavailable.
3. Route new jobs to the last approved compatible model if the rollback procedure permits.
4. Do not substitute an unapproved model just to turn readiness green.
5. Identify and safely retry eligible jobs after restoration.

### 19.4 Elevated model abstention or drift

1. Segment by source, channel, time, geography, intensity, and model version.
2. Verify upstream calibration/preprocessing/source metadata before blaming model.
3. Compare recent deploy/source changes and approved baseline.
4. Notify ML/data/domain owners; preserve samples/manifests under policy.
5. Continue, restrict, or roll back according to approved model incident rule.
6. Never retrain/promote automatically in response.

### 19.5 Incorrect/duplicate alert

1. Identify alert, analysis, model, rule, idempotency/dedup key, and all related alerts.
2. Preserve records; do not delete or rewrite.
3. If safety/workload requires, disable external delivery or affected rule version through audited emergency change.
4. Verify machine probability versus rules-engine decision and source quality.
5. Mark/resolve through approved review process and notify affected users.
6. Fix, test repeated delivery/concurrency, deploy, and audit impact window.

### 19.6 Database saturation

1. Check connection pools, long transactions, locks, slow queries, migrations, storage/IO.
2. Shed batch/replay work and apply API backpressure before exhausting DB.
3. Avoid arbitrary pool increases beyond DB budget.
4. Terminate queries only with incident authority and understanding of transaction impact.
5. Validate job/outbox/idempotency consistency after recovery.

### 19.7 Suspected credential or data compromise

1. Follow institutional security incident process immediately.
2. Contain affected identity/service, revoke/rotate secrets and signed URLs, preserve evidence.
3. Disable affected source/egress or state-changing capability without erasing audit.
4. Determine accessed data, model/policy changes, reports, and time window.
5. Restore from known-good artefacts/configuration and validate integrity.
6. Complete required notification, root cause, and key rotation.

Do not place sensitive evidence in public issue trackers or normal chat channels.

---

## 20. Security operations

### 20.1 Secret management

- Use workload identity rather than long-lived static keys where available.
- Inject secrets at runtime through approved secret store; never bake into image or ConfigMap.
- Scope by service/environment and operation.
- Rotate on schedule and after personnel/incident/change events.
- Support overlapping keys/credentials where provider permits to avoid downtime.
- Audit reads and changes.
- CI uses short-lived federation and protected environments.
- Local `.env.local` is untracked and contains only developer-scoped values.

A future `.env.example` contains variable names and safe placeholders only.

### 20.2 Vulnerability management

- Scan source, dependencies, lockfiles, IaC, images, and SBOM.
- Triage based on exploitability and exposure, not only score.
- Critical exploitable findings block promotion unless the security owner records a time-bounded exception.
- Rebuild immutable images after base/dependency patch; do not patch running containers manually.
- Track end-of-life Python/Node/Postgres/CUDA/runtime versions.
- Periodically rescan deployed image digests because new advisories appear after release.

### 20.3 Access review

Before pilot and periodically:

- OIDC group-to-role map;
- administrators and model/policy approvers;
- service-account permissions;
- database/object/broker/registry grants;
- CI/CD environment permissions;
- dormant users/keys;
- break-glass procedure and use logs.

### 20.4 Audit verification

Test that:

- inference, review, alert transition, export, configuration, and model/policy promotion generate events;
- ordinary app users cannot update/delete audit records;
- actor, target, outcome, UTC time, and correlation ID are present;
- secret redaction works;
- retention/archival and clock synchronisation are healthy.

---

## 21. Capacity and cost management

### 21.1 Required sizing inputs

Record per environment:

- scenes and track/environment objects per hour, including burst;
- average/p95 compressed/uncompressed object size;
- derived tensor/feature/report expansion factor;
- active/historical storm count and retention;
- per-model CPU/GPU memory, warm-up, batch, and latency;
- concurrent interactive users/jobs/replays;
- DB row/write/query rate and connection budget;
- availability/replica/zone and backup requirements.

### 21.2 Cost controls

- Lifecycle raw/derived objects to appropriate storage class only when retrieval/RTO permits.
- Deduplicate by content hash; avoid copying arrays between workflow stages.
- Use CPU models for demo or low-rate tasks if latency gates pass.
- Scale batch/replay to zero or schedule off-peak where safe; keep required live capability warm.
- Set per-user/project replay/upload quotas.
- Cache explanation overlays by input+model digest.
- Set budgets/alerts for GPU, object storage, egress, telemetry, and managed DB.
- Avoid public tile/API egress surprises with approved internal cache/tiles.
- Keep high-cardinality labels out of metrics to control telemetry cost.

Cost optimisation may not remove reproducibility artefacts required by retention policy or reduce required availability/security without owner approval.

---

## 22. Maintenance procedures

### 22.1 Dependency/runtime upgrades

1. Identify compatibility and end-of-life deadlines.
2. Update locks/base digests; generate SBOM and scans.
3. Run scientific golden results for numeric drift.
4. Run API/schema, migration, load, and accessibility tests.
5. For CUDA/ONNX/PyTorch changes, compare outputs across representative devices/tolerances.
6. Deploy through normal staged rollout and retain rollback image.

A runtime change that alters model output beyond tolerance is treated as a model/scientific change, not routine patching.

### 22.2 Certificate/key rotation

- Inventory certificate/secret owners and expirations in monitored systems.
- Prefer automated renewal with alerts well before expiry.
- Test overlap for signing/session/object keys.
- Rotate without logging values.
- Verify old credentials are revoked after grace period.

### 22.3 Storage lifecycle and integrity

- Monitor capacity, lifecycle failures, replication lag, orphan objects, and checksum sample failures.
- Reconcile DB references to object existence and vice versa after a safety window.
- Quarantine, do not silently delete, when integrity mismatch is found.
- Validate retained model/input dependencies before lifecycle deletion.

### 22.4 Queue dead-letter review

- Review on an owned schedule and alert on age/count.
- Classify permanent input, transient platform, code defect, resource, and poison job.
- Replay only after cause is addressed and with original idempotency context.
- Retain investigation/audit linkage; do not bulk requeue blindly.

---

## 23. Demo-day operating plan

A demonstration needs a controlled fallback without misrepresenting live capability.

### 23.1 Before the event

- Pin exact application/model/policy/data manifest digests.
- Cache/licence-check the historical event locally/in demo storage.
- Rehearse from a clean environment and restricted network.
- Run full event replay at least twice and capture timings.
- Pre-warm model servers and verify disk/GPU capacity.
- Disable autonomous external notifications.
- Confirm mode/disclaimer on every screen/report.
- Prepare read-only screenshots/video and a static report as fallback, clearly labelled recorded.
- Have one operator and one presenter; avoid ad hoc admin changes during presentation.

### 23.2 Day-of checks

- TLS/DNS/login and intended browser/display.
- API/model/data readiness and source fixtures.
- Relative API routes; no localhost requests in browser dev tools.
- Exact historical timestamps, expected outputs, provenance, and accessibility zoom.
- Backup demo path accessible without external provider dependency.
- Stop unrelated replay/training workloads.

### 23.3 Failure handling

State transparently whether the audience is seeing live inference, cached historical inference, or recorded fallback. Never label replayed data as current operations.

---

## 24. Decommissioning

For an environment or product shutdown:

1. Obtain owner, data-governance, security, and source-licence approval.
2. Disable new ingestion/jobs/alerts and external integrations.
3. Export required manifests, model/policy packages, reports, and audit records.
4. Verify retention/legal/scientific hold obligations.
5. Revoke OIDC clients, service identities, provider credentials, signing keys, and signed URL capability.
6. Delete or archive data by class, including replicas, multipart uploads, snapshots, and backups according to policy.
7. Destroy compute, network routes, DNS/certificates, registries, queues, and secret versions.
8. Confirm no public bucket/endpoints or recurring costs remain.
9. Record destruction/archival evidence and final responsible owner.

Deleting application infrastructure before preserving required model/input/audit artefacts can make retained analyses irreproducible and is prohibited.

---

## 25. Readiness gates

### 25.1 Demonstration readiness

- [ ] Reproducible installation/build from clean checkout.
- [ ] Exact historical data/model/policy versions pinned.
- [ ] Core end-to-end and failure states rehearsed.
- [ ] Non-operational mode/disclaimer present.
- [ ] No credentials/raw restricted data in Git/image/logs.
- [ ] Backup presentation path prepared and honestly labelled.
- [ ] Basic vulnerability/secret scanning completed.

### 25.2 Shadow-mode readiness

- [ ] All P0 SRS requirements implemented and evidenced for this mode.
- [ ] Institutional identity, RBAC, protected audit, and access review.
- [ ] Threat model/security test findings resolved or accepted.
- [ ] Storm-level model evaluation and meteorological approval.
- [ ] Source licences, adapters, calibration, freshness, and failure paths approved.
- [ ] Immutable manifests/model packages/policies and rollback proven.
- [ ] Dashboards, SLOs, actionable alerts, on-call ownership, and runbooks.
- [ ] Backup restore meets measured RPO/RTO.
- [ ] Load/resilience/accessibility/user-acceptance tests complete.
- [ ] External public/official dissemination remains disabled.

### 25.3 Controlled-pilot readiness

- [ ] Named service/product/domain/security/data owners accept responsibility.
- [ ] Approved operating procedure defines human authority and incident escalation.
- [ ] Formal SLO/support window and change process.
- [ ] Privacy/retention/licence and institutional security approvals.
- [ ] Shadow evidence demonstrates acceptable technical stability, scientific performance, calibration, and alert workload.
- [ ] Disaster recovery and rollback exercise completed.
- [ ] User training, terminology, disclaimers, and accessibility sign-off.
- [ ] Pilot scope, users, data, duration, and success/stop criteria documented.

---

## 26. Implementation backlog implied by this guide

1. Pin Python/tool versions and add automated test/quality configuration.
2. Add canonical JSON Schemas/OpenAPI and scientific golden fixtures.
3. Introduce API/web/worker vertical slice with PostGIS, object storage, and queue.
4. Add Dockerfiles, Compose development profile, health checks, and `.env.example`.
5. Add migrations, idempotent jobs, manifests, audit, and RBAC.
6. Package models by immutable digest with model cards/evaluation.
7. Add CI build/test/scan/SBOM/provenance and branch protections.
8. Add declarative demo then shadow infrastructure.
9. Implement telemetry, dashboards, alert rules, backup/restore automation.
10. Conduct threat model, load/resilience, accessibility, domain, and user acceptance reviews.

Each item should link back to SRS requirement IDs and have an owner/evidence definition.

---

## 27. Operational ownership record

| Responsibility | Primary | Backup | Contact/runbook |
|---|---|---|---|
| Product/service owner | TBD | TBD | TBD |
| Meteorological authority | TBD | TBD | TBD |
| Data source/adapters | TBD | TBD | TBD |
| ML models and monitoring | TBD | TBD | TBD |
| Application/API/UI | TBD | TBD | TBD |
| Platform/SRE/on-call | TBD | TBD | TBD |
| Security incident response | TBD | TBD | Institutional process TBD |
| Data governance/licensing | TBD | TBD | TBD |

A shadow or pilot deployment must not proceed while critical ownership remains `TBD`.

---

## 28. Approval record

| Role | Decision | Name/date |
|---|---|---|
| Engineering/release lead | Pending | — |
| Platform/SRE lead | Pending | — |
| Security reviewer | Pending | — |
| Data/ML lead | Pending | — |
| Meteorological/product owner | Pending | — |
