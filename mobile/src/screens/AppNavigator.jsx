/**
 * SafeReach — App Navigator
 * React Navigation stack for both Victim and Crew app modes.
 * App mode is detected from SecureStore on first launch.
 */

import React, { useEffect, useState } from "react";
import { View, ActivityIndicator } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import * as SecureStore from "expo-secure-store";

// Victim app screens
import SOSScreen        from "./SOSScreen";
import SettingsScreen   from "./SettingsScreen";

// Crew app screens
import CrewDashboardScreen    from "./CrewDashboardScreen";
import CrewNavigationScreen   from "./CrewNavigationScreen";

// Onboarding
import OnboardingScreen from "./OnboardingScreen";

const Stack = createNativeStackNavigator();

const SCREEN_OPTIONS = {
  headerShown:      false,
  animation:        "slide_from_right",
  contentStyle:     { backgroundColor: "#0f172a" },
};

export default function AppNavigator() {
  const [appMode, setAppMode]     = useState(null); // "victim" | "crew" | null
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    (async () => {
      const mode = await SecureStore.getItemAsync("app_mode");
      setAppMode(mode || null);
      setLoading(false);
    })();
  }, []);

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: "#0f172a", justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color="#3b82f6" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator screenOptions={SCREEN_OPTIONS}>
        {appMode === null && (
          // First launch — choose mode
          <Stack.Screen name="Onboarding" component={OnboardingScreen} />
        )}

        {/* Victim mode screens */}
        {(appMode === "victim" || appMode === null) && (
          <>
            <Stack.Screen name="SOS"      component={SOSScreen}      />
            <Stack.Screen name="Settings" component={SettingsScreen}  />
          </>
        )}

        {/* Crew mode screens */}
        {appMode === "crew" && (
          <>
            <Stack.Screen name="CrewDashboard" component={CrewDashboardScreen}  />
            <Stack.Screen name="Navigation"    component={CrewNavigationScreen} />
            <Stack.Screen name="Settings"      component={SettingsScreen}        />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
