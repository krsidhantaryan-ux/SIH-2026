import {
  AlertTriangle,
  ArrowRight,
  Check,
  Cpu,
  FileImage,
  FlaskConical,
  ImagePlus,
  Info,
  LoaderCircle,
  RefreshCw,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  Wind,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { uploadAnalysis } from "../api";
import type { SystemStatus, UploadResult } from "../types";
import { bytes } from "../utils";

interface Props {
  status: SystemStatus;
}

export default function AnalysisLab({ status }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function choose(next: File | undefined) {
    if (!next) return;
    setFile(next);
    setResult(null);
    setError(null);
  }

  async function loadSample() {
    setError(null);
    try {
      const response = await fetch("/imagery/insat3d-demo-sample.jpg");
      const blob = await response.blob();
      choose(new File([blob], "insat3d-demo-sample.jpg", { type: blob.type || "image/jpeg" }));
    } catch {
      setError("Could not load the bundled demonstration image.");
    }
  }

  async function analyse() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await uploadAnalysis(file));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setFile(null);
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className="view-stack analysis-view">
      <section className="page-heading">
        <div>
          <div className="eyebrow"><FlaskConical size={13} /> Analysis laboratory · Legacy CNN</div>
          <div className="heading-row"><h1>INSAT-3D intensity analysis</h1><span className="storm-tag lab">Demo</span></div>
          <p>Upload one storm-centred IR image to exercise the real ONNX inference pipeline.</p>
        </div>
        <div className="model-ready-chip">
          <span className={status.model.status === "ready" ? "status-dot ready" : "status-dot unavailable"} />
          <div><strong>{status.model.status === "ready" ? "Model ready" : "Model unavailable"}</strong><span>ONNX Runtime · CPU</span></div>
        </div>
      </section>

      <section className="mode-notice caution">
        <AlertTriangle size={17} />
        <div><strong>Legacy, independently unvalidated model</strong><span>Useful for demonstrating replaceable inference—not for operational accuracy claims.</span></div>
        <a href="https://github.com/cycloneintensity/CrossKnotHacks-Cyclonet" target="_blank" rel="noreferrer">View source <ArrowRight size={14} /></a>
      </section>

      <section className="lab-grid">
        <article className="panel upload-panel">
          <header className="panel-header">
            <div><h2>1 · Select satellite image</h2><p>PNG, JPEG or WebP · maximum 10 MB · minimum 64 × 64</p></div>
            {file && <button className="icon-button" onClick={reset} aria-label="Clear selected image"><X size={17} /></button>}
          </header>

          {!file ? (
            <div
              className={`drop-zone ${dragging ? "dragging" : ""}`}
              onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                choose(event.dataTransfer.files[0]);
              }}
            >
              <div className="drop-icon"><UploadCloud size={30} /></div>
              <h3>Drop a storm-centred image here</h3>
              <p>Use an INSAT-3D-style infrared image for the most meaningful demonstration.</p>
              <div className="drop-actions">
                <button className="button primary" onClick={() => inputRef.current?.click()}><ImagePlus size={16} /> Browse image</button>
                <button className="button secondary" onClick={() => void loadSample()}><Sparkles size={16} /> Use Phailin sample</button>
              </div>
              <input
                ref={inputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                hidden
                onChange={(event) => choose(event.target.files?.[0])}
              />
            </div>
          ) : (
            <div className="selected-image">
              <div className="selected-preview">
                {preview && <img src={preview} alt="Selected cyclone input preview" />}
                <div className="preview-grid" />
                <span><ScanSearch size={14} /> Input preview</span>
              </div>
              <div className="file-meta">
                <div className="file-icon"><FileImage size={22} /></div>
                <div><strong>{file.name}</strong><span>{bytes(file.size)} · {file.type || "image"}</span></div>
                <Check size={18} className="success-icon" />
              </div>
              <button className="analyse-button" disabled={busy || status.model.status !== "ready"} onClick={() => void analyse()}>
                {busy ? <><LoaderCircle size={19} className="spin" /> Running inference…</> : <><Cpu size={19} /> Run intensity model <ArrowRight size={18} /></>}
              </button>
            </div>
          )}
          {error && <div className="inline-error"><AlertTriangle size={16} /><span>{error}</span><button onClick={() => setError(null)}>Dismiss</button></div>}
        </article>

        <article className="panel pipeline-panel">
          <header className="panel-header"><div><h2>Inference pipeline</h2><p>Every transformation is explicit and replaceable</p></div></header>
          <div className="pipeline-list">
            <PipelineStep number="01" icon={<ShieldCheck size={18} />} title="Validate input" detail="Media signature, dimensions and 10 MB bound" state={file ? "done" : "waiting"} />
            <PipelineStep number="02" icon={<ScanSearch size={18} />} title="Preprocess" detail="Centre-fit to 250 × 250 · legacy BGR / [0,1]" state={busy || result ? "done" : file ? "ready" : "waiting"} />
            <PipelineStep number="03" icon={<Cpu size={18} />} title="ONNX inference" detail="CNN regression to one Vmax value in knots" state={result ? "done" : busy ? "active" : "waiting"} />
            <PipelineStep number="04" icon={<Wind size={18} />} title="Policy mapping" detail="Continuous wind → versioned demo IMD category" state={result ? "done" : "waiting"} />
          </div>
          <div className="pipeline-contract">
            <Info size={15} />
            <p><strong>Upgrade path built in.</strong> Swap the model artefact and JSON manifest while keeping the API response stable.</p>
          </div>
        </article>
      </section>

      {result ? (
        <section className="result-section" aria-live="polite">
          <div className="result-heading">
            <div><span className="result-kicker"><Check size={13} /> Inference complete</span><h2>Intensity analysis result</h2><p>{result.filename} · {result.dimensions.width} × {result.dimensions.height}</p></div>
            <button className="button secondary" onClick={reset}><RefreshCw size={15} /> Analyse another</button>
          </div>
          <div className="result-grid">
            <article className="result-hero">
              <div className="result-glow" />
              <span>Estimated maximum sustained wind</span>
              <strong>{result.result.vmax_kt.toFixed(1)}<small> kt</small></strong>
              <div className="category-result">{result.result.category.name}<b>{result.result.category.code}</b></div>
              <p><AlertTriangle size={14} /> Confidence interval unavailable: this legacy checkpoint has no published calibration.</p>
            </article>
            <article className="result-pattern">
              <span>Structure interpretation</span>
              <h3>{result.result.pattern}</h3>
              <div className="metric-grid">
                {Object.entries(result.result.metrics).map(([name, value]) => (
                  <div key={name}><span>{prettyMetric(name)}</span><strong>{Math.round(value * 100)}%</strong><i><b style={{ width: `${value * 100}%` }} /></i></div>
                ))}
              </div>
            </article>
            <article className="result-provenance">
              <span>Model provenance</span>
              <h3>{result.result.method.id}</h3>
              <dl>
                <div><dt>Runtime</dt><dd>ONNX / CPU</dd></div>
                <div><dt>Validation</dt><dd className="warning-text">Legacy unvalidated</dd></div>
                <div><dt>Model replaceable</dt><dd>Yes · manifest driven</dd></div>
                <div><dt>Analysis ID</dt><dd>{result.analysis_id.slice(0, 24)}…</dd></div>
              </dl>
              <p>{result.disclaimer}</p>
            </article>
          </div>
        </section>
      ) : (
        <section className="empty-result panel">
          <div className="empty-orbit"><span /><span /><Cpu size={25} /></div>
          <div><h2>Results will appear here</h2><p>The server performs real model inference; no browser-generated or hard-coded prediction is used.</p></div>
        </section>
      )}
    </div>
  );
}

function PipelineStep({ number, icon, title, detail, state }: { number: string; icon: React.ReactNode; title: string; detail: string; state: string }) {
  return (
    <div className={`pipeline-step state-${state}`}>
      <span className="step-number">{number}</span><span className="step-icon">{icon}</span>
      <div><strong>{title}</strong><p>{detail}</p></div>
      <span className="step-state">{state === "done" ? <Check size={15} /> : state === "active" ? <LoaderCircle size={15} className="spin" /> : null}</span>
    </div>
  );
}

function prettyMetric(name: string): string {
  return name.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
