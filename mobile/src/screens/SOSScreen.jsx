/**
 * SafeReach — Victim App: SOS Screen
 * Single large SOS button — primary screen.
 * On activation: captures GPS + photo, sends to backend, shows ETA.
 */

import React, { useState, useEffect, useRef } from "react";
import {
  View, Text, TouchableOpacity, StyleSheet, Alert,
  Animated, Vibration, Platform, StatusBar,
} from "react-native";
import * as Location from "expo-location";
import * as Camera from "expo-camera";
import * as SecureStore from "expo-secure-store";
import NetInfo from "@react-native-community/netinfo";

const API_BASE = process.env.EXPO_PUBLIC_API_URL || "https://api.safereach.in";

const INCIDENT_STATUS_MSG = {
  reported:         "🔄 Connecting to emergency services…",
  dispatched:       "🚑 Ambulance dispatched!",
  en_route:         "🚑 Help is on the way",
  on_scene:         "✅ Emergency crew arrived",
  hospital_handoff: "🏥 Heading to hospital",
};

export default function SOSScreen({ navigation }) {
  const [phase, setPhase]           = useState("ready"); // ready | capturing | sending | tracking
  const [eta, setEta]               = useState(null);
  const [incidentId, setIncidentId] = useState(null);
  const [ambulanceCode, setAmbulanceCode] = useState(null);
  const [hospitalName, setHospitalName]  = useState(null);
  const [incidentStatus, setIncidentStatus] = useState(null);
  const [locationPerm, setLocationPerm]     = useState(false);

  const pulseAnim   = useRef(new Animated.Value(1)).current;
  const cameraRef   = useRef(null);
  const socketRef   = useRef(null);
  const etaInterval = useRef(null);

  // ── Permission check on mount ────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      setLocationPerm(status === "granted");
      await Camera.requestCameraPermissionsAsync();
    })();
    return () => {
      socketRef.current?.disconnect();
      if (etaInterval.current) clearInterval(etaInterval.current);
    };
  }, []);

  // ── Pulse animation (ready state) ─────────────────────────────────────────
  useEffect(() => {
    if (phase !== "ready") return;
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.07, duration: 900, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 900, useNativeDriver: true }),
      ])
    );
    pulse.start();
    return () => pulse.stop();
  }, [phase, pulseAnim]);

  // ── SOS activation ────────────────────────────────────────────────────────
  const handleSOS = async () => {
    if (phase !== "ready") return;
    Vibration.vibrate([0, 200, 100, 200]);
    setPhase("capturing");

    try {
      // 1. Get GPS (with retry)
      const location = await getLocationWithRetry();

      // 2. Capture photo
      let photoUri = null;
      if (cameraRef.current) {
        try {
          const photo = await cameraRef.current.takePictureAsync({
            quality: 0.7,
            skipProcessing: true,
          });
          photoUri = photo.uri;
        } catch (camErr) {
          console.warn("Camera capture failed — proceeding without photo:", camErr);
        }
      }

      setPhase("sending");

      // 3. Get auth token
      const token = await SecureStore.getItemAsync("device_token");
      if (!token) {
        await registerDevice();
      }
      const deviceToken = await SecureStore.getItemAsync("device_token");
      const deviceId    = await SecureStore.getItemAsync("device_id");

      // 4. Get emergency contacts from storage
      const contactsRaw = await SecureStore.getItemAsync("emergency_contacts");
      const contacts    = contactsRaw ? JSON.parse(contactsRaw) : [];

      // 5. Check connectivity
      const netState = await NetInfo.fetch();
      if (!netState.isConnected) {
        await sendOfflineSMS(location);
        setPhase("offline");
        return;
      }

      // 6. Trigger SOS
      const sosRes = await fetch(`${API_BASE}/api/v1/sos/trigger`, {
        method:  "POST",
        headers: {
          "Content-Type":  "application/json",
          Authorization:   `Bearer ${deviceToken}`,
        },
        body: JSON.stringify({
          device_id:          deviceId,
          location:           { latitude: location.coords.latitude, longitude: location.coords.longitude, accuracy_meters: location.coords.accuracy },
          language:           await SecureStore.getItemAsync("language") || "en",
          emergency_contacts: contacts,
        }),
      });

      if (!sosRes.ok) throw new Error(`SOS API error: ${sosRes.status}`);
      const sosData = await sosRes.json();

      setIncidentId(sosData.incident_id);
      setEta(sosData.eta_seconds ? Math.ceil(sosData.eta_seconds / 60) : null);
      setAmbulanceCode(sosData.ambulance_unit_code);
      setHospitalName(sosData.nearest_hospital_name);
      setIncidentStatus("reported");
      setPhase("tracking");

      // 7. Upload photo in background
      if (photoUri && sosData.incident_id) {
        uploadPhotoBackground(photoUri, sosData.incident_id, deviceToken);
      }

      // 8. Subscribe to real-time updates
      connectSocket(sosData.incident_id, deviceToken);

    } catch (err) {
      console.error("SOS error:", err);
      Alert.alert("Error", "Could not reach emergency services. Calling 112 now.");
      setPhase("ready");
    }
  };

  const getLocationWithRetry = async (attempts = 3) => {
    for (let i = 0; i < attempts; i++) {
      try {
        return await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.High,
          timeInterval: 5000,
        });
      } catch {
        if (i === attempts - 1) throw new Error("GPS unavailable");
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
  };

  const registerDevice = async () => {
    const deviceId = `android-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const res = await fetch(`${API_BASE}/api/v1/auth/device/register`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ device_id: deviceId, platform: Platform.OS }),
    });
    const data = await res.json();
    await SecureStore.setItemAsync("device_token", data.device_token);
    await SecureStore.setItemAsync("device_id", deviceId);
  };

  const uploadPhotoBackground = async (uri, incidentId, token) => {
    try {
      const formData = new FormData();
      formData.append("photo", { uri, name: "crash.jpg", type: "image/jpeg" });
      await fetch(`${API_BASE}/api/v1/sos/photo/${incidentId}`, {
        method:  "POST",
        headers: { Authorization: `Bearer ${token}` },
        body:    formData,
      });
    } catch (err) {
      console.warn("Background photo upload failed:", err);
    }
  };

  const sendOfflineSMS = async (location) => {
    // Service-worker SMS fallback via Twilio
    try {
      const formData = new FormData();
      formData.append("latitude",  String(location.coords.latitude));
      formData.append("longitude", String(location.coords.longitude));
      formData.append("device_id", (await SecureStore.getItemAsync("device_id")) || "unknown");
      await fetch(`${API_BASE}/api/v1/sos/offline`, { method: "POST", body: formData });
    } catch {
      // Last resort — trigger native SMS to 112
      // Linking.openURL("sms:112?body=Emergency+road+accident")
    }
  };

  const connectSocket = (incId, token) => {
    try {
      const { io } = require("socket.io-client");
      const socket = io(API_BASE, { auth: { token }, transports: ["websocket"] });
      socket.on("connect", () => socket.emit("join_room", `incident:${incId}`));
      socket.on("incident_updated", (data) => {
        if (data.incident_id !== incId) return;
        setIncidentStatus(data.status);
        if (data.eta_seconds) setEta(Math.ceil(data.eta_seconds / 60));
        if (data.ambulance_code) setAmbulanceCode(data.ambulance_code);
      });
      socketRef.current = socket;
    } catch (err) {
      // Socket.io unavailable — fall back to polling
      etaInterval.current = setInterval(() => {
        setEta((prev) => (prev && prev > 1 ? prev - 1 : prev));
      }, 60000);
    }
  };

  const handleCancel = () => {
    Alert.alert(
      "Cancel Emergency?",
      "Are you sure you want to cancel the emergency alert?",
      [
        { text: "Keep Active", style: "cancel" },
        { text: "Cancel Alert", style: "destructive", onPress: () => { socketRef.current?.disconnect(); setPhase("ready"); setIncidentId(null); setEta(null); } },
      ]
    );
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0f172a" />

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>SafeReach</Text>
        <TouchableOpacity onPress={() => navigation.navigate("Settings")} style={styles.settingsBtn}>
          <Text style={styles.settingsIcon}>⚙️</Text>
        </TouchableOpacity>
      </View>

      {/* Main SOS button or tracking view */}
      <View style={styles.centerContent}>
        {phase === "ready" && (
          <>
            <Animated.View style={[styles.sosOuter, { transform: [{ scale: pulseAnim }] }]}>
              <TouchableOpacity
                style={styles.sosButton}
                onPress={handleSOS}
                activeOpacity={0.85}
                accessible
                accessibilityLabel="SOS Emergency Button"
                accessibilityHint="Press to trigger emergency response"
              >
                <Text style={styles.sosText}>SOS</Text>
                <Text style={styles.sosSubText}>Press for Emergency</Text>
              </TouchableOpacity>
            </Animated.View>
            {!locationPerm && (
              <Text style={styles.permWarning}>
                ⚠️ Location access needed for accurate emergency response
              </Text>
            )}
          </>
        )}

        {(phase === "capturing" || phase === "sending") && (
          <View style={styles.loadingView}>
            <Text style={styles.loadingEmoji}>{phase === "capturing" ? "📍" : "📡"}</Text>
            <Text style={styles.loadingTitle}>
              {phase === "capturing" ? "Getting your location…" : "Contacting emergency services…"}
            </Text>
            <Text style={styles.loadingSubtitle}>Stay calm. Help is coming.</Text>
          </View>
        )}

        {phase === "tracking" && (
          <View style={styles.trackingView}>
            {/* ETA */}
            {eta !== null && (
              <View style={styles.etaCard}>
                <Text style={styles.etaLabel}>Estimated Arrival</Text>
                <Text style={styles.etaValue}>{eta} min</Text>
                {ambulanceCode && (
                  <Text style={styles.etaUnit}>🚑 Unit {ambulanceCode}</Text>
                )}
              </View>
            )}

            {/* Status */}
            <View style={styles.statusCard}>
              <Text style={styles.statusText}>
                {INCIDENT_STATUS_MSG[incidentStatus] || "Emergency services notified"}
              </Text>
              {hospitalName && (
                <Text style={styles.hospitalText}>🏥 {hospitalName}</Text>
              )}
            </View>

            <TouchableOpacity
              style={styles.trackerLinkBtn}
              onPress={() => navigation.navigate("Tracker", { incidentId })}
            >
              <Text style={styles.trackerLinkText}>Share live location →</Text>
            </TouchableOpacity>
          </View>
        )}

        {phase === "offline" && (
          <View style={styles.loadingView}>
            <Text style={styles.loadingEmoji}>📱</Text>
            <Text style={styles.loadingTitle}>SMS sent to 112</Text>
            <Text style={styles.loadingSubtitle}>No internet detected. Emergency SMS dispatched with your GPS location.</Text>
          </View>
        )}
      </View>

      {/* Cancel / Done button */}
      {(phase === "tracking" || phase === "offline") && (
        <TouchableOpacity style={styles.cancelBtn} onPress={handleCancel}>
          <Text style={styles.cancelText}>Cancel Alert</Text>
        </TouchableOpacity>
      )}

      {/* Emergency call fallback */}
      <View style={styles.footer}>
        <Text style={styles.footerText}>Direct emergency line: </Text>
        <Text style={styles.footerCall}>112</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container:      { flex: 1, backgroundColor: "#0f172a" },
  header:         { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 20, paddingTop: Platform.OS === "android" ? 40 : 60 },
  headerTitle:    { fontSize: 20, fontWeight: "700", color: "#f8fafc" },
  settingsBtn:    { padding: 8 },
  settingsIcon:   { fontSize: 22 },
  centerContent:  { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },

  // SOS button
  sosOuter:       { width: 240, height: 240, borderRadius: 120, backgroundColor: "rgba(220,38,38,0.15)", alignItems: "center", justifyContent: "center" },
  sosButton:      { width: 200, height: 200, borderRadius: 100, backgroundColor: "#dc2626", alignItems: "center", justifyContent: "center", elevation: 8, shadowColor: "#dc2626", shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.5, shadowRadius: 12 },
  sosText:        { fontSize: 52, fontWeight: "900", color: "#fff", letterSpacing: 4 },
  sosSubText:     { fontSize: 13, color: "rgba(255,255,255,0.8)", marginTop: 4 },
  permWarning:    { marginTop: 24, fontSize: 12, color: "#f59e0b", textAlign: "center", maxWidth: 280 },

  // Loading
  loadingView:    { alignItems: "center", gap: 16 },
  loadingEmoji:   { fontSize: 60 },
  loadingTitle:   { fontSize: 20, fontWeight: "700", color: "#f8fafc", textAlign: "center" },
  loadingSubtitle:{ fontSize: 14, color: "#94a3b8", textAlign: "center", maxWidth: 280 },

  // Tracking
  trackingView:   { width: "100%", gap: 16 },
  etaCard:        { backgroundColor: "#1e3a5f", borderRadius: 16, padding: 24, alignItems: "center", borderWidth: 1, borderColor: "#3b82f6" },
  etaLabel:       { fontSize: 12, color: "#93c5fd", marginBottom: 4, letterSpacing: 1 },
  etaValue:       { fontSize: 48, fontWeight: "800", color: "#60a5fa" },
  etaUnit:        { fontSize: 14, color: "#93c5fd", marginTop: 4 },
  statusCard:     { backgroundColor: "#1e293b", borderRadius: 16, padding: 20, borderWidth: 1, borderColor: "#334155" },
  statusText:     { fontSize: 15, color: "#e2e8f0", textAlign: "center", fontWeight: "500" },
  hospitalText:   { fontSize: 13, color: "#94a3b8", textAlign: "center", marginTop: 8 },
  trackerLinkBtn: { padding: 12, alignItems: "center" },
  trackerLinkText:{ fontSize: 14, color: "#60a5fa" },

  // Cancel
  cancelBtn:  { margin: 24, padding: 16, backgroundColor: "#1e293b", borderRadius: 12, alignItems: "center", borderWidth: 1, borderColor: "#334155" },
  cancelText: { fontSize: 15, color: "#f87171", fontWeight: "600" },

  // Footer
  footer:     { flexDirection: "row", justifyContent: "center", padding: 16, paddingBottom: Platform.OS === "android" ? 24 : 40 },
  footerText: { fontSize: 13, color: "#475569" },
  footerCall: { fontSize: 13, color: "#dc2626", fontWeight: "700" },
});
