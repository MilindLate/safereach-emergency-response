"use client";

/**
 * SafeReach — Dispatcher Dashboard (Next.js 14)
 * Real-time incident feed, severity-sorted, one-click dispatch.
 * Connects to backend via Socket.io for live updates.
 */

import { useEffect, useState, useCallback } from "react";
import Head from "next/head";
import dynamic from "next/dynamic";

// Dynamic import for map (SSR disabled — Leaflet requires window)
const IncidentMap = dynamic(() => import("@/components/IncidentMap"), { ssr: false });

const SEVERITY_COLOR = {
  critical: "#dc2626",
  medium: "#d97706",
  low: "#16a34a",
};

const SEVERITY_LABEL = {
  critical: "CRITICAL",
  medium: "URGENT",
  low: "STANDARD",
};

const STATUS_LABEL = {
  reported: "Reported",
  dispatched: "Dispatched",
  en_route: "En Route",
  on_scene: "On Scene",
  hospital_handoff: "Hospital Handoff",
  closed: "Closed",
};

export default function DispatcherDashboard() {
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isAssigning, setIsAssigning] = useState(false);
  const [filterStatus, setFilterStatus] = useState("active");
  const [candidates, setCandidates] = useState([]);
  const [authToken, setAuthToken] = useState(null);

  // ── Fetch incidents from API ────────────────────────────────────────────────
  const fetchIncidents = useCallback(async () => {
    if (!authToken) return;
    try {
      const statusParam = filterStatus === "active" ? "" : `?status=${filterStatus}`;
      const res = await fetch(`/api/v1/incidents/${statusParam}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error("Failed to fetch incidents");
      const data = await res.json();
      // Sort by severity: critical > medium > low, then by time
      const sorted = data.sort((a, b) => {
        const order = { critical: 0, medium: 1, low: 2 };
        if (order[a.severity] !== order[b.severity]) return order[a.severity] - order[b.severity];
        return new Date(b.created_at) - new Date(a.created_at);
      });
      setIncidents(sorted);
    } catch (err) {
      console.error("Error fetching incidents:", err);
    }
  }, [authToken, filterStatus]);

  // ── Socket.io real-time connection ─────────────────────────────────────────
  useEffect(() => {
    if (!authToken) return;

    let socket;
    import("socket.io-client").then(({ io }) => {
      socket = io(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000", {
        auth: { token: authToken },
        transports: ["websocket"],
      });

      socket.on("connect", () => {
        setIsConnected(true);
        socket.emit("join_room", "safereach:incidents");
      });

      socket.on("disconnect", () => setIsConnected(false));

      socket.on("new_incident", (data) => {
        setIncidents((prev) => {
          const updated = [{ ...data, _new: true }, ...prev];
          return updated.sort((a, b) => {
            const order = { critical: 0, medium: 1, low: 2 };
            return (order[a.severity] || 1) - (order[b.severity] || 1);
          });
        });
        // Audio alert for critical
        if (data.severity === "critical") {
          playAlertSound();
        }
      });

      socket.on("incident_updated", (data) => {
        setIncidents((prev) =>
          prev.map((inc) =>
            inc.id === data.incident_id
              ? { ...inc, status: data.status, ambulance_unit_code: data.ambulance_code }
              : inc
          )
        );
        if (selectedIncident?.id === data.incident_id) {
          setSelectedIncident((prev) => ({ ...prev, ...data }));
        }
      });

      socket.on("severity_updated", (data) => {
        setIncidents((prev) =>
          prev.map((inc) =>
            inc.id === data.incident_id
              ? { ...inc, severity: data.severity, cnn_confidence: data.cnn_confidence }
              : inc
          )
        );
      });
    });

    return () => socket?.disconnect();
  }, [authToken]);

  // ── Load candidates when incident selected ─────────────────────────────────
  useEffect(() => {
    if (!selectedIncident || !authToken) return;

    const loadCandidates = async () => {
      try {
        const res = await fetch(
          `/api/v1/dispatch/candidates/${selectedIncident.id}?limit=5`,
          { headers: { Authorization: `Bearer ${authToken}` } }
        );
        if (res.ok) {
          setCandidates(await res.json());
        }
      } catch (err) {
        console.error("Error loading candidates:", err);
      }
    };
    loadCandidates();
  }, [selectedIncident, authToken]);

  useEffect(() => { fetchIncidents(); }, [fetchIncidents]);

  // ── Dispatch action ────────────────────────────────────────────────────────
  const handleAssign = async (ambulanceUnitId) => {
    if (!selectedIncident || isAssigning) return;
    setIsAssigning(true);
    try {
      const res = await fetch("/api/v1/dispatch/assign", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          incident_id: selectedIncident.id,
          ambulance_unit_id: ambulanceUnitId,
        }),
      });
      if (!res.ok) throw new Error("Dispatch failed");
      await fetchIncidents();
      setSelectedIncident(null);
    } catch (err) {
      alert("Dispatch error: " + err.message);
    } finally {
      setIsAssigning(false);
    }
  };

  const playAlertSound = () => {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    osc.connect(ctx.destination);
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.1);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
  };

  const activeIncidents = incidents.filter((i) =>
    filterStatus === "active"
      ? !["closed"].includes(i.status)
      : i.status === filterStatus
  );

  // Simple login gate
  if (!authToken) {
    return <LoginScreen onLogin={setAuthToken} />;
  }

  return (
    <>
      <Head>
        <title>SafeReach — Dispatcher Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div style={{ display: "flex", height: "100vh", fontFamily: "'Inter', sans-serif", background: "#0f172a", color: "#e2e8f0" }}>
        {/* ── Sidebar: incident feed ── */}
        <div style={{ width: 380, flexShrink: 0, display: "flex", flexDirection: "column", borderRight: "1px solid #1e293b" }}>
          {/* Header */}
          <div style={{ padding: "16px 20px", borderBottom: "1px solid #1e293b", background: "#0f172a" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 20, fontWeight: 700, color: "#f8fafc" }}>🚨 SafeReach</span>
                <span style={{ fontSize: 11, background: isConnected ? "#15803d" : "#7f1d1d", color: "#fff", padding: "2px 8px", borderRadius: 99, fontWeight: 500 }}>
                  {isConnected ? "LIVE" : "OFFLINE"}
                </span>
              </div>
              <span style={{ fontSize: 12, color: "#64748b" }}>{activeIncidents.length} active</span>
            </div>
            {/* Filter tabs */}
            <div style={{ display: "flex", gap: 6 }}>
              {["active", "dispatched", "closed"].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilterStatus(f)}
                  style={{
                    padding: "4px 12px", borderRadius: 6, border: "none", cursor: "pointer",
                    fontSize: 12, fontWeight: 500,
                    background: filterStatus === f ? "#3b82f6" : "#1e293b",
                    color: filterStatus === f ? "#fff" : "#94a3b8",
                  }}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Incident list */}
          <div style={{ flex: 1, overflowY: "auto" }}>
            {activeIncidents.length === 0 && (
              <div style={{ padding: 40, textAlign: "center", color: "#475569" }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>✓</div>
                <div>No active incidents</div>
              </div>
            )}
            {activeIncidents.map((inc) => (
              <IncidentCard
                key={inc.id}
                incident={inc}
                isSelected={selectedIncident?.id === inc.id}
                onClick={() => setSelectedIncident(inc)}
              />
            ))}
          </div>
        </div>

        {/* ── Main: map + detail panel ── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          {/* Map */}
          <div style={{ flex: 1, position: "relative" }}>
            <IncidentMap
              incidents={activeIncidents}
              selectedIncident={selectedIncident}
              onIncidentClick={setSelectedIncident}
            />
          </div>

          {/* Detail + dispatch panel */}
          {selectedIncident && (
            <DispatchPanel
              incident={selectedIncident}
              candidates={candidates}
              isAssigning={isAssigning}
              onAssign={handleAssign}
              onClose={() => setSelectedIncident(null)}
            />
          )}
        </div>
      </div>
    </>
  );
}


// ── Sub-components ─────────────────────────────────────────────────────────────

function IncidentCard({ incident, isSelected, onClick }) {
  const color = SEVERITY_COLOR[incident.severity] || "#64748b";
  const age = Math.floor((Date.now() - new Date(incident.created_at)) / 60000);

  return (
    <div
      onClick={onClick}
      style={{
        padding: "14px 20px",
        borderBottom: "1px solid #1e293b",
        cursor: "pointer",
        background: isSelected ? "#1e3a5f" : "transparent",
        borderLeft: `3px solid ${color}`,
        transition: "background 0.15s",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color, letterSpacing: "0.08em" }}>
          {SEVERITY_LABEL[incident.severity]}
        </span>
        <span style={{ fontSize: 11, color: "#64748b" }}>{age}m ago</span>
      </div>
      <div style={{ fontSize: 13, color: "#e2e8f0", marginBottom: 4 }}>
        {incident.address_approx || `${incident.latitude?.toFixed(4)}, ${incident.longitude?.toFixed(4)}`}
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <StatusBadge status={incident.status} />
        {incident.ambulance_unit_code && (
          <span style={{ fontSize: 11, color: "#38bdf8" }}>🚑 {incident.ambulance_unit_code}</span>
        )}
        {incident.cnn_score != null && (
          <span style={{ fontSize: 11, color: "#a78bfa" }}>
            AI: {(incident.cnn_score * 100).toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  const colors = {
    reported: ["#7c2d12", "#fb923c"],
    dispatched: ["#1e3a5f", "#60a5fa"],
    en_route: ["#14532d", "#4ade80"],
    on_scene: ["#713f12", "#fbbf24"],
    hospital_handoff: ["#1e1b4b", "#a5b4fc"],
    closed: ["#1e293b", "#64748b"],
  };
  const [bg, text] = colors[status] || ["#1e293b", "#64748b"];
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 99,
      background: bg, color: text, letterSpacing: "0.06em",
    }}>
      {STATUS_LABEL[status] || status}
    </span>
  );
}

function DispatchPanel({ incident, candidates, isAssigning, onAssign, onClose }) {
  return (
    <div style={{
      height: 260, background: "#0f172a", borderTop: "1px solid #1e293b",
      padding: 20, overflowY: "auto",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#f8fafc", marginBottom: 4 }}>
            Incident {incident.id?.slice(0, 8)}…
          </div>
          <div style={{ fontSize: 12, color: "#64748b" }}>
            Severity: <strong style={{ color: SEVERITY_COLOR[incident.severity] }}>
              {SEVERITY_LABEL[incident.severity]}
            </strong>
            {incident.hospital_name && ` · Hospital: ${incident.hospital_name}`}
          </div>
        </div>
        <button onClick={onClose} style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer", fontSize: 18 }}>×</button>
      </div>

      {incident.status === "reported" ? (
        <>
          <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 10 }}>
            Select ambulance unit to dispatch:
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {candidates.length === 0 && (
              <span style={{ fontSize: 12, color: "#475569" }}>Loading available units…</span>
            )}
            {candidates.map((unit) => (
              <button
                key={unit.id}
                onClick={() => onAssign(unit.id)}
                disabled={isAssigning}
                style={{
                  padding: "8px 16px", borderRadius: 8, border: "1px solid #3b82f6",
                  background: "#1e3a5f", color: "#93c5fd", cursor: "pointer",
                  fontSize: 12, fontWeight: 600, transition: "all 0.15s",
                  opacity: isAssigning ? 0.5 : 1,
                }}
              >
                🚑 {unit.unit_code}
                {unit.distance_km && ` · ${unit.distance_km.toFixed(1)}km`}
              </button>
            ))}
          </div>
        </>
      ) : (
        <div style={{ fontSize: 13, color: "#64748b" }}>
          This incident is already <strong style={{ color: "#60a5fa" }}>{STATUS_LABEL[incident.status]}</strong>.
          {incident.ambulance_unit_code && ` Unit ${incident.ambulance_unit_code} assigned.`}
        </div>
      )}
    </div>
  );
}

function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/v1/auth/dispatcher/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error("Invalid credentials");
      const data = await res.json();
      localStorage.setItem("safereach_token", data.access_token);
      onLogin(data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      height: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "#0f172a", fontFamily: "'Inter', sans-serif",
    }}>
      <div style={{ width: 380, padding: 40, background: "#1e293b", borderRadius: 16, border: "1px solid #334155" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>🚨</div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "#f8fafc" }}>SafeReach</h1>
          <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 14 }}>Dispatcher Dashboard</p>
        </div>
        <form onSubmit={handleSubmit}>
          <input
            type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}
            required
            style={{ width: "100%", padding: "12px 16px", background: "#0f172a", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0", fontSize: 14, marginBottom: 12, boxSizing: "border-box" }}
          />
          <input
            type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)}
            required
            style={{ width: "100%", padding: "12px 16px", background: "#0f172a", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0", fontSize: 14, marginBottom: 16, boxSizing: "border-box" }}
          />
          {error && <div style={{ color: "#f87171", fontSize: 13, marginBottom: 12 }}>{error}</div>}
          <button
            type="submit" disabled={loading}
            style={{
              width: "100%", padding: "12px", background: "#3b82f6", border: "none", borderRadius: 8,
              color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer",
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
