/**
 * SafeReach — Family Tracker Page
 * No login required — accessed via JWT-signed link in SMS.
 * Shows: victim location, ambulance position, ETA, receiving hospital.
 */

"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import dynamic from "next/dynamic";

const TrackerMap = dynamic(() => import("@/components/TrackerMap"), { ssr: false });

const STATUS_MESSAGES = {
  reported:         "🆘 Accident reported — dispatching help now",
  dispatched:       "🚑 Ambulance dispatched and on the way",
  en_route:         "🚑 Ambulance en route to accident location",
  on_scene:         "✅ Emergency crew arrived at scene",
  hospital_handoff: "🏥 Patient being admitted to hospital",
  closed:           "✅ Incident closed",
};

export default function TrackerPage() {
  const router  = useRouter();
  const { token } = router.query;

  const [data, setData]       = useState(null);
  const [error, setError]     = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;

    const fetchData = async () => {
      try {
        const res = await fetch(`/api/v1/tracker/data?token=${token}`);
        if (!res.ok) throw new Error(res.status === 401 ? "This link has expired." : "Unable to load tracking data.");
        setData(await res.json());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    // Refresh every 15 seconds for live updates
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [token]);

  if (loading) return <LoadingScreen />;
  if (error)   return <ErrorScreen message={error} />;
  if (!data)   return null;

  const etaMinutes = data.ambulance_eta_seconds
    ? Math.ceil(data.ambulance_eta_seconds / 60)
    : null;

  return (
    <div style={{ minHeight: "100vh", background: "#0f172a", color: "#e2e8f0", fontFamily: "'Inter', sans-serif" }}>
      {/* Header */}
      <div style={{ padding: "16px 20px", background: "#1e293b", borderBottom: "1px solid #334155" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 22 }}>🚨</span>
          <div>
            <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: "#f8fafc" }}>SafeReach</h1>
            <p style={{ margin: 0, fontSize: 12, color: "#64748b" }}>Live Emergency Tracker</p>
          </div>
        </div>
      </div>

      {/* Status Banner */}
      <div style={{
        padding: "14px 20px",
        background: data.incident_status === "closed" ? "#14532d" : "#7c2d12",
        fontSize: 14, fontWeight: 500,
      }}>
        {STATUS_MESSAGES[data.incident_status] || `Status: ${data.incident_status}`}
      </div>

      {/* Map */}
      <div style={{ height: 320 }}>
        <TrackerMap
          victimLat={data.victim_latitude}
          victimLng={data.victim_longitude}
          ambulanceLat={data.ambulance_latitude}
          ambulanceLng={data.ambulance_longitude}
        />
      </div>

      {/* Info cards */}
      <div style={{ padding: "20px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
        {/* ETA card */}
        {etaMinutes !== null && data.incident_status !== "closed" && (
          <InfoCard
            icon="🕐"
            label="Estimated arrival"
            value={`${etaMinutes} min`}
            highlight
          />
        )}

        {/* Hospital */}
        {data.receiving_hospital_name && (
          <InfoCard
            icon="🏥"
            label="Receiving hospital"
            value={data.receiving_hospital_name}
          />
        )}

        {/* Last updated */}
        <InfoCard
          icon="🔄"
          label="Last updated"
          value={new Date(data.last_updated).toLocaleTimeString()}
        />

        {/* Emergency number */}
        <div style={{
          padding: "14px 16px", background: "#1e293b", borderRadius: 12,
          border: "1px solid #334155", textAlign: "center",
        }}>
          <p style={{ margin: "0 0 8px", fontSize: 13, color: "#94a3b8" }}>
            For additional help, call
          </p>
          <a
            href="tel:112"
            style={{ fontSize: 28, fontWeight: 700, color: "#dc2626", textDecoration: "none" }}
          >
            112
          </a>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "#64748b" }}>National Emergency</p>
        </div>
      </div>
    </div>
  );
}

function InfoCard({ icon, label, value, highlight }) {
  return (
    <div style={{
      padding: "14px 16px", background: "#1e293b", borderRadius: 12,
      border: `1px solid ${highlight ? "#3b82f6" : "#334155"}`,
      display: "flex", alignItems: "center", gap: 14,
    }}>
      <span style={{ fontSize: 24 }}>{icon}</span>
      <div>
        <div style={{ fontSize: 11, color: "#64748b", marginBottom: 2 }}>{label}</div>
        <div style={{
          fontSize: highlight ? 22 : 15,
          fontWeight: highlight ? 700 : 500,
          color: highlight ? "#60a5fa" : "#e2e8f0",
        }}>
          {value}
        </div>
      </div>
    </div>
  );
}

function LoadingScreen() {
  return (
    <div style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0f172a", flexDirection: "column", gap: 16 }}>
      <span style={{ fontSize: 40 }}>🚨</span>
      <p style={{ color: "#94a3b8", fontFamily: "sans-serif" }}>Loading tracker…</p>
    </div>
  );
}

function ErrorScreen({ message }) {
  return (
    <div style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0f172a", flexDirection: "column", gap: 16, padding: 20, textAlign: "center" }}>
      <span style={{ fontSize: 40 }}>⚠️</span>
      <p style={{ color: "#f87171", fontFamily: "sans-serif", maxWidth: 300 }}>{message}</p>
      <a href="tel:112" style={{ color: "#dc2626", fontSize: 22, fontWeight: 700, fontFamily: "sans-serif" }}>Call 112</a>
    </div>
  );
}
