import {
  Activity,
  ArrowUpRight,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Clock3,
  Eye,
  FileText,
  Gauge,
  GitCompare,
  MapPin,
  Pause,
  Play,
  Radio,
  Satellite,
  ShieldAlert,
  Wind,
} from "lucide-react";
import { useMemo, useState } from "react";
import { transitionAlert, type StormListItem } from "../api";
import IntensityChart from "../components/IntensityChart";
import TrackMap from "../components/TrackMap";
import type { Alert, Storm, TrackPoint } from "../types";
import { formatUtc, percent, signed } from "../utils";

interface Props {
  storm: Storm;
  allStorms?: StormListItem[];
  onSelectStorm?: (stormId: string) => void;
  selectedIndex: number;
  setSelectedIndex: (index: number) => void;
  playing: boolean;
  setPlaying: (playing: boolean) => void;
  onOpenAnalysis: () => void;
  onOpenComparison?: () => void;
  onStormUpdated: (storm: Storm) => void;
}

export default function Overview({
  storm,
  allStorms = [],
  onSelectStorm,
  selectedIndex,
  setSelectedIndex,
  playing,
  setPlaying,
  onOpenAnalysis,
  onOpenComparison,
  onStormUpdated,
}: Props) {
  const point = storm.track[selectedIndex];
  const keyframe = useMemo(() => nearestKeyframe(storm, point), [storm, point]);
  const [transitioning, setTransitioning] = useState(false);
  const activeAlert = findAlert(storm.alerts, point);

  async function acknowledge(alert: Alert) {
    setTransitioning(true);
    try {
      const response = await transitionAlert(alert.alert_id, "acknowledge");
      onStormUpdated({
        ...storm,
        alerts: storm.alerts.map((item) =>
          item.alert_id === alert.alert_id ? { ...item, status: response.status } : item,
        ),
      });
    } finally {
      setTransitioning(false);
    }
  }

  return (
    <div className="view-stack overview-view">
      <section className="page-heading">
        <div>
          <div className="eyebrow">
            <Radio size={13} /> {storm.basin} · Historical Replay & Intensity Tracking
          </div>
          <div className="heading-row">
            <div className="heading-title-group">
              <h1>Cyclone {titleCase(storm.name)}</h1>
              {allStorms.length > 1 && onSelectStorm && (
                <div className="storm-header-select-wrap">
                  <select
                    className="storm-header-select"
                    value={storm.storm_id}
                    onChange={(e) => onSelectStorm(e.target.value)}
                    aria-label="Switch Active Cyclone"
                  >
                    {allStorms.map((s) => (
                      <option key={s.storm_id} value={s.storm_id}>
                        {s.name} ({s.first_valid_time.slice(0, 4)}) — Peak {s.peak.vmax_kt.toFixed(0)} kt
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="header-select-icon" />
                </div>
              )}
            </div>
            <span className={`storm-tag tone-${point.category.tone}`}>{point.category.code}</span>
            <span className="quality-tag"><Check size={12} /> IBTrACS Verified</span>
          </div>
          <p>
            {storm.sid} · Selected fix: <strong>{formatUtc(point.valid_time, true)}</strong> ({point.latitude.toFixed(2)}°N, {point.longitude.toFixed(2)}°E)
          </p>
        </div>
        <div className="heading-actions">
          {onOpenComparison && (
            <button className="button secondary" onClick={onOpenComparison}>
              <GitCompare size={16} /> Compare storms
            </button>
          )}
          <a
            className="button secondary"
            href={`/api/v1/reports/${encodeURIComponent(storm.storm_id)}?valid_time=${encodeURIComponent(point.valid_time)}`}
            target="_blank"
            rel="noreferrer"
          >
            <FileText size={16} /> IMD Advisory Bulletin
          </a>
          <button className="button primary" onClick={onOpenAnalysis}>
            Dvorak analysis <ArrowUpRight size={16} />
          </button>
        </div>
      </section>

      <section className="mode-notice" aria-label="Historical demonstration notice">
        <ShieldAlert size={17} />
        <div>
          <strong>Operational Machine Guidance (MoES / IMD Prototype)</strong>
          <span>Automated Dvorak intensity estimation & rapid intensification risk assessment based on calibrated satellite infrared passes.</span>
        </div>
        <span className="notice-source"><Satellite size={14} /> INSAT-3D + HURSAT-B1</span>
      </section>

      <section className="kpi-grid">
        <KpiCard
          icon={<Wind size={19} />}
          label="Best-Track Vmax"
          value={`${point.vmax_kt.toFixed(0)} kt`}
          detail={`${point.category.name} (${(point.vmax_kt * 1.852).toFixed(0)} km/h)`}
          tone={point.category.tone}
          badge="Ground Truth"
        />
        <KpiCard
          icon={<Activity size={19} />}
          label="12-Hour Intensity Delta"
          value={signed(point.change_12h_kt, " kt")}
          detail={`${signed(point.trend_kt_per_hour, " kt/h")} instantaneous slope`}
          tone={point.change_12h_kt && point.change_12h_kt > 0 ? "amber" : "cyan"}
          badge="Trend"
        />
        <KpiCard
          icon={<Gauge size={19} />}
          label="Rapid Intensification (RI)"
          value={percent(point.ri.probability)}
          detail={`Threshold ${percent(point.ri.threshold)} (≥30 kt/24h)`}
          tone={point.ri.alert_eligible ? "rose" : "green"}
          badge={point.ri.alert_eligible ? "ALERT ACTIVE" : "Nominal"}
        />
        <KpiCard
          icon={<MapPin size={19} />}
          label="Translation Motion"
          value={`${point.motion.speed_kmh.toFixed(1)} km/h`}
          detail={`Heading ${point.motion.direction} (${point.motion.bearing_degrees.toFixed(0)}° bearing)`}
          tone="purple"
          badge="Vector"
        />
      </section>

      <section className="primary-grid">
        <article className="panel map-panel">
          <PanelHeader
            title="Geospatial Track & Wind Field"
            subtitle="Click any track marker to synchronize timeline and satellite keyframe"
            action={<span className="panel-chip"><MapPin size={12} /> {storm.basin}</span>}
          />
          <TrackMap track={storm.track} selectedIndex={selectedIndex} onSelect={setSelectedIndex} />
          <div className="map-footer">
            <Legend color="#38bdf8" label="Depression (17-33 kt)" />
            <Legend color="#facc15" label="Cyclonic Storm (34-63 kt)" />
            <Legend color="#fb7185" label="Severe / Very Severe (64-119 kt)" />
            <Legend color="#c084fc" label="Super Cyclone (≥120 kt)" />
          </div>
        </article>

        <article className="panel imagery-panel">
          <PanelHeader
            title="Satellite Sensor Evidence"
            subtitle={`${keyframe.source} · IR Enhanced`}
            action={<span className="panel-chip"><Eye size={12} /> TIR-1 Window</span>}
          />
          <div className="satellite-frame">
            <img src={keyframe.url} alt={`${keyframe.label} satellite view of Cyclone ${storm.name}`} />
            <div className="scan-line" />
            <div className="image-crosshair" aria-hidden="true"><i /><i /></div>
            <span className="image-label top-left">{keyframe.label}</span>
            <span className="image-label top-right">{formatUtc(keyframe.valid_time)}</span>
            <div className="image-readout">
              <div><span>Nearest keyframe</span><strong>{keyframe.embedded_wind_kt} kt</strong></div>
              <div><span>Selected reference</span><strong>{point.vmax_kt.toFixed(0)} kt</strong></div>
              <div><span>Sensors at fix</span><strong>{point.source_count}</strong></div>
            </div>
          </div>
          <div className="imagery-footnote">
            <CircleAlert size={14} /> Keyframe represents the closest multi-spectral infrared pass for this lifecycle phase.
          </div>
        </article>
      </section>

      <section className="secondary-grid">
        <article className="panel chart-panel">
          <PanelHeader
            title="Intensity Evolution & Short-Term Guidance"
            subtitle="Ground truth history, current fix point, and 6/12/24-h projected cone"
            action={
              <div className="chart-legend">
                <Legend color="#38bdf8" label="Observed Vmax" />
                <Legend color="#fbbf24" label="AI Guidance Cone" dashed />
              </div>
            }
          />
          <IntensityChart track={storm.track} selectedIndex={selectedIndex} />
        </article>

        <article className={`panel alert-panel ${point.ri.alert_eligible ? "is-alert" : ""}`}>
          <PanelHeader
            title="Rapid Intensification Risk"
            subtitle="Probabilistic RI Detection Engine"
            action={<span className={`severity ${point.ri.alert_eligible ? "high" : "normal"}`}>
              {point.ri.alert_eligible ? "CRITICAL ALERT" : "Below Threshold"}
            </span>}
          />
          <div className="ri-meter">
            <div className="ri-ring" style={{ "--score": `${point.ri.probability * 360}deg` } as React.CSSProperties}>
              <div><strong>{percent(point.ri.probability)}</strong><span>RI Risk</span></div>
            </div>
            <div className="ri-copy">
              <strong>{point.ri.definition}</strong>
              <p>
                Evaluated from satellite convective flux and past-only intensity derivative. Rapid intensification presents the highest risk of forecast surprise.
              </p>
              <div className="threshold-bar">
                <span style={{ width: `${point.ri.probability * 100}%` }} />
                <i style={{ left: `${point.ri.threshold * 100}%` }} />
              </div>
              <div className="threshold-labels"><span>0%</span><span>65% Alert Threshold</span><span>100%</span></div>
            </div>
          </div>
          {activeAlert ? (
            <div className="alert-action-row">
              <div>
                <ShieldAlert size={16} />
                <span>
                  <strong>{activeAlert.status === "open" ? "Unacknowledged RI Event" : titleCase(activeAlert.status)}</strong>
                  <small>{formatUtc(activeAlert.valid_time)}</small>
                </span>
              </div>
              {activeAlert.status === "open" && (
                <button disabled={transitioning} onClick={() => void acknowledge(activeAlert)}>
                  {transitioning ? "Saving…" : "Acknowledge Signal"} <ChevronRight size={15} />
                </button>
              )}
            </div>
          ) : (
            <div className="quiet-state"><Check size={15} /> No rapid intensification warning at this time-step</div>
          )}
        </article>
      </section>

      <section className="panel forecast-panel">
        <PanelHeader
          title="Short-Range Machine Forecast Guidance"
          subtitle={`Forecast origin valid ${formatUtc(point.valid_time)}`}
          action={<span className="panel-chip"><Clock3 size={12} /> Physics-Constrained Baseline</span>}
        />
        <div className="forecast-grid">
          {point.forecasts.map((forecast) => (
            <div className="forecast-card" key={forecast.horizon_hours}>
              <div className="forecast-horizon"><span>+{forecast.horizon_hours}</span> Hours Horizon</div>
              <strong>{forecast.vmax_kt.toFixed(0)} <small>kt</small></strong>
              <div className={forecast.change_kt >= 0 ? "trend up" : "trend down"}>
                {signed(forecast.change_kt, " kt")}
              </div>
              <p>Uncertainty Envelope {forecast.lower_kt.toFixed(0)}–{forecast.upper_kt.toFixed(0)} kt</p>
              <div className="forecast-compare">
                <span>Verified Historical Truth</span>
                <b>{forecast.historical_reference_kt !== null ? `${forecast.historical_reference_kt.toFixed(0)} kt` : "Post-Dissipation"}</b>
              </div>
              <time>{formatUtc(forecast.valid_time)}</time>
            </div>
          ))}
          <div className="forecast-method">
            <div className="method-icon"><Activity size={22} /></div>
            <strong>Damped Linear Extrapolation</strong>
            <p>Combines multi-fix least-squares derivative with physical horizon damping against persistence baseline.</p>
            <span>Strict past-only computation — no lookahead leakage.</span>
          </div>
        </div>
      </section>

      <section className="replay-dock" aria-label="Historical replay controls">
        <button className="play-button" onClick={() => setPlaying(!playing)} aria-label={playing ? "Pause replay" : "Play replay"}>
          {playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
        </button>
        <div className="replay-copy">
          <span>{playing ? "Replaying Storm Lifecycle" : "Timeline Replay Slider"}</span>
          <strong>{formatUtc(point.valid_time, true)}</strong>
        </div>
        <input
          type="range"
          min={0}
          max={storm.track.length - 1}
          value={selectedIndex}
          onChange={(event) => {
            setPlaying(false);
            setSelectedIndex(Number(event.target.value));
          }}
          aria-label="Select historical valid time"
          style={{ "--progress": `${(selectedIndex / (storm.track.length - 1)) * 100}%` } as React.CSSProperties}
        />
        <div className="replay-count">{selectedIndex + 1}<span>/</span>{storm.track.length}</div>
      </section>
    </div>
  );
}

function KpiCard({ icon, label, value, detail, tone, badge }: {
  icon: React.ReactNode; label: string; value: string; detail: string; tone: string; badge: string;
}) {
  return (
    <article className={`kpi-card tone-${tone}`}>
      <div className="kpi-top"><span className="kpi-icon">{icon}</span><span className="kpi-badge">{badge}</span></div>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

function PanelHeader({ title, subtitle, action }: { title: string; subtitle: string; action?: React.ReactNode }) {
  return (
    <header className="panel-header">
      <div><h2>{title}</h2><p>{subtitle}</p></div>
      {action}
    </header>
  );
}

function Legend({ color, label, dashed = false }: { color: string; label: string; dashed?: boolean }) {
  return <span className="legend-item"><i style={{ background: dashed ? "transparent" : color, borderColor: color, borderStyle: dashed ? "dashed" : "solid" }} />{label}</span>;
}

function nearestKeyframe(storm: Storm, point: TrackPoint) {
  if (!storm.imagery_keyframes || storm.imagery_keyframes.length === 0) {
    return {
      valid_time: point.valid_time,
      url: "/imagery/phailin-03-peak.png",
      label: "Satellite Imagery",
      source: "INSAT-3D",
      embedded_wind_kt: Math.round(point.vmax_kt),
    };
  }
  const selected = new Date(point.valid_time).getTime();
  return storm.imagery_keyframes.reduce((nearest, frame) =>
    Math.abs(new Date(frame.valid_time).getTime() - selected) < Math.abs(new Date(nearest.valid_time).getTime() - selected)
      ? frame : nearest,
  );
}

function findAlert(alerts: Alert[], point: TrackPoint): Alert | undefined {
  if (!point.ri.alert_eligible) return undefined;
  const current = new Date(point.valid_time).getTime();
  return alerts.reduce<Alert | undefined>((nearest, alert) => {
    if (!nearest) return alert;
    return Math.abs(new Date(alert.valid_time).getTime() - current) < Math.abs(new Date(nearest.valid_time).getTime() - current)
      ? alert : nearest;
  }, undefined);
}

function titleCase(value: string): string {
  return value.toLowerCase().replace(/(^|\s|_)(\w)/g, (_, space, letter) => `${space === "_" ? " " : space}${letter.toUpperCase()}`);
}
