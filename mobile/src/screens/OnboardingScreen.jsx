/**
 * SafeReach — Onboarding Screen
 * First-launch screen: choose Victim app or Crew app mode.
 * Sets app_mode in SecureStore, triggers device registration.
 */

import React, { useState } from "react";
import {
  View, Text, TouchableOpacity, StyleSheet, Platform,
  StatusBar, Alert,
} from "react-native";
import * as SecureStore from "expo-secure-store";

const API_BASE = process.env.EXPO_PUBLIC_API_URL || "https://api.safereach.in";

export default function OnboardingScreen({ navigation }) {
  const [loading, setLoading] = useState(false);

  const selectMode = async (mode) => {
    setLoading(true);
    try {
      // Generate device ID
      const deviceId = `${mode}-${Platform.OS}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      await SecureStore.setItemAsync("device_id", deviceId);
      await SecureStore.setItemAsync("app_mode", mode);

      // Register device with backend
      const res = await fetch(`${API_BASE}/api/v1/auth/device/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ device_id: deviceId, platform: Platform.OS }),
      });

      if (res.ok) {
        const { device_token } = await res.json();
        await SecureStore.setItemAsync("device_token", device_token);
      }

      // Navigate to the appropriate home screen
      if (mode === "victim") {
        navigation.replace("SOS");
      } else {
        navigation.replace("CrewDashboard");
      }
    } catch (err) {
      Alert.alert("Connection Error", "Could not register device. You can still use offline SOS.");
      if (mode === "victim") navigation.replace("SOS");
      else navigation.replace("CrewDashboard");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0f172a" />

      <View style={styles.hero}>
        <Text style={styles.emoji}>🚨</Text>
        <Text style={styles.title}>SafeReach</Text>
        <Text style={styles.subtitle}>
          AI-powered emergency response for road accidents
        </Text>
      </View>

      <View style={styles.modeSection}>
        <Text style={styles.modePrompt}>Select your role</Text>

        <TouchableOpacity
          style={[styles.modeCard, styles.victimCard]}
          onPress={() => selectMode("victim")}
          disabled={loading}
          activeOpacity={0.8}
        >
          <Text style={styles.modeIcon}>🧍</Text>
          <View style={styles.modeText}>
            <Text style={styles.modeTitle}>I'm a Road User</Text>
            <Text style={styles.modeDesc}>
              One-tap SOS, photo capture, live family tracker
            </Text>
          </View>
          <Text style={styles.modeArrow}>→</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.modeCard, styles.crewCard]}
          onPress={() => selectMode("crew")}
          disabled={loading}
          activeOpacity={0.8}
        >
          <Text style={styles.modeIcon}>🚑</Text>
          <View style={styles.modeText}>
            <Text style={styles.modeTitle}>I'm Ambulance Crew</Text>
            <Text style={styles.modeDesc}>
              Receive dispatches, turn-by-turn navigation, status updates
            </Text>
          </View>
          <Text style={styles.modeArrow}>→</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.footer}>
        {loading ? "Registering device…" : "Team CtrlAltElite · CoERS IIT Madras 2026"}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container:    { flex: 1, backgroundColor: "#0f172a", paddingTop: Platform.OS === "android" ? 40 : 60 },
  hero:         { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  emoji:        { fontSize: 64, marginBottom: 16 },
  title:        { fontSize: 36, fontWeight: "900", color: "#f8fafc", letterSpacing: -1 },
  subtitle:     { fontSize: 15, color: "#94a3b8", textAlign: "center", marginTop: 8, maxWidth: 280 },
  modeSection:  { padding: 24, gap: 14 },
  modePrompt:   { fontSize: 13, color: "#64748b", marginBottom: 4 },
  modeCard: {
    flexDirection: "row", alignItems: "center", gap: 16,
    padding: 18, borderRadius: 16, borderWidth: 1,
  },
  victimCard:   { backgroundColor: "#1e293b", borderColor: "#334155" },
  crewCard:     { backgroundColor: "#1e3a5f", borderColor: "#1d4ed8" },
  modeIcon:     { fontSize: 32 },
  modeText:     { flex: 1 },
  modeTitle:    { fontSize: 15, fontWeight: "700", color: "#f8fafc", marginBottom: 3 },
  modeDesc:     { fontSize: 12, color: "#94a3b8" },
  modeArrow:    { fontSize: 18, color: "#475569" },
  footer:       { textAlign: "center", color: "#334155", fontSize: 11, padding: 20, paddingBottom: Platform.OS === "android" ? 28 : 44 },
});
