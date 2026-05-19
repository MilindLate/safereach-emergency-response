/**
 * SafeReach — Crew App: Navigation Screen
 * Ambulance driver receives dispatch, follows OSRM turn-by-turn route.
 * Location updates sent to backend every 30s via Socket.io.
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  View, Text, TouchableOpacity, StyleSheet,
  Platform, StatusBar, Alert, Vibration,
} from "react-native";
import MapView, { Marker, Polyline, PROVIDER_GOOGLE } from "react-native-maps";
import * as Location from "expo-location";
import * as SecureStore from "expo-secure-store";
import * as Notifications from "expo-notifications";

const API_BASE = process.env.EXPO_PUBLIC_API_URL || "https://api.safereach.in";
const LOCATION_UPDATE_INTERVAL_MS = 30_000; // 30s as per spec

export default function CrewNavigationScreen({ route, navigation }) {
  const { incidentId, routePolyline, severity, destinationLat, destinationLng } = route.params || {};

  const [currentLocation, setCurrentLocation]     = useState(null);
  const [decodedRoute, setDecodedRoute]           = useState([]);
  const [nextInstruction, setNextInstruction]     = useState("Follow route to incident");
  const [distanceRemaining, setDistanceRemaining] = useState(null);
  const [incidentStatus, setIncidentStatus]       = useState("en_route");
  const [isConnected, setIsConnected]             = useState(false);

  const mapRef      = useRef(null);
  const socketRef   = useRef(null);
  const locationSub = useRef(null);

  const unitId    = useRef(null);
  const unitToken = useRef(null);

  // ── Init ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      unitId.current    = await SecureStore.getItemAsync("unit_id");
      unitToken.current = await SecureStore.getItemAsync("device_token");

      await Location.requestForegroundPermissionsAsync();
      await Location.requestBackgroundPermissionsAsync();

      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.BestForNavigation });
      setCurrentLocation(loc.coords);

      // Decode polyline
      if (routePolyline) {
        setDecodedRoute(decodePolyline(routePolyline));
      }

      startLocationTracking();
      connectSocket();
    })();

    return () => {
      locationSub.current?.remove();
      socketRef.current?.disconnect();
    };
  }, []);

  // ── Location tracking (30s interval) ─────────────────────────────────────
  const startLocationTracking = useCallback(async () => {
    locationSub.current = await Location.watchPositionAsync(
      {
        accuracy:       Location.Accuracy.BestForNavigation,
        timeInterval:   LOCATION_UPDATE_INTERVAL_MS,
        distanceInterval: 50, // minimum 50m between updates
      },
      async (loc) => {
        setCurrentLocation(loc.coords);
        await sendLocationUpdate(loc.coords);
        updateNavigationProgress(loc.coords);
      }
    );
  }, []);

  const sendLocationUpdate = async (coords) => {
    if (!unitId.current || !unitToken.current) return;
    try {
      await fetch(`${API_BASE}/api/v1/ambulances/location`, {
        method:  "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization:  `Bearer ${unitToken.current}`,
        },
        body: JSON.stringify({
          unit_id:  unitId.current,
          location: { latitude: coords.latitude, longitude: coords.longitude, accuracy_meters: coords.accuracy },
          speed_kmh: coords.speed ? coords.speed * 3.6 : null,
        }),
      });
    } catch (err) {
      console.warn("Location update failed:", err);
    }
  };

  const updateNavigationProgress = (coords) => {
    if (!destinationLat || !destinationLng) return;
    const dist = haversineKm(coords.latitude, coords.longitude, destinationLat, destinationLng);
    setDistanceRemaining(dist);
    if (dist < 0.1) {
      setNextInstruction("🏁 You have arrived at the incident");
    }
  };

  const connectSocket = () => {
    if (!unitToken.current) return;
    try {
      const { io } = require("socket.io-client");
      const socket = io(API_BASE, { auth: { token: unitToken.current }, transports: ["websocket"] });
      socket.on("connect", () => {
        setIsConnected(true);
        if (unitId.current) socket.emit("join_room", `safereach:ambulance:${unitId.current}`);
      });
      socket.on("disconnect", () => setIsConnected(false));
      socket.on("route_updated", (data) => {
        // Re-route pushed by backend every 30s
        if (data.route_polyline) setDecodedRoute(decodePolyline(data.route_polyline));
      });
      socketRef.current = socket;
    } catch (err) {
      console.warn("Socket connection failed:", err);
    }
  };

  // ── Status updates ────────────────────────────────────────────────────────
  const handleArrivedAtScene = async () => {
    Alert.alert("Confirm Arrival", "Mark as arrived at accident scene?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Arrived",
        onPress: async () => {
          Vibration.vibrate(200);
          await updateIncidentStatus("on_scene");
          setIncidentStatus("on_scene");
          setNextInstruction("✅ On scene — provide care");
        },
      },
    ]);
  };

  const handleTransportToHospital = async () => {
    await updateIncidentStatus("hospital_handoff");
    setIncidentStatus("hospital_handoff");
    Alert.alert("Hospital Pre-Alert Sent", "The receiving hospital has been notified of your arrival.");
  };

  const updateIncidentStatus = async (newStatus) => {
    if (!incidentId || !unitToken.current) return;
    try {
      await fetch(`${API_BASE}/api/v1/dispatch/status/${incidentId}?new_status=${newStatus}`, {
        method:  "PUT",
        headers: { Authorization: `Bearer ${unitToken.current}` },
      });
    } catch (err) {
      console.warn("Status update failed:", err);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  const region = currentLocation
    ? {
        latitude:       currentLocation.latitude,
        longitude:      currentLocation.longitude,
        latitudeDelta:  0.01,
        longitudeDelta: 0.01,
      }
    : { latitude: 20.5937, longitude: 78.9629, latitudeDelta: 5, longitudeDelta: 5 };

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" />

      {/* Map */}
      <MapView
        ref={mapRef}
        provider={PROVIDER_GOOGLE}
        style={styles.map}
        region={region}
        showsUserLocation
        showsMyLocationButton={false}
        customMapStyle={darkMapStyle}
      >
        {/* Route polyline */}
        {decodedRoute.length > 0 && (
          <Polyline
            coordinates={decodedRoute}
            strokeColor="#3b82f6"
            strokeWidth={4}
          />
        )}

        {/* Destination marker */}
        {destinationLat && destinationLng && (
          <Marker
            coordinate={{ latitude: destinationLat, longitude: destinationLng }}
            title="Incident Location"
            pinColor="#dc2626"
          />
        )}
      </MapView>

      {/* Navigation HUD */}
      <View style={styles.hud}>
        <View style={styles.instructionBar}>
          <Text style={styles.instructionText}>{nextInstruction}</Text>
          {distanceRemaining !== null && (
            <Text style={styles.distanceText}>
              {distanceRemaining < 1
                ? `${Math.round(distanceRemaining * 1000)}m`
                : `${distanceRemaining.toFixed(1)}km`}
            </Text>
          )}
        </View>

        {/* Severity badge */}
        <View style={[styles.severityBadge, { backgroundColor: severity === "critical" ? "#7f1d1d" : severity === "medium" ? "#78350f" : "#14532d" }]}>
          <Text style={styles.severityText}>
            {severity?.toUpperCase()} — Incident {incidentId?.slice(0, 8)}
          </Text>
        </View>

        {/* Action buttons */}
        <View style={styles.actionRow}>
          {incidentStatus === "en_route" && (
            <TouchableOpacity style={styles.arrivedBtn} onPress={handleArrivedAtScene}>
              <Text style={styles.arrivedBtnText}>✅ Arrived at Scene</Text>
            </TouchableOpacity>
          )}
          {incidentStatus === "on_scene" && (
            <TouchableOpacity style={styles.hospitalBtn} onPress={handleTransportToHospital}>
              <Text style={styles.hospitalBtnText}>🏥 Transport to Hospital</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Connection status */}
        <View style={styles.connectionStatus}>
          <View style={[styles.dot, { backgroundColor: isConnected ? "#22c55e" : "#ef4444" }]} />
          <Text style={styles.connectionText}>{isConnected ? "Connected" : "Reconnecting…"}</Text>
        </View>
      </View>
    </View>
  );
}

