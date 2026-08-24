import {
  ArrowRight,
  Layers,
} from "lucide-react";
import { useEffect, useState } from "react";
import { getStorm, type StormListItem } from "../api";
import type { Storm } from "../types";

interface Props {
  stormsList: StormListItem[];
  currentStorm: Storm;
  onSelectStorm: (stormId: string) => void;
}

export default function StormComparison({ stormsList, currentStorm, onSelectStorm }: Props) {
  const [selectedStormIds, setSelectedStormIds] = useState<string[]>([
    "2020137N10087", // Amphan
    "2019117N02086", // Fani
    "2013281N12098", // Phailin
  ]);
  const [loadedStorms, setLoadedStorms] = useState<Record<string, Storm>>({
    [currentStorm.storm_id]: currentStorm,
  });

  useEffect(() => {
    const toFetch = selectedStormIds.filter((id) => !loadedStorms[id]);
    if (toFetch.length === 0) return;

    Promise.all(toFetch.map((id) => getStorm(id)))
      .then((results) => {
        setLoadedStorms((prev) => {
          const next = { ...prev };
          results.forEach((s) => {
            next[s.storm_id] = s;
          });
          return next;
        });
      });
  }, [selectedStormIds, loadedStorms]);

  function toggleStorm(stormId: string) {
    if (selectedStormIds.includes(stormId)) {
      if (selectedStormIds.length <= 1) return; // Keep at least one
      setSelectedStormIds((prev) => prev.filter((id) => id !== stormId));
    } else {
      if (selectedStormIds.length >= 4) {
        setSelectedStormIds((prev) => [...prev.slice(1), stormId]);
      } else {
        setSelectedStormIds((prev) => [...prev, stormId]);
      }
    }
  }

  const activeStorms = selectedStormIds
    .map((id) => loadedStorms[id])
    .filter((s): s is Storm => Boolean(s));

  // Determine max lifecycle length in hours
  const maxHours = Math.max(
    ...activeStorms.map((s) => {
      if (!s.track.length) return 0;
      const start = new Date(s.track[0].valid_time).getTime();
      const end = new Date(s.track[s.track.length - 1].valid_time).getTime();
      return (end - start) / (1000 * 3600);
    }),
    120,
  );

  const colors = ["#38bdf8", "#f43f5e", "#a855f7", "#eab308"];

  return (
    <div className="view-stack comparison-view">
      <section className="page-heading">
        <div>
          <div className="eyebrow">
            <Layers size={13} /> North Indian Ocean · Multi-Cyclone Benchmarking
          </div>
          <div className="heading-row">
            <h1>Cyclone Lifecycle Comparison</h1>
            <span className="storm-tag">NIO Benchmark</span>
          </div>
          <p>
            Comparative analysis of intensity evolution, rapid intensification (RI) slopes, and wind field dynamics across North Indian Ocean cyclones.
          </p>
        </div>
      </section>

      {/* Storm Selector Pills */}
      <section className="comparison-selector-panel panel">
        <header className="panel-header">
          <div>
            <h2>Select Cyclones to Compare</h2>
            <p>Select up to 4 historic storms for superimposed lifecycle analysis</p>
          </div>
          <span className="panel-chip">
            {selectedStormIds.length} of 4 Active
          </span>
        </header>

        <div className="comparison-pills-grid">
          {stormsList.map((s) => {
            const isSelected = selectedStormIds.includes(s.storm_id);
            const activeIdx = selectedStormIds.indexOf(s.storm_id);
            const stormColor = isSelected ? colors[activeIdx % colors.length] : undefined;

            return (
              <button
                key={s.storm_id}
                className={`comparison-pill ${isSelected ? "selected" : ""}`}
                style={isSelected ? { borderColor: stormColor, boxShadow: `0 0 12px ${stormColor}33` } : {}}
                onClick={() => toggleStorm(s.storm_id)}
              >
                <div className="pill-header">
                  <span
                    className="color-dot"
                    style={{ background: isSelected ? stormColor : "#64748b" }}
                  />
                  <strong>Cyclone {s.name}</strong>
                  <small>{s.first_valid_time.slice(0, 4)}</small>
                </div>
                <div className="pill-body">
                  <span>{s.basin}</span>
                  <strong>{s.peak.vmax_kt.toFixed(0)} kt</strong>
                </div>
                <div className="pill-footer">
                  <span className={`cat-tag tone-${s.peak.category.tone}`}>
                    {s.peak.category.code}
                  </span>
                  <small>{s.observation_count} fixes</small>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* Superimposed Multi-Line Intensity Chart */}
      <section className="panel chart-panel">
        <header className="panel-header">
          <div>
            <h2>Normalized Lifecycle Intensity Curves</h2>
            <p>Wind speed (Vmax kt) plotted from Genesis (T+0 hours) to Landfall/Dissipation</p>
          </div>
          <div className="chart-legend">
            {activeStorms.map((s, i) => (
              <span key={s.storm_id} className="legend-item">
                <i style={{ background: colors[i % colors.length] }} />
                {s.name} ({s.peak.vmax_kt.toFixed(0)} kt)
              </span>
            ))}
          </div>
        </header>

        <div className="comparison-chart-container">
          <svg
            viewBox="0 0 900 320"
            className="comparison-svg-chart"
            preserveAspectRatio="none"
          >
            {/* Background Grid & Category Bands */}
            <line x1="60" y1="40" x2="880" y2="40" stroke="#334155" strokeDasharray="3 3" opacity="0.4" />
            <text x="50" y="44" fill="#94a3b8" fontSize="10" textAnchor="end">140 kt (Super)</text>

            <line x1="60" y1="90" x2="880" y2="90" stroke="#334155" strokeDasharray="3 3" opacity="0.4" />
            <text x="50" y="94" fill="#94a3b8" fontSize="10" textAnchor="end">115 kt (ESCS)</text>

            <line x1="60" y1="150" x2="880" y2="150" stroke="#334155" strokeDasharray="3 3" opacity="0.4" />
            <text x="50" y="154" fill="#94a3b8" fontSize="10" textAnchor="end">64 kt (VSCS)</text>

            <line x1="60" y1="210" x2="880" y2="210" stroke="#334155" strokeDasharray="3 3" opacity="0.4" />
            <text x="50" y="214" fill="#94a3b8" fontSize="10" textAnchor="end">34 kt (CS)</text>

            <line x1="60" y1="270" x2="880" y2="270" stroke="#475569" opacity="0.6" />
            <text x="50" y="274" fill="#94a3b8" fontSize="10" textAnchor="end">0 kt</text>

            {/* Time Axis Labels */}
            <text x="60" y="295" fill="#64748b" fontSize="10" textAnchor="middle">T+0h</text>
            <text x="265" y="295" fill="#64748b" fontSize="10" textAnchor="middle">T+48h</text>
            <text x="470" y="295" fill="#64748b" fontSize="10" textAnchor="middle">T+96h</text>
            <text x="675" y="295" fill="#64748b" fontSize="10" textAnchor="middle">T+144h</text>
            <text x="880" y="295" fill="#64748b" fontSize="10" textAnchor="middle">T+192h+</text>

            {/* Storm Curves */}
            {activeStorms.map((s, sIdx) => {
              if (!s.track || s.track.length < 2) return null;
              const startTime = new Date(s.track[0].valid_time).getTime();
              const color = colors[sIdx % colors.length];

              const pathPoints = s.track.map((pt) => {
                const curTime = new Date(pt.valid_time).getTime();
                const hours = (curTime - startTime) / (1000 * 3600);
                const x = 60 + (hours / Math.max(1, maxHours)) * 820;
                const y = 270 - (pt.vmax_kt / 160) * 230;
                return { x, y, pt, hours };
              });

              const d = pathPoints.reduce((acc, p, idx) => {
                return idx === 0 ? `M ${p.x.toFixed(1)} ${p.y.toFixed(1)}` : `${acc} L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
              }, "");

              return (
                <g key={s.storm_id}>
                  <path
                    d={d}
                    fill="none"
                    stroke={color}
                    strokeWidth="3.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  {pathPoints.map((p, pIdx) => {
                    const isPeak = p.pt.vmax_kt === s.peak.vmax_kt;
                    if (isPeak || pIdx % 4 === 0) {
                      return (
                        <circle
                          key={pIdx}
                          cx={p.x}
                          cy={p.y}
                          r={isPeak ? 5.5 : 3}
                          fill={isPeak ? "#ffffff" : color}
                          stroke={color}
                          strokeWidth={isPeak ? 2.5 : 1}
                        />
                      );
                    }
                    return null;
                  })}
                </g>
              );
            })}
          </svg>
        </div>
      </section>

      {/* Comparison Metrics Grid */}
      <section className="comparison-table-panel panel">
        <header className="panel-header">
          <div>
            <h2>Meteorological Parameters & Benchmark Comparison</h2>
            <p>Direct side-by-side metric breakdown derived from NOAA IBTrACS & IMD Best Track fixes</p>
          </div>
        </header>

        <div className="table-responsive">
          <table className="comparison-table">
            <thead>
              <tr>
                <th>Cyclone</th>
                <th>Basin</th>
                <th>Year</th>
                <th>Peak Intensity</th>
                <th>IMD Category</th>
                <th>Max 24h RI Delta</th>
                <th>Duration</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {activeStorms.map((s, idx) => {
                const color = colors[idx % colors.length];
                const max24hChange = s.track.reduce(
                  (max, p) => Math.max(max, p.change_24h_kt || 0),
                  0,
                );
                const startTime = new Date(s.track[0].valid_time).getTime();
                const endTime = new Date(s.track[s.track.length - 1].valid_time).getTime();
                const durationDays = ((endTime - startTime) / (1000 * 3600 * 24)).toFixed(1);

                return (
                  <tr key={s.storm_id}>
                    <td>
                      <div className="table-storm-name">
                        <span className="color-indicator" style={{ background: color }} />
                        <strong>Cyclone {s.name}</strong>
                      </div>
                    </td>
                    <td>{s.basin}</td>
                    <td>{s.first_valid_time.slice(0, 4)}</td>
                    <td>
                      <strong className="table-wind">{s.peak.vmax_kt.toFixed(0)} kt</strong>
                    </td>
                    <td>
                      <span className={`cat-tag tone-${s.peak.category.tone}`}>
                        {s.peak.category.name}
                      </span>
                    </td>
                    <td>
                      <span className={max24hChange >= 30 ? "ri-badge severe" : "ri-badge"}>
                        {max24hChange > 0 ? `+${max24hChange.toFixed(0)} kt / 24h` : "N/A"}
                      </span>
                    </td>
                    <td>{durationDays} days</td>
                    <td>
                      <button
                        className="button secondary small"
                        onClick={() => onSelectStorm(s.storm_id)}
                      >
                        Replay <ArrowRight size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
