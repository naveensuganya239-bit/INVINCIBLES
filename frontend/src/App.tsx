import { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Sidebar } from "./components/layout/Sidebar";
import { TopBar } from "./components/layout/TopBar";
import { RunProvider } from "./context/RunContext";

import MissionControl from "./pages/MissionControl";
import Dataset from "./pages/Dataset";
import Registration from "./pages/Registration";
import FeatureAnalysis from "./pages/FeatureAnalysis";
import Correspondence from "./pages/Correspondence";
import Results from "./pages/Results";
import MultiSensor from "./pages/MultiSensor";
import LunarAI from "./pages/LunarAI";
import Reports from "./pages/Reports";
import RunHistory from "./pages/RunHistory";

export default function App() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <RunProvider>
      <BrowserRouter>
        <div className="app-shell">
          <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
          <div className={`main-column${collapsed ? " sidebar-collapsed" : ""}`}>
            <TopBar />
            <Routes>
              <Route path="/" element={<MissionControl />} />
              <Route path="/dataset" element={<Dataset />} />
              <Route path="/registration" element={<Registration />} />
              <Route path="/features" element={<FeatureAnalysis />} />
              <Route path="/correspondence" element={<Correspondence />} />
              <Route path="/results" element={<Results />} />
              <Route path="/multi-sensor" element={<MultiSensor />} />
              <Route path="/lunar-ai" element={<LunarAI />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/history" element={<RunHistory />} />
            </Routes>
          </div>
        </div>
      </BrowserRouter>
    </RunProvider>
  );
}
