// Saved recipes live on the device, in AsyncStorage. A saved recipe
// keeps the item names and amounts as measured, so it reads like a
// recipe card, plus the photo URL from the scan it came from.

import AsyncStorage from "@react-native-async-storage/async-storage";

import type { ScanResponse } from "./api";

const KEY = "byeye.savedRecipes.v1";

export interface SavedRecipe {
  id: string;
  savedAt: string;
  title: string;
  photoUrl: string | null;
  items: { name: string; amountLabel: string | null; bandLabel: string | null }[];
}

export function recipeTitle(scan: ScanResponse): string {
  const names = scan.items.map((i) => i.name);
  if (names.length === 0) return "A plate, measured";
  if (names.length <= 2) return names.join(" and ");
  return `${names[0]}, ${names[1]} and ${names.length - 2} more`;
}

export async function loadSavedRecipes(): Promise<SavedRecipe[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as SavedRecipe[]) : [];
  } catch {
    return [];
  }
}

export async function saveRecipe(scan: ScanResponse): Promise<SavedRecipe[]> {
  const existing = await loadSavedRecipes();
  const recipe: SavedRecipe = {
    id: scan.scan_id,
    savedAt: new Date().toISOString(),
    title: recipeTitle(scan),
    photoUrl: scan.photo_url ?? null,
    items: scan.items.map((i) => ({
      name: i.name,
      amountLabel: i.amount_label,
      bandLabel: i.band_label,
    })),
  };
  const next = [recipe, ...existing.filter((r) => r.id !== recipe.id)];
  await AsyncStorage.setItem(KEY, JSON.stringify(next));
  return next;
}
