/**
 * SafeReach — Crew Dashboard Screen
 * Shows pending dispatch, unit status, and shift summary for ambulance crew.
 * Listens for Socket.io dispatch events and navigates to navigation screen.
 */

import React, { useEffect, useState, useRef } from "react";
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  Platform, StatusBar, Vibration, Alert,
} from "react-native";
import * as SecureStore from "expo-secure-store";
import * as Notifications from "expo-notifications";

const API_BASE = process.env.EXPO_PUBLIC_API_URL || "https://api.safereach.in";

const STATUS_COLORS = {
  free:     "#22c55e",
  routing:  "#60a5fa",
  on_scene: "#f97316",
};

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowAlert: true, shouldPlaySound: true, shouldSetBadge: true }),
});

export default function CrewDashboardScreen({ navigation }) {
  const [unitStatus, setUnitStatus]     = useState("free");
  const [unitCode, setUnitCode]         = useState("—");
  const [activeDispatch, setActiveDispatch] = useState(null);
  const [shiftStats, setShiftStats]     = useState({ dispatches: 0, on_time_pct: 100 });
  const [isConnected, setIsConnected]   = useState(false);

  const socketRef  = useRef(null);
  const unitIdRef  = useRef(null);
  const tokenRef   = useRef(null);

  // ── Init + socket ─────────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      unitIdRef.current  = await SecureStore.getItemAsync("unit_id");
      tokenRef.current   = await SecureStore.getItemAsync("device_token");
      const code = await SecureStore.getItemAsync("unit_code");
      if (code) setUnitCode(code);

      await Notifications.requestPermissionsAsync();
      connectSocket();
    })();

    return () => socketRef.current?.disconnect();
  }, []);

  const connectSocket = () => {
    if (!tokenRef.current) return;
    try {
      const { io } = require("socket.io-client");
      const socket = io(API_BASE, { auth: { token: tokenRef.current }, transports: ["websocket"] });

      socket.on("connect", () => {
        setIsConnected(true);
        if (unitIdRef.current) {
          socket.emit("join_room", `safereach:ambulance:${unitIdRef.current}`);
        }
      });
      socket.on("disconnect", () => setIsConnected(false));

      socket.on("dispatch", (data) => {
        // New incident dispatched to this unit
        Vibration.vibrate([0, 300, 100, 300, 100, 300]);
        setActiveDispatch(data);
        setUnitStatus("routing");

        // Local push notification for background state
        Notifications.scheduleNotificationAsync({
          content: {
            title:    `🚨 DISPATCH — ${data.severity?.toUpperCase()}`,
            body:     "New incident assigned. Open SafeReach now.",
            sound:    true,
            priority: Notifications.AndroidNotificationPriority.MAX,
          },
          trigger: null,
        });

        // Alert if app is foregrounded
        Alert.alert(
          `🚨 DISPATCH — ${data.severity?.toUpperCase()}`,
          "New incident assigned. Navigate to scene immediately.",
          [
            { text: "Navigate Now", onPress: () => goToNavigation(data) },
          ],
          { cancelable: false }
        );
      });

      socket.on("dispatch_cancelled", () => {
        setActiveDispatch(null);
        setUnitStatus("free");
      });

      socketRef.current = socket;
    } catch (err) {
      console.warn("Socket.io unavailable:", err);
    }
  };

  const goToNavigation = (dispatch) => {
    navigation.navigate("Navigation", {
      incidentId:     dispatch.incident_id,
      routePolyline:  dispatch.route_polyline,
      severity:       dispatch.severity,
      destinationLat: dispatch.destination_lat,
      destinationLng: dispatch.destination_lng,
    });
  };

  const handleMarkAvailable = async () => {
    setUnitStatus("free");
    setActiveDispatch(null);
    // Notify backend
    if (unitIdRef.current && tokenRef.current) {
      try {
        await fetch(`${API_BASE}/api/v1/ambulances/status`, {
          method:  "PUT",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenRef.current}` },
          body:    JSON.stringify({ unit_id: unitIdRef.current, status: "free" }),
        });
      } catch {}
    }
  };

  const statusColor = STATUS_COLORS[unitStatus] || "#64748b";

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0f172a" />

      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>SafeReach Crew</Text>
          <Text style={styles.headerUnit}>Unit {unitCode}</Text>
        </View>
        <View style={styles.connectionPill}>
          <View style={[styles.dot, { backgroundColor: isConnected ? "#22c55e" : "#ef4444" }]} />
          <Text style={styles.connectionText}>{isConnected ? "Live" : "Reconnecting"}</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Unit Status Card */}
        <View style={[styles.statusCard, { borderColor: statusColor }]}>
          <Text style={styles.statusLabel}>Unit Status</Text>
          <View style={styles.statusRow}>
            <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.statusValue, { color: statusColor }]}>
              {unitStatus === "free"     ? "Available"  :
               unitStatus === "routing"  ? "En Route"   :
               unitStatus === "on_scene" ? "On Scene"   : unitStatus}
            </Text>
          </View>
        </View>

        {/* Active Dispatch */}
        {activeDispatch ? (
          <View style={styles.dispatchCard}>
            <Text style={styles.dispatchTitle}>🚨 Active Dispatch</Text>
            <View style={styles.dispatchRow}>
              <Text style={styles.dispatchLabel}>Severity</Text>
              <Text style={[styles.dispatchValue, { color: activeDispatch.severity === "critical" ? "#dc2626" : "#f97316" }]}>
                {activeDispatch.severity?.toUpperCase()}
              </Text>
            </View>
            <View style={styles.dispatchRow}>
              <Text style={styles.dispatchLabel}>Incident ID</Text>
              <Text style={styles.dispatchValue}>{activeDispatch.incident_id?.slice(0, 8)}…</Text>
            </View>

            <View style={styles.actionButtons}>
              <TouchableOpacity
                style={styles.navBtn}
                onPress={() => goToNavigation(activeDispatch)}
              >
                <Text style={styles.navBtnText}>🗺 Open Navigation</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.availBtn} onPress={handleMarkAvailable}>
                <Text style={styles.availBtnText}>Mark Available</Text>
              </TouchableOpacity>
            </View>
          </View>
        ) : (
          <View style={styles.waitingCard}>
            <Text style={styles.waitingIcon}>📡</Text>
            <Text style={styles.waitingTitle}>Listening for dispatches</Text>
            <Text style={styles.waitingDesc}>
              You'll be alerted the moment a new incident is assigned to your unit.
            </Text>
          </View>
        )}

        {/* Shift Stats */}
        <View style={styles.statsCard}>
          <Text style={styles.statsTitle}>Today's Shift</Text>
          <View style={styles.statsRow}>
            <StatItem label="Dispatches" value={String(shiftStats.dispatches)} />
            <StatItem label="On-Time %" value={`${shiftStats.on_time_pct}%`} />
          </View>
        </View>

        {/* Settings link */}
        <TouchableOpacity
          style={styles.settingsLink}
          onPress={() => navigation.navigate("Settings")}
        >
          <Text style={styles.settingsLinkText}>⚙️  Unit Settings</Text>
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
}

function StatItem({ label, value }) {
  return (
    <View style={styles.statItem}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container:     { flex: 1, backgroundColor: "#0f172a" },
  header:        { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 20, paddingTop: Platform.OS === "android" ? 40 : 60, borderBottomWidth: 1, borderBottomColor: "#1e293b" },
  headerTitle:   { fontSize: 20, fontWeight: "700", color: "#f8fafc" },
  headerUnit:    { fontSize: 13, color: "#64748b", marginTop: 2 },
  connectionPill:{ flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: "#1e293b", paddingHorizontal: 12, paddingVertical: 6, borderRadius: 99 },
  dot:           { width: 8, height: 8, borderRadius: 4 },
  connectionText:{ fontSize: 12, color: "#94a3b8" },

  content:       { padding: 20, gap: 16 },

  statusCard:    { backgroundColor: "#1e293b", borderRadius: 16, padding: 20, borderWidth: 1.5 },
  statusLabel:   { fontSize: 12, color: "#64748b", marginBottom: 8 },
  statusRow:     { flexDirection: "row", alignItems: "center", gap: 10 },
  statusDot:     { width: 12, height: 12, borderRadius: 6 },
  statusValue:   { fontSize: 22, fontWeight: "700" },

  dispatchCard:  { backgroundColor: "#1e293b", borderRadius: 16, padding: 20, borderWidth: 1.5, borderColor: "#dc2626" },
  dispatchTitle: { fontSize: 16, fontWeight: "700", color: "#f8fafc", marginBottom: 14 },
  dispatchRow:   { flexDirection: "row", justifyContent: "space-between", marginBottom: 10 },
  dispatchLabel: { fontSize: 13, color: "#64748b" },
  dispatchValue: { fontSize: 13, fontWeight: "600", color: "#e2e8f0" },
  actionButtons: { gap: 10, marginTop: 12 },
  navBtn:        { backgroundColor: "#1e3a5f", padding: 14, borderRadius: 12, alignItems: "center", borderWidth: 1, borderColor: "#3b82f6" },
  navBtnText:    { fontSize: 14, fontWeight: "700", color: "#60a5fa" },
  availBtn:      { padding: 12, borderRadius: 12, alignItems: "center", borderWidth: 1, borderColor: "#334155" },
  availBtnText:  { fontSize: 13, color: "#64748b" },

  waitingCard:   { backgroundColor: "#1e293b", borderRadius: 16, padding: 32, alignItems: "center", gap: 8 },
  waitingIcon:   { fontSize: 40, marginBottom: 4 },
  waitingTitle:  { fontSize: 15, fontWeight: "600", color: "#e2e8f0" },
  waitingDesc:   { fontSize: 13, color: "#64748b", textAlign: "center" },

  statsCard:     { backgroundColor: "#1e293b", borderRadius: 16, padding: 20 },
  statsTitle:    { fontSize: 13, fontWeight: "600", color: "#94a3b8", marginBottom: 14 },
  statsRow:      { flexDirection: "row", gap: 16 },
  statItem:      { flex: 1, alignItems: "center" },
  statValue:     { fontSize: 28, fontWeight: "800", color: "#f8fafc" },
  statLabel:     { fontSize: 11, color: "#64748b", marginTop: 2 },

  settingsLink:  { padding: 16, alignItems: "center" },
  settingsLinkText: { fontSize: 14, color: "#475569" },
});
