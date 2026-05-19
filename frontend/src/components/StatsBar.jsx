/**
 * SafeReach — Dashboard Stats Bar
 * Real-time KPIs: active incidents, free ambulances, avg response time.
 * Refreshes every 30s via API polling.
 */

import { useEffect, useState } from "react";

const STAT_CONFIG = [
  { key: "active_incidents",   label: "Active Incidents",    icon: "🚨", color: "#dc2626" },
  { key: "critical_count",     label: "Critical",            icon: "🔴", color: "#f97316" },
  { key: "free_ambulances",    label: "Free Ambulances",     icon: "🚑", color: "#22c55e" },
  { key: "avg_dispatch_min",   label: "Avg Dispatch (min)",  icon: "⏱",  color: "#60a5fa" },
  { key: "avg_response_min",   label: "Avg Response (min)",  icon: "🏁", color: "#a78bfa" },
  { key: "resolved_today",     label: "Resolved Today",      icon: "✅", color: "#4ade80" },
];

export default function StatsBar({ authToken }) {
  const [stats, setStats] = useState({
    active_incidents:  "—",
    critical_count:    "—",
    free_ambulances:   "—",
    avg_dispatch_min:  "—",
    avg_response_min:  "—",
    resolved_today:    "—",
  });
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchStats = async () => {
    if (!authToken) return;
    try {
      const res = await fetch("/api/v1/incidents/stats/summary", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) return;
      const data = await res.json();
      setStats(data);
      setLastRefresh(new Date());
    } catch {
      // silently ignore — stats are non-critical
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30_000);
    return () => clearInterval(interval);
  }, [authToken]);

  return (
    <div style={{
      display: "flex",
      gap: 1,
      background: "#0f172a",
      borderBottom: "1px solid #1e293b",
      overflowX: "auto",
    }}>
      {STAT_CONFIG.map((s) => (
        <StatCell key={s.key} config={s} value={stats[s.key]} />
      ))}
      {lastRefresh && (
        <div style={{
          marginLeft: "auto",
          padding: "0 16px",
          display: "flex",
          alignItems: "center",
          fontSize: 10,
          color: "#334155",
          whiteSpace: "nowrap",
        }}>
          Refreshed {lastRefresh.toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}

function StatCell({ config, value }) {
  return (
    <div style={{
      flex: 1,
      minWidth: 100,
      padding: "10px 16px",
      display: "flex",
      flexDirection: "column",
      gap: 2,
      borderRight: "1px solid #1e293b",
    }}>
      <div style={{ fontSize: 10, color: "#475569", whiteSpace: "nowrap" }}>
        {config.icon} {config.label}
      </div>
      <div style={{ fontSize: 20, fontWeight: 700, color: config.color }}>
        {value}
      </div>
    </div>
  );
}
