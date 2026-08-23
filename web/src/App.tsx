import {
  Activity,
  Bell,
  BookOpen,
  Database,
  FlaskConical,
  HelpCircle,
  Menu,
  PanelLeftClose,
  Radar,
  Satellite,
  Search,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { getStatus, getStorm } from "./api";
import type { Storm, SystemStatus, ViewName } from "./types";
import AnalysisLab from "./views/AnalysisLab";
import DataModel from "./views/DataModel";
import Overview from "./views/Overview";

const DEMO_STORM_ID = "2013281N12098";

export default function App() {
  const [view, setView] = useState<ViewName>("overview");
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [storm, setStorm] = useState<Storm | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([getStatus(controller.signal), getStorm(DEMO_STORM_ID, controller.signal)])
      .then(([nextStatus, nextStorm]) => {
        setStatus(nextStatus);
        setStorm(nextStorm);
        const defaultTime = new Date("2013-10-10T12:00:00Z").getTime();
        const nearest = nextStorm.track.reduce(
          (best, point, index) =>
            Math.abs(new Date(point.valid_time).getTime() - defaultTime) <
            Math.abs(new Date(nextStorm.track[best].valid_time).getTime() - defaultTime)
              ? index
              : best,
          0,
        );
        setSelectedIndex(nearest);
      })
      .catch((reason) => {
        if (reason.name !== "AbortError") {
          setError(reason instanceof Error ? reason.message : "Unable to load the demonstration");
        }
      });
    return () => controller.abort();
  }, []);

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
    }, 650);
    return () => window.clearInterval(timer);
  }, [playing, storm]);

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

  return (
    <div className="app-shell">
      <aside className={`sidebar ${sidebarOpen ? "mobile-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Radar size={22} /></div>
          <div><strong>Cyclone<span>AI</span></strong><small>Analyst console</small></div>
          <button className="mobile-close" onClick={() => setSidebarOpen(false)} aria-label="Close menu"><X size={19} /></button>
        </div>
        <div className="scope-card">
          <div><Satellite size={15} /><span>North Indian Ocean</span></div>
          <strong>SIH 2026</strong>
          <small>Problem statement 26070</small>
        </div>
        <nav aria-label="Primary navigation">
          <span className="nav-label">Workspace</span>
          <NavButton active={view === "overview"} onClick={() => navigate("overview")} icon={<Activity size={18} />} label="Storm overview" badge="1" />
          <NavButton active={view === "analysis"} onClick={() => navigate("analysis")} icon={<FlaskConical size={18} />} label="Analysis lab" />
          <NavButton active={view === "data"} onClick={() => navigate("data")} icon={<Database size={18} />} label="Data & model" />
          <span className="nav-label secondary-label">Reference</span>
          <a href="/api/docs" target="_blank" rel="noreferrer" className="nav-button"><BookOpen size={18} /><span>API reference</span></a>
          <a href="https://github.com/krsidhantaryan-ux/SIH-2026/tree/arena/01a02f8d-sih-2026/docs" target="_blank" rel="noreferrer" className="nav-button"><HelpCircle size={18} /><span>Documentation</span></a>
        </nav>
        <div className="sidebar-status">
          <div className="status-orbit"><span /><ShieldCheck size={17} /></div>
          <div><strong>Demo systems ready</strong><span>Historical mode · v{status.release}</span></div>
        </div>
        <div className="analyst-profile">
          <div className="avatar">CA</div>
          <div><strong>Demo analyst</strong><span>Review workspace</span></div>
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
            <span className="breadcrumb">Operations <b>/</b> {view === "overview" ? "Storm intelligence" : view === "analysis" ? "Analysis lab" : "Data & model"}</span>
          </div>
          <div className="topbar-right">
            <button className="search-box" onClick={() => navigate("overview")}><Search size={16} /><span>Search storms</span><kbd>⌘ K</kbd></button>
            <div className="environment-pill"><span /> Historical demo</div>
            <button className="top-icon" aria-label="Notifications"><Bell size={18} /><i /></button>
            <div className="top-avatar">CA</div>
          </div>
        </header>

        <main className="main-content">
          {view === "overview" && (
            <Overview
              storm={storm}
              selectedIndex={selectedIndex}
              setSelectedIndex={setSelectedIndex}
              playing={playing}
              setPlaying={setPlaying}
              onOpenAnalysis={() => navigate("analysis")}
              onStormUpdated={setStorm}
            />
          )}
          {view === "analysis" && <AnalysisLab status={status} />}
          {view === "data" && <DataModel status={status} />}
        </main>
        <footer className="app-footer">
          <span>Cyclone-AI · SIH 2026 prototype</span>
          <span>Historical machine guidance only · Not an official forecast or warning</span>
          <span>UTC · {status.dataset.category_profile_id}</span>
        </footer>
      </div>
    </div>
  );
}

function NavButton({ active, onClick, icon, label, badge }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string; badge?: string }) {
  return <button className={`nav-button ${active ? "active" : ""}`} onClick={onClick}>{icon}<span>{label}</span>{badge && <b>{badge}</b>}</button>;
}

function LoadingScreen() {
  return (
    <main className="loading-screen">
      <div className="loading-radar"><Radar size={31} /><i /><i /><i /></div>
      <strong>Initialising Cyclone-AI</strong>
      <span>Verifying data, model integrity and analysis services…</span>
    </main>
  );
}