// ── Utilities ──────────────────────────────────────────────────────────────────

function decodePolyline(encoded) {
  // Google polyline decoder
  const points = [];
  let index = 0, lat = 0, lng = 0;
  while (index < encoded.length) {
    let b, shift = 0, result = 0;
    do { b = encoded.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
    lat += (result & 1) ? ~(result >> 1) : result >> 1;
    shift = result = 0;
    do { b = encoded.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
    lng += (result & 1) ? ~(result >> 1) : result >> 1;
    points.push({ latitude: lat / 1e5, longitude: lng / 1e5 });
  }
  return points;
}

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

const darkMapStyle = [
  { elementType: "geometry", stylers: [{ color: "#0f172a" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#94a3b8" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#0f172a" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#1e293b" }] },
  { featureType: "road.arterial", elementType: "geometry", stylers: [{ color: "#334155" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#020617" }] },
];

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a" },
  map:       { flex: 1 },
  hud: {
    position: "absolute", bottom: 0, left: 0, right: 0,
    backgroundColor: "rgba(15,23,42,0.95)",
    borderTopLeftRadius: 20, borderTopRightRadius: 20,
    padding: 20, paddingBottom: Platform.OS === "android" ? 24 : 40,
    gap: 12,
  },
  instructionBar:  { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  instructionText: { fontSize: 15, fontWeight: "600", color: "#f8fafc", flex: 1 },
  distanceText:    { fontSize: 16, fontWeight: "700", color: "#60a5fa", marginLeft: 12 },
  severityBadge:   { padding: "6px 12px", borderRadius: 8, alignSelf: "flex-start" },
  severityText:    { fontSize: 11, fontWeight: "700", color: "#fff", letterSpacing: 0.8 },
  actionRow:       { gap: 10 },
  arrivedBtn:      { backgroundColor: "#14532d", padding: 16, borderRadius: 12, alignItems: "center", borderWidth: 1, borderColor: "#22c55e" },
  arrivedBtnText:  { fontSize: 15, fontWeight: "700", color: "#4ade80" },
  hospitalBtn:     { backgroundColor: "#1e3a5f", padding: 16, borderRadius: 12, alignItems: "center", borderWidth: 1, borderColor: "#3b82f6" },
  hospitalBtnText: { fontSize: 15, fontWeight: "700", color: "#60a5fa" },
  connectionStatus:{ flexDirection: "row", alignItems: "center", gap: 6 },
  dot:             { width: 8, height: 8, borderRadius: 4 },
  connectionText:  { fontSize: 11, color: "#64748b" },
});
