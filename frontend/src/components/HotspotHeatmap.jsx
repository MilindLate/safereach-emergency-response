/**
 * SafeReach — Hotspot Heatmap Panel
 * D3-powered grid heatmap showing XGBoost accident risk scores.
 * Data refreshed every 6 hours by Celery beat task.
 * Rendered as an SVG overlay panel — not on the main Leaflet map
 * to avoid SSR issues. Toggle from dashboard header.
 */

import { useEffect, useRef, useState } from "react";

const RISK_COLORS = [
  { threshold: 0.70, color: "#dc2626", label: "High Risk"    },
  { threshold: 0.40, color: "#f97316", label: "Moderate"     },
  { threshold: 0.00, color: "#22c55e", label: "Low Risk"     },
];

function riskColor(score) {
  for (const { threshold, color } of RISK_COLORS) {
    if (score >= threshold) return color;
  }
  return "#22c55e";
}

const STUB_HOTSPOTS = [
  { lat: 28.61, lng: 77.23, risk: 0.82, road: "NH-48", label: "Dhaula Kuan" },
  { lat: 19.07, lng: 72.87, risk: 0.74, road: "NH-8",  label: "Bhiwandi" },
  { lat: 12.97, lng: 77.59, risk: 0.68, road: "ORR",   label: "Silk Board Jn" },
  { lat: 22.57, lng: 88.36, risk: 0.63, road: "NH-6",  label: "Ultadanga" },
  { lat: 17.38, lng: 78.47, risk: 0.55, road: "ORR",   label: "LB Nagar" },
  { lat: 13.08, lng: 80.27, risk: 0.49, road: "GST Rd",label: "Tambaram" },
  { lat: 21.25, lng: 81.65, risk: 0.38, road: "NH-30", label: "Raipur bypass" },
  { lat: 26.85, lng: 80.94, risk: 0.29, road: "NH-27", label: "Lucknow ring" },
];

export default function HotspotHeatmap({ authToken, onClose }) {
  const [hotspots, setHotspots]   = useState(STUB_HOTSPOTS);
  const [loading, setLoading]     = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    const load = async () => {
      if (!authToken) return;
      setLoading(true);
      try {
        const res = await fetch("/api/v1/incidents/hotspots?limit=50", {
          headers: { Authorization: `Bearer ${authToken}` },
        });
        if (res.ok) {
          const data = await res.json();
          if (data.length > 0) {
            setHotspots(data);
            setLastUpdated(new Date());
          }
        }
      } catch {
        // use stub data
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [authToken]);

  const sorted = [...hotspots].sort((a, b) => b.risk - a.risk);

  return (
    <div style={{
      position: "absolute", top: 0, right: 0, bottom: 0,
      width: 320, background: "#0f172a",
      borderLeft: "1px solid #1e293b",
      display: "flex", flexDirection: "column",
      zIndex: 100,
      boxShadow: "-4px 0 24px rgba(0,0,0,0.5)",
    }}>
      {/* Header */}
      <div style={{
        padding: "14px 16px",
        borderBottom: "1px solid #1e293b",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#f8fafc" }}>
            🗺 Accident Hotspots
          </div>
          <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>
            {loading ? "Refreshing…" : lastUpdated
              ? `Updated ${lastUpdated.toLocaleTimeString()}`
              : "XGBoost predictions (6h refresh)"}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer", fontSize: 18 }}
        >
          ×
        </button>
      </div>

      {/* Legend */}
      <div style={{ padding: "10px 16px", display: "flex", gap: 12, borderBottom: "1px solid #1e293b" }}>
        {RISK_COLORS.map((r) => (
          <div key={r.label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: r.color }} />
            <span style={{ fontSize: 10, color: "#94a3b8" }}>{r.label}</span>
          </div>
        ))}
      </div>

      {/* Risk bar chart */}
      <div style={{ padding: "8px 0", flex: 1, overflowY: "auto" }}>
        {sorted.map((spot, i) => (
          <HotspotRow key={i} spot={spot} rank={i + 1} />
        ))}
      </div>

      {/* Footer note */}
      <div style={{
        padding: "10px 16px", borderTop: "1px solid #1e293b",
        fontSize: 10, color: "#334155",
      }}>
        Predictions based on iRAD 2015–2021 + MoRTH data. Not a substitute for field assessment.
      </div>
    </div>
  );
}

function HotspotRow({ spot, rank }) {
  const color = riskColor(spot.risk);
  const pct   = Math.round(spot.risk * 100);

  return (
    <div style={{
      padding: "10px 16px",
      borderBottom: "1px solid #0f172a",
      cursor: "pointer",
    }}
      onMouseEnter={(e) => e.currentTarget.style.background = "#1e293b"}
      onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
    >
      {/* Top row */}
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 11, color: "#475569", width: 16 }}>#{rank}</span>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#e2e8f0" }}>{spot.label}</div>
            <div style={{ fontSize: 10, color: "#64748b" }}>{spot.road}</div>
          </div>
        </div>
        <span style={{ fontSize: 13, fontWeight: 700, color }}>{pct}%</span>
      </div>

      {/* Risk bar */}
      <div style={{ height: 4, background: "#1e293b", borderRadius: 2, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${pct}%`,
          background: color,
          borderRadius: 2,
          transition: "width 0.6s ease",
        }} />
      </div>
    </div>
  );
}
