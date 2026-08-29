import {
  ArrowRight,
  Box,
  Check,
  CircleAlert,
  CloudCog,
  Code2,
  Cpu,
  Database,
  ExternalLink,
  FileCheck2,
  GitBranch,
  Layers3,
  LockKeyhole,
  RefreshCw,
  Satellite,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import type { SystemStatus } from "../types";

interface Props {
  status: SystemStatus;
}

export default function DataModel({ status }: Props) {
  return (
    <div className="view-stack data-view">
      <section className="page-heading">
        <div>
          <div className="eyebrow"><Layers3 size={13} /> Data & model control plane</div>
          <div className="heading-row"><h1>Transparent by design</h1><span className="quality-tag"><Check size={12} /> replaceable</span></div>
          <p>Inspect what is real today, what is provisional, and how the model can improve later.</p>
        </div>
        <a className="button secondary" href="/api/docs" target="_blank" rel="noreferrer"><Code2 size={16} /> Open API contract</a>
      </section>

      <section className="readiness-strip">
        <div><span className="status-dot ready" /><p><strong>Demo API</strong><small>Ready</small></p></div>
        <i />
        <div><span className="status-dot ready" /><p><strong>Historical data</strong><small>{status.dataset.source_row_count} rows</small></p></div>
        <i />
        <div><span className="status-dot ready" /><p><strong>ONNX model</strong><small>Digest verified</small></p></div>
        <i />
        <div><span className="status-dot caution" /><p><strong>Scientific approval</strong><small>Not validated</small></p></div>
      </section>

      <section className="source-grid">
        {status.sources.map((source) => (
          <article className="panel source-card" key={source.id}>
            <div className={`source-icon source-${source.status}`}>
              {source.id === "insat" ? <Satellite size={22} /> : source.id === "ibtracs" ? <GitBranch size={22} /> : <Database size={22} />}
            </div>
            <div className="source-title"><h2>{source.name}</h2><span className={`source-status status-${source.status}`}>{source.status.replace("_", " ")}</span></div>
            <p>{source.detail}</p>
            <div className="source-meta"><span>{source.mode.replace("_", " ")}</span><span>ID · {source.id}</span></div>
          </article>
        ))}
      </section>

      <section className="model-layout">
        <article className="panel model-card-main">
          <header className="model-hero-header">
            <div className="model-cube"><Box size={29} /><span /></div>
            <div><span className="result-kicker">Active intensity model</span><h2>{status.model.id}</h2><p>Legacy Kaggle-trained CNN · converted to portable ONNX</p></div>
            <span className="legacy-badge"><CircleAlert size={13} /> Demo only</span>
          </header>
          <div className="model-spec-grid">
            <Spec icon={<Cpu size={17} />} label="Runtime" value={status.model.runtime} />
            <Spec icon={<SlidersHorizontal size={17} />} label="Task" value="Image → Vmax regression" />
            <Spec icon={<ShieldCheck size={17} />} label="Integrity" value="SHA-256 verified" />
            <Spec icon={<LockKeyhole size={17} />} label="Validation" value="Legacy unvalidated" warning />
          </div>
          <div className="model-hash"><span>Artefact digest</span><code>{status.model.sha256}</code></div>
          <div className="model-links">
            <a href={status.model.source_repository} target="_blank" rel="noreferrer">Upstream source <ExternalLink size={13} /></a>
            <a href={status.model.training_dataset} target="_blank" rel="noreferrer">Training dataset <ExternalLink size={13} /></a>
            <a href="https://github.com/krsidhantaryan-ux/SIH-2026/blob/arena/01a02f8d-sih-2026/models/MODEL_CARD.md" target="_blank" rel="noreferrer">Model card <ExternalLink size={13} /></a>
          </div>
        </article>

        <article className="panel dataset-card">
          <header className="panel-header"><div><h2>Active Storm Dataset</h2><p>Committed metadata, multi-satellite fixes, and verified imagery</p></div><Database size={19} /></header>
          <div className="dataset-number"><strong>{status.dataset.source_row_count}</strong><span>source fixes</span></div>
          <div className="dataset-stats">
            <div><strong>{status.dataset.observation_count}</strong><span>unique valid times</span></div>
            <div><strong>{status.dataset.storm_count}</strong><span>NIO benchmark storms</span></div>
            <div><strong>{status.dataset.satellites.length}</strong><span>satellites</span></div>
          </div>
          <div className="satellite-list">{status.dataset.satellites.map((satellite) => <span key={satellite}><Satellite size={12} />{satellite}</span>)}</div>
          <p className="dataset-note"><CircleAlert size={14} /> Multi-storm index loaded with Phailin, Hudhud, Vardah, Fani, Amphan, Tauktae, and Biparjoy.</p>
        </article>
      </section>

      <section className="panel replacement-panel">
        <header className="panel-header"><div><h2>How the model improves later</h2><p>The UI and API stay stable while the scientific model evolves</p></div><span className="panel-chip"><RefreshCw size={12} /> Manifest-driven</span></header>
        <div className="replacement-flow">
          <FlowStep icon={<CloudCog size={21} />} number="01" title="Ingest better data" detail="Kaggle now; storm-grouped HURSAT/INSAT later" />
          <ArrowRight className="flow-arrow" size={19} />
          <FlowStep icon={<Sparkles size={21} />} number="02" title="Train & validate" detail="Storm-disjoint splits, RMSE, MAE and category F1" />
          <ArrowRight className="flow-arrow" size={19} />
          <FlowStep icon={<FileCheck2 size={21} />} number="03" title="Export ONNX" detail="One scalar Vmax contract plus model card" />
          <ArrowRight className="flow-arrow" size={19} />
          <FlowStep icon={<GitBranch size={21} />} number="04" title="Change manifest" detail="Pin artefact, checksum and preprocessing" />
          <ArrowRight className="flow-arrow" size={19} />
          <FlowStep icon={<ShieldCheck size={21} />} number="05" title="Promote safely" detail="Golden tests, shadow mode and instant rollback" />
        </div>
        <div className="contract-callout">
          <div><strong>Stable contract</strong><code>image → vmax_kt → category policy → API response</code></div>
          <p>The active model is selected through <code>models/active-model.json</code>. Replacing it does not require rebuilding this interface.</p>
        </div>
      </section>

      <section className="governance-grid">
        <article className="panel"><div className="governance-icon blue"><ShieldCheck size={21} /></div><h3>What we can claim</h3><ul><li>Real ONNX inference executes on uploaded images</li><li>Model and data provenance are visible</li><li>Historical forecasts use past data only</li><li>Model artefacts are checksum verified</li></ul></article>
        <article className="panel"><div className="governance-icon amber"><CircleAlert size={21} /></div><h3>What we cannot claim yet</h3><ul><li>Operational or official forecast accuracy</li><li>Held-out performance for the legacy CNN</li><li>Calibrated uncertainty or RI probability</li><li>Generalisation across sensors and storms</li></ul></article>
        <article className="panel"><div className="governance-icon purple"><GitBranch size={21} /></div><h3>Next scientific gate</h3><ul><li>Acquire labelled multi-storm imagery</li><li>Remove duplicates and group by cyclone</li><li>Benchmark against persistence</li><li>Publish model card and slice metrics</li></ul></article>
      </section>
    </div>
  );
}

function Spec({ icon, label, value, warning = false }: { icon: React.ReactNode; label: string; value: string; warning?: boolean }) {
  return <div className="model-spec"><span>{icon}</span><div><small>{label}</small><strong className={warning ? "warning-text" : ""}>{value}</strong></div></div>;
}

function FlowStep({ icon, number, title, detail }: { icon: React.ReactNode; number: string; title: string; detail: string }) {
  return <div className="flow-step"><div>{icon}<span>{number}</span></div><strong>{title}</strong><p>{detail}</p></div>;
}
