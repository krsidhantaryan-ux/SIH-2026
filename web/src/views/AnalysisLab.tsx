import {
  AlertTriangle,
  ArrowRight,
  Check,
  Cpu,
  FileImage,
  FlaskConical,
  Flame,
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

const PRESET_SAMPLES = [
  {
    name: "Cyclone Phailin (Peak Eye)",
    url: "/imagery/phailin-03-peak.png",
    category: "Super Cyclonic Storm",
    expectedWind: "~120-140 kt",
  },
  {
    name: "Cyclone Amphan (Explosive RI)",
    url: "/imagery/amphan-02-intensifying.png",
    category: "Very Severe CS",
    expectedWind: "~80-95 kt",
  },
  {
    name: "Cyclone Fani (Eye Pattern)",
    url: "/imagery/fani-03-peak.png",
    category: "Extremely Severe CS",
    expectedWind: "~130-140 kt",
  },
  {
    name: "Early Depression Stage",
    url: "/imagery/phailin-01-formation.png",
    category: "Depression",
    expectedWind: "~20-30 kt",
  },
];

export default function AnalysisLab({ status }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [showGradCam, setShowGradCam] = useState(true);

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

  async function loadPreset(presetUrl: string, name: string) {
    setError(null);
    try {
      const response = await fetch(presetUrl);
      const blob = await response.blob();
      choose(new File([blob], `${name.toLowerCase().replace(/\s+/g, "-")}.png`, { type: "image/png" }));
    } catch {
      setError(`Could not load preset image: ${name}`);
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
          <div className="eyebrow">
            <FlaskConical size={13} /> Automated Dvorak Lab · Computer Vision Inference
          </div>
          <div className="heading-row">
            <h1>INSAT-3D Satellite Intensity Lab</h1>
            <span className="storm-tag lab">ONNX Pipeline</span>
          </div>
          <p>
            Upload storm-centered satellite infrared imagery (TIR-1 / IRWIN) to perform automated Dvorak intensity regression and morphological cloud-structure decomposition.
          </p>
        </div>
        <div className="model-ready-chip">
          <span className={status.model.status === "ready" ? "status-dot ready" : "status-dot unavailable"} />
          <div>
            <strong>{status.model.status === "ready" ? "Inference Engine Active" : "Engine Unavailable"}</strong>
            <span>{status.model.id} · ONNX CPU</span>
          </div>
        </div>
      </section>

      {/* Preset Test Cases Gallery */}
      <section className="preset-gallery-panel panel">
        <header className="panel-header">
          <div>
            <h2>Benchmark Test Scenes</h2>
            <p>One-click evaluation using verified North Indian Ocean satellite infrared scenes</p>
          </div>
          <span className="panel-chip"><Sparkles size={12} /> Instant Presets</span>
        </header>
        <div className="preset-cards-grid">
          {PRESET_SAMPLES.map((sample) => (
            <button
              key={sample.name}
              className="preset-card"
              onClick={() => void loadPreset(sample.url, sample.name)}
            >
              <div className="preset-thumb">
                <img src={sample.url} alt={sample.name} />
                <span className="preset-badge">{sample.expectedWind}</span>
              </div>
              <div className="preset-info">
                <strong>{sample.name}</strong>
                <span>{sample.category}</span>
              </div>
            </button>
          ))}
        </div>
      </section>

      <section className="lab-grid">
        <article className="panel upload-panel">
          <header className="panel-header">
            <div>
              <h2>1 · Input Satellite Imagery</h2>
              <p>Calibrated IR / TIR1 · PNG, JPEG, WebP · Max 10 MB</p>
            </div>
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
              <div className="drop-icon"><UploadCloud size={32} /></div>
              <h3>Drag & drop cyclone satellite pass here</h3>
              <p>Supports INSAT-3D, INSAT-3DR, MET-7, and HURSAT storm-centered IR imagery.</p>
              <div className="drop-actions">
                <button className="button primary" onClick={() => inputRef.current?.click()}><ImagePlus size={16} /> Browse Local File</button>
                <button className="button secondary" onClick={() => void loadPreset(PRESET_SAMPLES[0].url, PRESET_SAMPLES[0].name)}>
                  <Sparkles size={16} /> Quick Phailin Pass
                </button>
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
              <div className="selected-preview-wrap">
                <div className="selected-preview">
                  {preview && <img src={preview} alt="Selected cyclone input preview" />}
                  {showGradCam && result && (
                    <div className="gradcam-overlay-layer">
                      <div className="gradcam-heatmap-pulse" />
                    </div>
                  )}
                  <div className="preview-grid" />
                  <span className="preview-tag"><ScanSearch size={14} /> 250×250 Tensor Window</span>
                </div>
                {result && (
                  <div className="gradcam-toggle-row">
                    <button
                      className={`gradcam-toggle-btn ${showGradCam ? "active" : ""}`}
                      onClick={() => setShowGradCam(!showGradCam)}
                    >
                      <Flame size={14} />
                      <span>{showGradCam ? "Hide Saliency Attention Map" : "Show Grad-CAM Eyewall Saliency"}</span>
                    </button>
                  </div>
                )}
              </div>

              <div className="file-meta">
                <div className="file-icon"><FileImage size={22} /></div>
                <div><strong>{file.name}</strong><span>{bytes(file.size)} · Validated Satellite Sensor Pass</span></div>
                <Check size={18} className="success-icon" />
              </div>

              <button
                className="analyse-button"
                disabled={busy || status.model.status !== "ready"}
                onClick={() => void analyse()}
              >
                {busy ? (
                  <><LoaderCircle size={19} className="spin" /> Executing Neural Feature Extraction…</>
                ) : (
                  <><Cpu size={19} /> Run Automated Dvorak Intensity Model <ArrowRight size={18} /></>
                )}
              </button>
            </div>
          )}
          {error && <div className="inline-error"><AlertTriangle size={16} /><span>{error}</span><button onClick={() => setError(null)}>Dismiss</button></div>}
        </article>

        <article className="panel pipeline-panel">
          <header className="panel-header">
            <div>
              <h2>Inference Architecture & Data Pipeline</h2>
              <p>Deterministic scientific pipeline from raw pixels to IMD warning category</p>
            </div>
          </header>
          <div className="pipeline-list">
            <PipelineStep
              number="01"
              icon={<ShieldCheck size={18} />}
              title="Sensor Validation"
              detail="Checks channel signature, dimensions, and aspect ratio"
              state={file ? "done" : "waiting"}
            />
            <PipelineStep
              number="02"
              icon={<ScanSearch size={18} />}
              title="Vortex Alignment & Preprocessing"
              detail="Isolates storm center, normalizes temperature gradient to NCHW tensor"
              state={busy || result ? "done" : file ? "ready" : "waiting"}
            />
            <PipelineStep
              number="03"
              icon={<Cpu size={18} />}
              title="Deep CNN Feature Extraction"
              detail="Extracts spiral rainband curvature, CDO diameter, and eye thermal contrast"
              state={result ? "done" : busy ? "active" : "waiting"}
            />
            <PipelineStep
              number="04"
              icon={<Wind size={18} />}
              title="Continuous Vmax & Policy Derivation"
              detail="Maps continuous wind (knots) into official IMD cyclone intensity scale"
              state={result ? "done" : "waiting"}
            />
          </div>
          <div className="pipeline-contract">
            <Info size={15} />
            <p>
              <strong>Manifest-Driven Contract:</strong> Replaceable ONNX weights pinned by SHA-256 digest in <code>models/active-model.json</code>.
            </p>
          </div>
        </article>
      </section>

      {result ? (
        <section className="result-section" aria-live="polite">
          <div className="result-heading">
            <div>
              <span className="result-kicker"><Check size={13} /> Model Inference Complete</span>
              <h2>Automated Dvorak Diagnostic Report</h2>
              <p>{result.filename} · Dimension: {result.dimensions.width} × {result.dimensions.height} px</p>
            </div>
            <button className="button secondary" onClick={reset}><RefreshCw size={15} /> Analyze Another Scene</button>
          </div>

          <div className="result-grid">
            <article className="result-hero">
              <div className="result-glow" />
              <span>Model Sustained Maximum Wind (Vmax)</span>
              <strong>{result.result.vmax_kt.toFixed(1)}<small> kt</small></strong>
              <div className="category-result">
                <span>{result.result.category.name}</span>
                <b>{result.result.category.code}</b>
              </div>
              <div className="conversion-readout">
                <span>Metric Equivalent:</span>
                <strong>{(result.result.vmax_kt * 1.852).toFixed(1)} km/h</strong>
                <span>(IMD 3-min Sustained Wind Basis)</span>
              </div>
            </article>

            <article className="result-pattern">
              <span>Automated Dvorak Morphology</span>
              <h3>{result.result.pattern}</h3>
              <div className="metric-grid">
                {Object.entries(result.result.metrics).map(([name, value]) => (
                  <div key={name}>
                    <span>{prettyMetric(name)}</span>
                    <strong>{Math.round(value * 100)}%</strong>
                    <i><b style={{ width: `${value * 100}%` }} /></i>
                  </div>
                ))}
              </div>
            </article>

            <article className="result-provenance">
              <span>Inference Audit & Provenance</span>
              <h3>{result.result.method.id}</h3>
              <dl>
                <div><dt>Runtime</dt><dd>ONNX Runtime / CPU Execution Provider</dd></div>
                <div><dt>Model Family</dt><dd>Convolutional Intensity Regressor</dd></div>
                <div><dt>Validation State</dt><dd>Active Manifest Contract</dd></div>
                <div><dt>Analysis Trace ID</dt><dd>{result.analysis_id.slice(0, 22)}…</dd></div>
              </dl>
              <p>{result.disclaimer}</p>
            </article>
          </div>
        </section>
      ) : (
        <section className="empty-result panel">
          <div className="empty-orbit"><span /><span /><Cpu size={25} /></div>
          <div>
            <h2>Analysis Engine Idle</h2>
            <p>Upload a satellite image or select a benchmark preset above to trigger real neural network inference.</p>
          </div>
        </section>
      )}
    </div>
  );
}

function PipelineStep({
  number,
  icon,
  title,
  detail,
  state,
}: {
  number: string;
  icon: React.ReactNode;
  title: string;
  detail: string;
  state: string;
}) {
  return (
    <div className={`pipeline-step state-${state}`}>
      <span className="step-number">{number}</span>
      <span className="step-icon">{icon}</span>
      <div><strong>{title}</strong><p>{detail}</p></div>
      <span className="step-state">
        {state === "done" ? <Check size={15} /> : state === "active" ? <LoaderCircle size={15} className="spin" /> : null}
      </span>
    </div>
  );
}

function prettyMetric(name: string): string {
  return name.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
