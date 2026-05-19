/**
 * SafeReach — Tracker Map (family-facing)
 * Shows victim pin + ambulance pin with animated pulse.
 */

import { useEffect, useRef } from "react";

export default function TrackerMap({ victimLat, victimLng, ambulanceLat, ambulanceLng }) {
  const mapRef = useRef(null);
  const leafletRef = useRef(null);
  const ambMarkerRef = useRef(null);

  useEffect(() => {
    if (!victimLat || !victimLng || leafletRef.current) return;

    const L = require("leaflet");
    require("leaflet/dist/leaflet.css");

    const map = L.map(mapRef.current, {
      center: [victimLat, victimLng],
      zoom: 13,
      zoomControl: false,
      attributionControl: false,
    });

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      { subdomains: "abcd", maxZoom: 19 }
    ).addTo(map);

    // Victim pin — pulsing red
    const victimIcon = L.divIcon({
      className: "",
      html: `
        <div style="position:relative;width:20px;height:20px">
          <div style="position:absolute;width:20px;height:20px;background:#dc2626;border-radius:50%;border:2px solid #fff;z-index:2"></div>
          <div style="position:absolute;width:20px;height:20px;background:#dc2626;border-radius:50%;opacity:0.5;animation:ping 1.5s cubic-bezier(0,0,0.2,1) infinite;z-index:1"></div>
        </div>
        <style>@keyframes ping{75%,100%{transform:scale(2);opacity:0}}</style>
      `,
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });

    L.marker([victimLat, victimLng], { icon: victimIcon })
      .addTo(map)
      .bindTooltip("Accident location", { permanent: true, direction: "top", className: "safereach-tooltip" });

    leafletRef.current = map;

    return () => {
      map.remove();
      leafletRef.current = null;
    };
  }, [victimLat, victimLng]);

  // Update ambulance marker
  useEffect(() => {
    const map = leafletRef.current;
    if (!map || !ambulanceLat || !ambulanceLng) return;

    const L = require("leaflet");
    const ambIcon = L.divIcon({
      className: "",
      html: `<div style="font-size:24px;line-height:1">🚑</div>`,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });

    if (ambMarkerRef.current) {
      ambMarkerRef.current.setLatLng([ambulanceLat, ambulanceLng]);
    } else {
      ambMarkerRef.current = L.marker([ambulanceLat, ambulanceLng], { icon: ambIcon })
        .addTo(map)
        .bindTooltip("Ambulance", { direction: "top", className: "safereach-tooltip" });
    }
  }, [ambulanceLat, ambulanceLng]);

  return (
    <>
      <style>{`
        .safereach-tooltip {
          background: #0f172a !important;
          border: 1px solid #334155 !important;
          color: #e2e8f0 !important;
          font-size: 12px;
          border-radius: 6px;
        }
        .safereach-tooltip::before { display: none !important; }
      `}</style>
      <div ref={mapRef} style={{ width: "100%", height: "100%" }} />
    </>
  );
}
