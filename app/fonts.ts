// Native font loading: the real Inter and Fraunces faces, bundled
// with the app by @expo-google-fonts. On web, fonts.web.ts replaces
// this file and the faces arrive through global.css instead.

import { useFonts } from "expo-font";
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
} from "@expo-google-fonts/inter";
import { Fraunces_600SemiBold } from "@expo-google-fonts/fraunces";

export function useAppFonts(): boolean {
  const [loaded] = useFonts({
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
    Fraunces_600SemiBold,
  });
  return loaded;
}
