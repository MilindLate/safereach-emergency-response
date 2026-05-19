/**
 * SafeReach — Analytics Page
 * Response-time trends, severity breakdown, hotspot map, weekly comparisons.
 */

"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const COLORS = { critical: "#dc2626", medium: "#f97316", low: "#22c55e" };

// Stub data — replaced by real API in production
const WEEKLY_INCIDENTS = [
  { day: "Mon", critical: 3, medium: 7, low: 5 },
  { day: "Tue", critical: 2, medium: 5, low: 8 },
  { day: "Wed", critical: 5, medium: 9, low: 3 },
  { day: "Thu", critical: 1, medium: 6, low: 7 },
  { day: "Fri", critical: 4, medium: 11, low: 6 },
  { day: "Sat", critical: 6, medium: 8, low: 4 },
  { day: "Sun", critical: 3, medium: 5, low: 9 },
];

const RESPONSE_TIMES = [
  { time: "00:00", avg_min: 12.4 },
  { time: "04:00", avg_min: 8.2  },
  { time: "08:00", avg_min: 18.7 },
  { time: "12:00", avg_min: 15.3 },
  { time: "16:00", avg_min: 21.1 },
  { time: "20:00", avg_min: 14.8 },
  { time: "23:59", avg_min: 10.2 },
];

const SEVERITY_PIE = [
  { name: "Critical", value: 24, color: "#dc2626" },
  { name: "Medium",   value: 51, color: "#f97316" },
  { name: "Low",      value: 25, color: "#22c55e" },
];

export default function AnalyticsPage() {
  const router = useRouter();
  const [authToken, setAuthToken] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("safereach_token");
    if (!token) { router.push("/"); return; }
    setAuthToken(token);
  }, []);

  return (
    <div style={{ minHeight: "100vh", background: "#0f172a", color: "#e2e8f0", fontFamily: "'Inter', sans-serif" }}>
      {/* Header */}
      <div style={{ padding: "16px 24px", borderBottom: "1px solid #1e293b", display: "flex", alignItems: "center", gap: 16 }}>
        <button
          onClick={() => router.push("/")}
          style={{ background: "none", border: "none", color: "#60a5fa", cursor: "pointer", fontSize: 14 }}
        >
          ← Dashboard
        </button>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: "#f8fafc" }}>Analytics</h1>
        <span style={{ fontSize: 12, color: "#475569" }}>Last 7 days</span>
      </div>

      <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>
        {/* KPI row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
          {[
            { label: "Total Incidents",     value: "143",   delta: "+12%", up: true  },
            { label: "Avg Response Time",   value: "14.2m", delta: "-18%", up: false },
            { label: "Dispatch Accuracy",   value: "96.4%", delta: "+2.1%",up: false },
            { label: "Lives Impacted",      value: "143",   delta: "Est.",  up: true  },
          ].map((kpi) => (
            <div key={kpi.label} style={{ background: "#1e293b", borderRadius: 12, padding: 20, border: "1px solid #334155" }}>
              <div style={{ fontSize: 12, color: "#64748b", marginBottom: 6 }}>{kpi.label}</div>
              <div style={{ fontSize: 28, fontWeight: 800, color: "#f8fafc" }}>{kpi.value}</div>
              <div style={{ fontSize: 12, color: kpi.up ? "#22c55e" : "#f97316", marginTop: 4 }}>
                {kpi.delta} vs last week
              </div>
            </div>
          ))}
        </div>

        {/* Charts row */}
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
          {/* Weekly incidents bar chart */}
          <ChartCard title="Weekly Incidents by Severity">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={WEEKLY_INCIDENTS} barSize={14}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="day" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }} />
                <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
                <Bar dataKey="critical" fill={COLORS.critical} name="Critical" radius={[3, 3, 0, 0]} />
                <Bar dataKey="medium"   fill={COLORS.medium}   name="Medium"   radius={[3, 3, 0, 0]} />
                <Bar dataKey="low"      fill={COLORS.low}       name="Low"      radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* Severity pie */}
          <ChartCard title="Severity Distribution">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={SEVERITY_PIE}
                  cx="50%" cy="50%"
                  innerRadius={60} outerRadius={85}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {SEVERITY_PIE.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }}
                  formatter={(val, name) => [`${val}%`, name]}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: "#94a3b8" }} />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>

        {/* Response time line chart */}
        <ChartCard title="Average Response Time by Hour of Day">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={RESPONSE_TIMES}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} unit="m" />
              <Tooltip
                contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0" }}
                formatter={(v) => [`${v} min`, "Avg Response"]}
              />
              <Line
                type="monotone" dataKey="avg_min"
                stroke="#60a5fa" strokeWidth={2.5}
                dot={{ fill: "#60a5fa", r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
          <div style={{ fontSize: 11, color: "#475569", marginTop: 8 }}>
            Peak congestion windows: 08:00–09:30 and 16:30–18:30 (weekdays)
          </div>
        </ChartCard>

        {/* AI model performance */}
        <ChartCard title="AI Model Performance">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, padding: "4px 0" }}>
            {[
              { model: "Severity CNN",    metric: "Accuracy",  value: "87.4%", target: "≥85%", met: true  },
              { model: "Hotspot XGBoost", metric: "F1 Score",  value: "0.838", target: "≥0.82",met: true  },
              { model: "Hotspot XGBoost", metric: "AUC-ROC",   value: "0.891", target: "≥0.85",met: true  },
            ].map((m, i) => (
              <div key={i} style={{ background: "#0f172a", borderRadius: 10, padding: 16, border: "1px solid #1e293b" }}>
                <div style={{ fontSize: 11, color: "#64748b", marginBottom: 4 }}>{m.model}</div>
                <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 6 }}>{m.metric}</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: m.met ? "#4ade80" : "#f87171" }}>{m.value}</div>
                <div style={{ fontSize: 10, color: "#475569", marginTop: 4 }}>
                  {m.met ? "✅" : "❌"} Target: {m.target}
                </div>
              </div>
            ))}
          </div>
        </ChartCard>
      </div>
    </div>
  );
}

function ChartCard({ title, children }) {
  return (
    <div style={{ background: "#1e293b", borderRadius: 12, padding: 20, border: "1px solid #334155" }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: "#94a3b8", marginBottom: 16 }}>{title}</div>
      {children}
    </div>
  );
}
