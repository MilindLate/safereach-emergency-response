/**
 * SafeReach — Settings Screen
 * Emergency contact setup, language selection, device registration.
 */

import React, { useState, useEffect } from "react";
import {
  View, Text, TextInput, TouchableOpacity, ScrollView,
  StyleSheet, Alert, Platform, Switch,
} from "react-native";
import * as SecureStore from "expo-secure-store";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिन्दी (Hindi)" },
  { code: "mr", label: "मराठी (Marathi)" },
  { code: "ta", label: "தமிழ் (Tamil)" },
  { code: "te", label: "తెలుగు (Telugu)" },
  { code: "bn", label: "বাংলা (Bengali)" },
  { code: "kn", label: "ಕನ್ನಡ (Kannada)" },
];

export default function SettingsScreen({ navigation }) {
  const [contacts, setContacts]     = useState(["", "", ""]);
  const [language, setLanguage]     = useState("en");
  const [voiceSOS, setVoiceSOS]     = useState(true);
  const [deviceId, setDeviceId]     = useState("");
  const [isSaving, setIsSaving]     = useState(false);

  useEffect(() => {
    (async () => {
      const stored = await SecureStore.getItemAsync("emergency_contacts");
      if (stored) setContacts(JSON.parse(stored).concat(["", "", ""]).slice(0, 3));

      const lang = await SecureStore.getItemAsync("language");
      if (lang) setLanguage(lang);

      const did = await SecureStore.getItemAsync("device_id");
      if (did) setDeviceId(did.slice(-8));

      const voice = await SecureStore.getItemAsync("voice_sos");
      setVoiceSOS(voice !== "false");
    })();
  }, []);

  const handleSave = async () => {
    const validContacts = contacts.filter((c) => c.trim().length >= 10);
    if (validContacts.length === 0) {
      Alert.alert("No Contacts", "Please add at least one emergency contact phone number.");
      return;
    }

    setIsSaving(true);
    await SecureStore.setItemAsync("emergency_contacts", JSON.stringify(validContacts));
    await SecureStore.setItemAsync("language", language);
    await SecureStore.setItemAsync("voice_sos", String(voiceSOS));
    setIsSaving(false);

    Alert.alert("Saved", "Settings saved. Your emergency contacts will be notified during an SOS.");
    navigation.goBack();
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.backBtn}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Settings</Text>
        <View style={{ width: 50 }} />
      </View>

      {/* Emergency Contacts */}
      <Section title="Emergency Contacts" subtitle="Up to 3 numbers — notified instantly on SOS">
        {contacts.map((c, i) => (
          <TextInput
            key={i}
            style={styles.input}
            placeholder={`Contact ${i + 1} phone number`}
            placeholderTextColor="#475569"
            value={c}
            onChangeText={(v) => {
              const updated = [...contacts];
              updated[i] = v;
              setContacts(updated);
            }}
            keyboardType="phone-pad"
            maxLength={15}
          />
        ))}
      </Section>

      {/* Language */}
      <Section title="Language" subtitle="For voice SOS and notifications">
        <View style={styles.langGrid}>
          {LANGUAGES.map((lang) => (
            <TouchableOpacity
              key={lang.code}
              style={[styles.langChip, language === lang.code && styles.langChipActive]}
              onPress={() => setLanguage(lang.code)}
            >
              <Text style={[styles.langChipText, language === lang.code && styles.langChipTextActive]}>
                {lang.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </Section>

      {/* Voice SOS */}
      <Section title="Voice SOS" subtitle='Say "Help, emergency" to trigger SOS hands-free'>
        <View style={styles.toggleRow}>
          <Text style={styles.toggleLabel}>Enable Voice SOS</Text>
          <Switch
            value={voiceSOS}
            onValueChange={setVoiceSOS}
            trackColor={{ false: "#334155", true: "#1e3a5f" }}
            thumbColor={voiceSOS ? "#3b82f6" : "#64748b"}
          />
        </View>
        <Text style={styles.voiceNote}>
          Uses on-device Whisper AI — no audio sent to servers.
        </Text>
      </Section>

      {/* Device Info */}
      {deviceId && (
        <Section title="Device" subtitle="Your registered device ID">
          <Text style={styles.deviceId}>…{deviceId}</Text>
        </Section>
      )}

      {/* Save */}
      <TouchableOpacity
        style={[styles.saveBtn, isSaving && styles.saveBtnDisabled]}
        onPress={handleSave}
        disabled={isSaving}
      >
        <Text style={styles.saveBtnText}>{isSaving ? "Saving…" : "Save Settings"}</Text>
      </TouchableOpacity>

      <Text style={styles.footer}>SafeReach v1.0.0 · Team CtrlAltElite</Text>
    </ScrollView>
  );
}

function Section({ title, subtitle, children }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.sectionSubtitle}>{subtitle}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a" },
  content:   { padding: 20, paddingBottom: 60, paddingTop: Platform.OS === "android" ? 40 : 60 },
  header:    { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 28 },
  backBtn:   { fontSize: 15, color: "#60a5fa" },
  title:     { fontSize: 18, fontWeight: "700", color: "#f8fafc" },
  section:   { marginBottom: 28 },
  sectionTitle:    { fontSize: 14, fontWeight: "700", color: "#e2e8f0", marginBottom: 2, letterSpacing: 0.5 },
  sectionSubtitle: { fontSize: 12, color: "#64748b", marginBottom: 12 },
  input: {
    backgroundColor: "#1e293b", borderWidth: 1, borderColor: "#334155",
    borderRadius: 10, padding: 14, color: "#e2e8f0", fontSize: 14,
    marginBottom: 10,
  },
  langGrid:        { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  langChip:        { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 99, backgroundColor: "#1e293b", borderWidth: 1, borderColor: "#334155" },
  langChipActive:  { backgroundColor: "#1e3a5f", borderColor: "#3b82f6" },
  langChipText:    { fontSize: 12, color: "#94a3b8" },
  langChipTextActive: { color: "#93c5fd", fontWeight: "600" },
  toggleRow:       { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  toggleLabel:     { fontSize: 14, color: "#e2e8f0" },
  voiceNote:       { fontSize: 12, color: "#475569", marginTop: 8 },
  deviceId:        { fontSize: 13, color: "#64748b", fontFamily: "monospace" },
  saveBtn:         { backgroundColor: "#3b82f6", padding: 18, borderRadius: 14, alignItems: "center", marginTop: 8 },
  saveBtnDisabled: { opacity: 0.6 },
  saveBtnText:     { fontSize: 16, fontWeight: "700", color: "#fff" },
  footer:          { textAlign: "center", color: "#334155", fontSize: 11, marginTop: 32 },
});
