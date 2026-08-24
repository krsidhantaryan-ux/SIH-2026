import {
  Activity,
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  Eye,
  FileText,
  Gauge,
  MapPin,
  Pause,
  Play,
  Radio,
  Satellite,
  ShieldAlert,
  Wind,
} from "lucide-react";
import { useMemo, useState } from "react";
import { transitionAlert } from "../api";
import IntensityChart from "../components/IntensityChart";
import TrackMap from "../components/TrackMap";
import type { Alert, Storm, TrackPoint } from "../types";
import { formatUtc, percent, signed } from "../utils";

interface Props {
  storm: Storm;
  selectedIndex: number;
  setSelectedIndex: (index: number) => void;
  playing: boolean;
  setPlaying: (playing: boolean) => void;
  onOpenAnalysis: () => void;
  onStormUpdated: (storm: Storm) => void;
}

export default function Overview({
  storm,
  selectedIndex,
  setSelectedIndex,
  playing,
  setPlaying,
  onOpenAnalysis,
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
          <div className="eyebrow"><Radio size={13} /> North Indian Ocean · Historical replay</div>
          <div className="heading-row">
            <h1>Cyclone {titleCase(storm.name)}</h1>
            <span className="storm-tag">{point.category.code}</span>
            <span className="quality-tag"><Check size={12} /> source valid</span>
          </div>
          <p>
            {storm.sid} · selected analysis valid <strong>{formatUtc(point.valid_time, true)}</strong>
          </p>
        </div>
        <div className="heading-actions">
          <a
            className="button secondary"
            href={`/api/v1/reports/${encodeURIComponent(storm.storm_id)}?valid_time=${encodeURIComponent(point.valid_time)}`}
            target="_blank"
            rel="noreferrer"
          >
            <FileText size={16} /> Generate report
          </a>
          <button className="button primary" onClick={onOpenAnalysis}>
            Analyse an image <ArrowUpRight size={16} />
          </button>
        </div>
      </section>

      <section className="mode-notice" aria-label="Historical demonstration notice">
        <ShieldAlert size={17} />
        <div>
          <strong>Historical demonstration</strong>
          <span>Machine guidance for workflow evaluation — not an official forecast or public warning.</span>
        </div>
        <span className="notice-source"><Satellite size={14} /> HURSAT-B1 + IBTrACS</span>
      </section>

      <section className="kpi-grid">
        <KpiCard
          icon={<Wind size={19} />}
          label="Best-track reference"
          value={`${point.vmax_kt.toFixed(0)} kt`}
          detail={point.category.name}
          tone="blue"
          badge="Reference"
        />
        <KpiCard
          icon={<Activity size={19} />}
          label="12-hour change"
          value={signed(point.change_12h_kt, " kt")}
          detail={`${signed(point.trend_kt_per_hour, " kt/h")} recent slope`}
          tone={point.change_12h_kt && point.change_12h_kt > 0 ? "amber" : "cyan"}
          badge="Past only"
        />
        <KpiCard
          icon={<Gauge size={19} />}
          label="RI trend indicator"
          value={percent(point.ri.probability)}
          detail={`Alert threshold ${percent(point.ri.threshold)}`}
          tone={point.ri.alert_eligible ? "rose" : "green"}
          badge="Rule baseline"
        />
        <KpiCard
          icon={<MapPin size={19} />}
          label="Storm motion"
          value={`${point.motion.speed_kmh.toFixed(1)} km/h`}
          detail={`${point.motion.direction} · ${point.motion.bearing_degrees.toFixed(0)}° bearing`}
          tone="purple"
          badge="3 h vector"
        />
      </section>

      <section className="primary-grid">
        <article className="panel map-panel">
          <PanelHeader
            title="Track intelligence"
            subtitle="Click any marker to inspect its valid-time analysis"
            action={<span className="panel-chip"><MapPin size={12} /> Bay of Bengal</span>}
          />
          <TrackMap track={storm.track} selectedIndex={selectedIndex} onSelect={setSelectedIndex} />
          <div className="map-footer">
            <Legend color="#38bdf8" label="Depression" />
            <Legend color="#facc15" label="Cyclonic storm" />
            <Legend color="#fb7185" label="Extreme" />
            <Legend color="#c084fc" label="Super cyclone" />
          </div>
        </article>

        <article className="panel imagery-panel">
          <PanelHeader
            title="Satellite evidence"
            subtitle={keyframe.source}
            action={<span className="panel-chip"><Eye size={12} /> IR window</span>}
          />
          <div className="satellite-frame">
            <img src={keyframe.url} alt={`${keyframe.label} satellite view of Cyclone Phailin`} />
            <div className="scan-line" />
            <div className="image-crosshair" aria-hidden="true"><i /><i /></div>
            <span className="image-label top-left">{keyframe.label}</span>
            <span className="image-label top-right">{formatUtc(keyframe.valid_time)}</span>
            <div className="image-readout">
              <div><span>Nearest keyframe</span><strong>{keyframe.embedded_wind_kt} kt</strong></div>
              <div><span>Selected reference</span><strong>{point.vmax_kt.toFixed(0)} kt</strong></div>
              <div><span>Sources at time</span><strong>{point.source_count}</strong></div>
            </div>
          </div>
          <div className="imagery-footnote">
            <CircleAlert size={14} /> Keyframe time may differ from the selected track time. Both timestamps remain visible.
          </div>
        </article>
      </section>

      <section className="secondary-grid">
        <article className="panel chart-panel">
          <PanelHeader
            title="Intensity evolution"
            subtitle="Reference history and the selected past-only trend forecast"
            action={
              <div className="chart-legend">
                <Legend color="#38bdf8" label="Reference" />
                <Legend color="#fbbf24" label="Guidance" dashed />
              </div>
            }
          />
          <IntensityChart track={storm.track} selectedIndex={selectedIndex} />
        </article>

        <article className={`panel alert-panel ${point.ri.alert_eligible ? "is-alert" : ""}`}>
          <PanelHeader
            title="Rapid intensification"
            subtitle={point.ri.method}
            action={<span className={`severity ${point.ri.alert_eligible ? "high" : "normal"}`}>
              {point.ri.alert_eligible ? "Review" : "Below threshold"}
            </span>}
          />
          <div className="ri-meter">
            <div className="ri-ring" style={{ "--score": `${point.ri.probability * 360}deg` } as React.CSSProperties}>
              <div><strong>{percent(point.ri.probability)}</strong><span>indicator</span></div>
            </div>
            <div className="ri-copy">
              <strong>{point.ri.definition}</strong>
              <p>
                Derived only from observations available at this selected time. It is a transparent trend rule,
                not the image intensity CNN.
              </p>
              <div className="threshold-bar">
                <span style={{ width: `${point.ri.probability * 100}%` }} />
                <i style={{ left: `${point.ri.threshold * 100}%` }} />
              </div>
              <div className="threshold-labels"><span>0%</span><span>65% alert</span><span>100%</span></div>
            </div>
          </div>
          {activeAlert ? (
            <div className="alert-action-row">
              <div>
                <ShieldAlert size={16} />
                <span><strong>{activeAlert.status === "open" ? "Unreviewed signal" : titleCase(activeAlert.status)}</strong>
                  <small>{formatUtc(activeAlert.valid_time)}</small></span>
              </div>
              {activeAlert.status === "open" && (
                <button disabled={transitioning} onClick={() => void acknowledge(activeAlert)}>
                  {transitioning ? "Saving…" : "Acknowledge"} <ChevronRight size={15} />
                </button>
              )}
            </div>
          ) : (
            <div className="quiet-state"><Check size={15} /> No alert generated at this valid time</div>
          )}
        </article>
      </section>

      <section className="panel forecast-panel">
        <PanelHeader
          title="Short-range intensity guidance"
          subtitle={`Issued from selected base time ${formatUtc(point.valid_time)}`}
          action={<span className="panel-chip"><Clock3 size={12} /> Past-only baseline</span>}
        />
        <div className="forecast-grid">
          {point.forecasts.map((forecast) => (
            <div className="forecast-card" key={forecast.horizon_hours}>
              <div className="forecast-horizon"><span>+{forecast.horizon_hours}</span> hours</div>
              <strong>{forecast.vmax_kt.toFixed(0)} <small>kt</small></strong>
              <div className={forecast.change_kt >= 0 ? "trend up" : "trend down"}>
                {signed(forecast.change_kt, " kt")}
              </div>
              <p>Indicative band {forecast.lower_kt.toFixed(0)}–{forecast.upper_kt.toFixed(0)} kt</p>
              <div className="forecast-compare">
                <span>Historical reference</span>
                <b>{forecast.historical_reference_kt !== null ? `${forecast.historical_reference_kt.toFixed(0)} kt` : "Unavailable"}</b>
              </div>
              <time>{formatUtc(forecast.valid_time)}</time>
            </div>
          ))}
          <div className="forecast-method">
            <div className="method-icon"><Activity size={22} /></div>
            <strong>Interpretable before complex</strong>
            <p>Five-point linear trend with horizon damping, compared against persistence and archived truth.</p>
            <span>No future observation enters the forecast calculation.</span>
          </div>
        </div>
      </section>

      <section className="replay-dock" aria-label="Historical replay controls">
        <button className="play-button" onClick={() => setPlaying(!playing)} aria-label={playing ? "Pause replay" : "Play replay"}>
          {playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
        </button>
        <div className="replay-copy">
          <span>{playing ? "Replaying lifecycle" : "Historical timeline"}</span>
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
