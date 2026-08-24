import {
  Activity,
  Bell,
  BookOpen,
  ChevronDown,
  Database,
  FlaskConical,
  GitCompare,
  HelpCircle,
  Menu,
  PanelLeftClose,
  Radar,
  Satellite,
  Search,
  Settings,
  ShieldCheck,
  Wind,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { getStatus, getStorm, getStorms, type StormListItem } from "./api";
import type { Storm, SystemStatus, ViewName } from "./types";
import AnalysisLab from "./views/AnalysisLab";
import DataModel from "./views/DataModel";
import Overview from "./views/Overview";
import StormComparison from "./views/StormComparison";

const DEFAULT_STORM_ID = "2013281N12098"; // Phailin

export default function App() {
  const [view, setView] = useState<ViewName>("overview");
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [stormsList, setStormsList] = useState<StormListItem[]>([]);
  const [selectedStormId, setSelectedStormId] = useState<string>(DEFAULT_STORM_ID);
  const [storm, setStorm] = useState<Storm | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Load initial status and storm catalog
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      getStatus(controller.signal),
      getStorms(controller.signal),
      getStorm(selectedStormId, controller.signal),
    ])
      .then(([nextStatus, nextStorms, nextStorm]) => {
        setStatus(nextStatus);
        setStormsList(nextStorms.items);
        setStorm(nextStorm);
        // Find peak or mid-point index as default
        const peakIdx = nextStorm.track.reduce(
          (best, p, idx) => (p.vmax_kt > nextStorm.track[best].vmax_kt ? idx : best),
          0,
        );
        setSelectedIndex(peakIdx);
      })
      .catch((reason) => {
        if (reason.name !== "AbortError") {
          setError(reason instanceof Error ? reason.message : "Unable to initialize Cyclone-AI");
        }
      });
    return () => controller.abort();
  }, []);

  // Handle storm selection changes
  function selectStorm(stormId: string) {
    if (stormId === selectedStormId && storm) return;
    setSelectedStormId(stormId);
    setPlaying(false);
    setSearchOpen(false);

    getStorm(stormId)
      .then((nextStorm) => {
        setStorm(nextStorm);
        const peakIdx = nextStorm.track.reduce(
          (best, p, idx) => (p.vmax_kt > nextStorm.track[best].vmax_kt ? idx : best),
          0,
        );
        setSelectedIndex(peakIdx);
      })
      .catch((err) => {
        console.error("Failed to load storm:", err);
      });
  }

  // Lifecycle playback
  useEffect(() => {
    if (!playing || !storm) return;
    const timer = window.setInterval(() => {
      setSelectedIndex((current) => {
        if (current >= storm.track.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 600);
    return () => window.clearInterval(timer);
  }, [playing, storm]);

  // Global keyboard shortcuts (Cmd+K / search, Space for play/pause, Arrow keys)
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      } else if (e.key === "Escape") {
        setSearchOpen(false);
      } else if (e.key === " " && view === "overview") {
        e.preventDefault();
        setPlaying((prev) => !prev);
      } else if (e.key === "ArrowRight" && view === "overview" && storm) {
        setSelectedIndex((i) => Math.min(storm.track.length - 1, i + 1));
      } else if (e.key === "ArrowLeft" && view === "overview" && storm) {
        setSelectedIndex((i) => Math.max(0, i - 1));
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [view, storm]);

  function navigate(next: ViewName) {
    setView(next);
    setPlaying(false);
    setSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  if (error) {
    return (
      <main className="fatal-state">
        <div className="brand-mark large"><Radar size={31} /></div>
        <h1>Cyclone-AI could not start</h1>
        <p>{error}</p>
        <button className="button primary" onClick={() => window.location.reload()}>Retry</button>
      </main>
    );
  }

  if (!status || !storm) return <LoadingScreen />;

  const filteredStorms = stormsList.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.sid.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.basin.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.peak.category.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "mobile-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Radar size={22} /></div>
          <div><strong>Cyclone<span>AI</span></strong><small>Operational workstation</small></div>
          <button className="mobile-close" onClick={() => setSidebarOpen(false)} aria-label="Close menu"><X size={19} /></button>
        </div>
        <div className="scope-card">
          <div><Satellite size={15} /><span>North Indian Ocean</span></div>
          <strong>MoES / IMD · SIH 2026</strong>
          <small>AI Analyst & Prediction System</small>
        </div>

        {/* Quick Storm Selector in Sidebar */}
        <div className="sidebar-storm-selector">
          <label htmlFor="sidebar-select">Active Cyclone</label>
          <div className="select-wrapper">
            <select
              id="sidebar-select"
              value={selectedStormId}
              onChange={(e) => selectStorm(e.target.value)}
            >
              {stormsList.map((s) => (
                <option key={s.storm_id} value={s.storm_id}>
                  {s.name} ({s.first_valid_time.slice(0, 4)}) — {s.peak.vmax_kt.toFixed(0)} kt
                </option>
              ))}
            </select>
            <ChevronDown size={14} className="select-arrow" />
          </div>
        </div>

        <nav aria-label="Primary navigation">
          <span className="nav-label">Workspace</span>
          <NavButton
            active={view === "overview"}
            onClick={() => navigate("overview")}
            icon={<Activity size={18} />}
            label="Storm intelligence"
            badge={`${stormsList.length}`}
          />
          <NavButton
            active={view === "comparison"}
            onClick={() => navigate("comparison")}
            icon={<GitCompare size={18} />}
            label="Storm comparison"
          />
          <NavButton
            active={view === "analysis"}
            onClick={() => navigate("analysis")}
            icon={<FlaskConical size={18} />}
            label="Dvorak analysis lab"
          />
          <NavButton
            active={view === "data"}
            onClick={() => navigate("data")}
            icon={<Database size={18} />}
            label="Data & model registry"
          />
          <span className="nav-label secondary-label">Reference</span>
          <a href="/api/docs" target="_blank" rel="noreferrer" className="nav-button">
            <BookOpen size={18} /><span>API endpoints</span>
          </a>
          <a
            href="https://github.com/krsidhantaryan-ux/SIH-2026/tree/arena/01a0338e-sih-2026/docs"
            target="_blank"
            rel="noreferrer"
            className="nav-button"
          >
            <HelpCircle size={18} /><span>Architecture docs</span>
          </a>
        </nav>

        <div className="sidebar-status">
          <div className="status-orbit"><span /><ShieldCheck size={17} /></div>
          <div>
            <strong>7 Historical Cyclones Loaded</strong>
            <span>HURSAT-B1 + NOAA IBTrACS</span>
          </div>
        </div>

        <div className="analyst-profile">
          <div className="avatar">RSMC</div>
          <div><strong>MoES Analyst</strong><span>Operational Console</span></div>
          <Settings size={16} />
        </div>
      </aside>
      {sidebarOpen && <button className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} aria-label="Close navigation" />}

      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-left">
            <button className="menu-button" onClick={() => setSidebarOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
            <PanelLeftClose size={17} className="desktop-panel-icon" />
            <span className="topbar-separator" />
            <span className="breadcrumb">
              Operations <b>/</b>{" "}
              {view === "overview"
                ? `Cyclone ${storm.name} Replay`
                : view === "comparison"
                ? "Multi-Storm Comparison"
                : view === "analysis"
                ? "Dvorak Analysis Lab"
                : "Model Lineage & Registry"}
            </span>
          </div>

          <div className="topbar-right">
            {/* Quick Cyclone Carousel / Dropdown */}
            <div className="storm-pills-container">
              {stormsList.slice(0, 5).map((s) => (
                <button
                  key={s.storm_id}
                  className={`storm-pill-btn ${s.storm_id === selectedStormId ? "active" : ""}`}
                  onClick={() => selectStorm(s.storm_id)}
                >
                  <Wind size={12} />
                  <span>{s.name}</span>
                  <small>{s.first_valid_time.slice(0, 4)}</small>
                </button>
              ))}
            </div>

            <button className="search-box" onClick={() => setSearchOpen(true)}>
              <Search size={16} />
              <span>Search storms...</span>
              <kbd>⌘ K</kbd>
            </button>

            <div className="environment-pill"><span /> Operational AI</div>
            <button className="top-icon" aria-label="Notifications"><Bell size={18} /><i /></button>
            <div className="top-avatar">IMD</div>
          </div>
        </header>

        <main className="main-content">
          {view === "overview" && (
            <Overview
              storm={storm}
              allStorms={stormsList}
              onSelectStorm={selectStorm}
              selectedIndex={selectedIndex}
              setSelectedIndex={setSelectedIndex}
              playing={playing}
              setPlaying={setPlaying}
              onOpenAnalysis={() => navigate("analysis")}
              onOpenComparison={() => navigate("comparison")}
              onStormUpdated={setStorm}
            />
          )}
          {view === "comparison" && (
            <StormComparison
              stormsList={stormsList}
              currentStorm={storm}
              onSelectStorm={(id) => {
                selectStorm(id);
                navigate("overview");
              }}
            />
          )}
          {view === "analysis" && <AnalysisLab status={status} />}
          {view === "data" && <DataModel status={status} />}
        </main>

        <footer className="app-footer">
          <span>Cyclone-AI · Ministry of Earth Sciences / IMD · SIH 2026</span>
          <span>Automated Dvorak Intensity Estimation & Rapid Intensification Alerting</span>
          <span>UTC Reference Time · WGS 84</span>
        </footer>
      </div>

      {/* Command Palette / Storm Search Modal */}
      {searchOpen && (
        <div className="modal-backdrop" onClick={() => setSearchOpen(false)}>
          <div className="command-palette" onClick={(e) => e.stopPropagation()}>
            <div className="command-input-row">
              <Search size={20} />
              <input
                autoFocus
                type="text"
                placeholder="Search cyclone by name, year, basin, or category..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <button className="close-btn" onClick={() => setSearchOpen(false)}><X size={18} /></button>
            </div>
            <div className="command-results">
              {filteredStorms.length === 0 ? (
                <div className="no-results">No cyclones match "{searchQuery}"</div>
              ) : (
                filteredStorms.map((s) => (
                  <button
                    key={s.storm_id}
                    className={`command-item ${s.storm_id === selectedStormId ? "selected" : ""}`}
                    onClick={() => {
                      selectStorm(s.storm_id);
                      if (view !== "overview") setView("overview");
                    }}
                  >
                    <div className="item-left">
                      <div className="storm-icon-box"><Wind size={18} /></div>
                      <div>
                        <strong>Cyclone {s.name}</strong>
                        <span>{s.basin} · {s.first_valid_time.slice(0, 4)}</span>
                      </div>
                    </div>
                    <div className="item-right">
                      <span className={`cat-pill tone-${s.peak.category.tone}`}>{s.peak.category.code}</span>
                      <strong className="peak-wind">{s.peak.vmax_kt.toFixed(0)} kt</strong>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function NavButton({
  active,
  onClick,
  icon,
  label,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  badge?: string;
}) {
  return (
    <button className={`nav-button ${active ? "active" : ""}`} onClick={onClick}>
      {icon}
      <span>{label}</span>
      {badge && <b>{badge}</b>}
    </button>
  );
}

function LoadingScreen() {
  return (
    <main className="loading-screen">
      <div className="loading-radar">
        <Radar size={36} />
        <i />
        <i />
        <i />
      </div>
      <strong>Initialising Cyclone-AI Analyst Console</strong>
      <span>Loading multi-storm satellite indices, NOAA best tracks, and AI inference engines…</span>
    </main>
  );
}

