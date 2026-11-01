import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as ImagePicker from "expo-image-picker";

import { useAppFonts } from "./fonts";

import { API_URL, absoluteUrl, fetchRecentScans, fetchScanResult, uploadPlatePhoto } from "./api";
import type { ScanResponse, ScanSummary } from "./api";
import { loadSavedRecipes } from "./storage";
import type { SavedRecipe } from "./storage";
import HomeScreen from "./screens/HomeScreen";
import AnalyzingScreen from "./screens/AnalyzingScreen";
import ResultScreen from "./screens/ResultScreen";
import { colors, fonts } from "./theme";

type Screen = "home" | "analyzing" | "result";

export default function App() {
  const fontsLoaded = useAppFonts();

  const [screen, setScreen] = useState<Screen>("home");
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [recentScans, setRecentScans] = useState<ScanSummary[]>([]);
  const [recentUnavailable, setRecentUnavailable] = useState(false);
  const [savedRecipes, setSavedRecipes] = useState<SavedRecipe[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refreshHome = useCallback(async () => {
    try {
      setRecentScans(await fetchRecentScans());
      setRecentUnavailable(false);
    } catch {
      setRecentUnavailable(true);
    }
    setSavedRecipes(await loadSavedRecipes());
  }, []);

  useEffect(() => {
    if (screen === "home") void refreshHome();
  }, [screen, refreshHome]);

  const startScan = useCallback((uri: string) => {
    setError(null);
    setPhotoUri(uri);
    setScreen("analyzing");
    uploadPlatePhoto(uri)
      .then((result) => {
        setScan(result);
        setScreen("result");
      })
      .catch(() => {
        setError(
          "That scan did not finish. Check the By Eye server is running, then try the photo again.",
        );
        setScreen("home");
      });
  }, []);

  const takePhoto = useCallback(async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      setError("Camera access is off. Allow it in settings, or use a photo you already have.");
      return;
    }
    const result = await ImagePicker.launchCameraAsync({ mediaTypes: ["images"], quality: 0.9 });
    if (!result.canceled) startScan(result.assets[0].uri);
  }, [startScan]);

  const pickPhoto = useCallback(async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.9,
    });
    if (!result.canceled) startScan(result.assets[0].uri);
  }, [startScan]);

  const openScan = useCallback(async (scanId: string) => {
    try {
      const result = await fetchScanResult(scanId);
      setScan(result);
      setPhotoUri(absoluteUrl(result.photo_url));
      setScreen("result");
    } catch {
      setError("That scan could not be loaded again. The server may have restarted.");
    }
  }, []);

  if (!fontsLoaded) {
    return (
      <View style={styles.loading}>
        <Text style={styles.loadingWordmark}>By Eye</Text>
        <StatusBar style="dark" />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      {screen === "home" && (
        <HomeScreen
          onScanPress={takePhoto}
          onPickPress={pickPhoto}
          onSamplePress={() => startScan(`${API_URL}/sample.jpg`)}
          recentScans={recentScans}
          recentUnavailable={recentUnavailable}
          savedRecipes={savedRecipes}
          onOpenScan={openScan}
          error={error}
        />
      )}
      {screen === "analyzing" && photoUri && <AnalyzingScreen photoUri={photoUri} />}
      {screen === "result" && scan && photoUri && (
        <ResultScreen
          scan={scan}
          photoUri={photoUri}
          onBack={() => setScreen("home")}
          onRecipesChanged={() => void loadSavedRecipes().then(setSavedRecipes)}
        />
      )}
      <StatusBar style={screen === "home" ? "dark" : "light"} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  loading: {
    flex: 1,
    backgroundColor: colors.paper,
    alignItems: "center",
    justifyContent: "center",
  },
  loadingWordmark: { fontFamily: fonts.display, fontSize: 30, color: colors.terracottaDeep },
});
