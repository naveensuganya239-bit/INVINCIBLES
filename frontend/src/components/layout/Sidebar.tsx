import { NavLink } from "react-router-dom";
import {
  IconOrbit,
  IconLayers,
  IconTarget,
  IconWave,
  IconLink,
  IconChart,
  IconGrid,
  IconSparkle,
  IconDoc,
  IconHistory,
  IconChevronLeft,
  IconChevronRight,
} from "../common/Icons";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Mission Control", icon: IconOrbit },
  { to: "/dataset", label: "Dataset", icon: IconLayers },
  { to: "/registration", label: "Registration", icon: IconTarget },
  { to: "/features", label: "Feature Analysis", icon: IconWave },
  { to: "/correspondence", label: "Correspondence", icon: IconLink },
  { to: "/results", label: "Results", icon: IconChart },
  { to: "/multi-sensor", label: "Multi-Sensor", icon: IconGrid },
  { to: "/lunar-ai", label: "Lunar AI", icon: IconSparkle },
  { to: "/reports", label: "Reports", icon: IconDoc },
  { to: "/history", label: "Run History", icon: IconHistory },
];

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <aside className={`sidebar${collapsed ? " collapsed" : ""}`}>
      <div className="sidebar-header">
        <div className="sidebar-mark" />
        {!collapsed && (
          <div>
            <div className="sidebar-title">INVINCIBLES</div>
            <div className="sidebar-subtitle">LUNAR REGISTRATION SYSTEM</div>
          </div>
        )}
      </div>

      <nav className="sidebar-nav">
        {!collapsed && <div className="nav-section-label">Analysis</div>}
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
            title={collapsed ? item.label : undefined}
          >
            <span className="nav-icon">
              <item.icon />
            </span>
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button className="collapse-btn" onClick={onToggle} aria-label="Toggle sidebar">
          {collapsed ? <IconChevronRight /> : (
            <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
              <IconChevronLeft /> Collapse
            </span>
          )}
        </button>
      </div>
    </aside>
  );
}
