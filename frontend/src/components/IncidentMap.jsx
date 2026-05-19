/**
 * SafeReach — Incident Map Component (Leaflet)
 * Real-time map with incident pins, ambulance tracking, hotspot heatmap.
 * SSR disabled — Leaflet requires window object.
 */

import { useEffect, useRef } from "react";

const SEVERITY_PIN_COLOR = {
  critical: "#dc2626",
  medium:   "#d97706",
  low:      "#16a34a",
};

export default function IncidentMap({ incidents, selectedIncident, onIncidentClick }) {
  const mapRef   = useRef(null);
  const leafletRef = useRef(null);
  const markersRef = useRef({});

  // ── Initialise Leaflet map ─────────────────────────────────────────────────
  useEffect(() => {
    if (leafletRef.current) return; // already initialised

    const L = require("leaflet");
    require("leaflet/dist/leaflet.css");

    const map = L.map(mapRef.current, {
      center: [20.5937, 78.9629], // centre of India
      zoom:   5,
      zoomControl: true,
      attributionControl: false,
    });

    // Dark tile layer
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { subdomains: "abcd", maxZoom: 19 }
    ).addTo(map);

    leafletRef.current = map;

    return () => {
      map.remove();
      leafletRef.current = null;
    };
  }, []);

  // ── Sync incident markers ──────────────────────────────────────────────────
  useEffect(() => {
    const map = leafletRef.current;
    if (!map) return;

    const L = require("leaflet");
    const currentIds = new Set(incidents.map((i) => i.id));

    // Remove stale markers
    Object.entries(markersRef.current).forEach(([id, marker]) => {
      if (!currentIds.has(id)) {
        map.removeLayer(marker);
        delete markersRef.current[id];
      }
    });

    // Add / update markers
    incidents.forEach((inc) => {
      if (!inc.latitude || !inc.longitude) return;
      const color = SEVERITY_PIN_COLOR[inc.severity] || "#64748b";
      const isSelected = selectedIncident?.id === inc.id;

      const icon = L.divIcon({
        className: "",
        html: `
          <div style="
            width: ${isSelected ? 20 : 14}px;
            height: ${isSelected ? 20 : 14}px;
            background: ${color};
            border: 2px solid ${isSelected ? "#fff" : "rgba(255,255,255,0.4)"};
            border-radius: 50%;
            box-shadow: 0 0 ${isSelected ? 12 : 6}px ${color};
            cursor: pointer;
          "></div>
        `,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });

      if (markersRef.current[inc.id]) {
        markersRef.current[inc.id].setIcon(icon);
      } else {
        const marker = L.marker([inc.latitude, inc.longitude], { icon })
          .addTo(map)
          .on("click", () => onIncidentClick(inc));

        marker.bindTooltip(
          `<strong>${inc.severity?.toUpperCase()}</strong><br>${
            inc.address_approx || `${inc.latitude.toFixed(4)}, ${inc.longitude.toFixed(4)}`
          }`,
          { className: "safereach-tooltip", direction: "top" }
        );
        markersRef.current[inc.id] = marker;
      }
    });
  }, [incidents, selectedIncident, onIncidentClick]);

  // ── Pan to selected incident ───────────────────────────────────────────────
  useEffect(() => {
    const map = leafletRef.current;
    if (!map || !selectedIncident?.latitude) return;
    map.flyTo([selectedIncident.latitude, selectedIncident.longitude], 14, {
      duration: 1.2,
    });
  }, [selectedIncident]);

  return (
    <>
      <style>{`
        .safereach-tooltip {
          background: #0f172a;
          border: 1px solid #334155;
          color: #e2e8f0;
          font-size: 12px;
          padding: 6px 10px;
          border-radius: 6px;
        }
        .safereach-tooltip::before { display: none; }
      `}</style>
      <div
        ref={mapRef}
        style={{ width: "100%", height: "100%", background: "#0f172a" }}
      />
    </>
  );
}
