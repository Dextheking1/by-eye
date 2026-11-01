// Talks to the By Eye plate server (~/workspace/by-eye/server).
// Set EXPO_PUBLIC_API_URL when the phone is not on the dev machine.

import { Platform } from "react-native";

export const API_URL: string =
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ScanItem {
  id: string;
  name: string;
  amount: number | null;
  unit: string;
  amount_label: string | null;
  band_low: number | null;
  band_high: number | null;
  band_label: string | null;
  support: string;
  publishable: boolean;
  note: string;
  coverage_percent: number | null;
  box: { x: number; y: number; w: number; h: number } | null;
  anchor: { x: number; y: number } | null;
  outlines: { d: string; tx: number; ty: number }[];
  mask_url: string | null;
}

export interface ScanResponse {
  scan_id: string;
  photo_url: string;
  overlay_url: string;
  created_at: string;
  credit: string;
  image: { width: number; height: number };
  items: ScanItem[];
}

export interface ScanSummary {
  scan_id: string;
  created_at: string;
  item_count: number;
  photo_url: string;
  overlay_url: string;
}

export function absoluteUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_URL}${path}`;
}

export async function fetchRecentScans(): Promise<ScanSummary[]> {
  const res = await fetch(`${API_URL}/scans`);
  if (!res.ok) throw new Error("server said no");
  const body = await res.json();
  return body.scans as ScanSummary[];
}

export async function fetchScanResult(scanId: string): Promise<ScanResponse> {
  const res = await fetch(`${API_URL}/scans/${scanId}/result.json`);
  if (!res.ok) throw new Error("server said no");
  return (await res.json()) as ScanResponse;
}

export async function uploadPlatePhoto(photoUri: string): Promise<ScanResponse> {
  const form = new FormData();
  if (Platform.OS === "web") {
    const blob = await (await fetch(photoUri)).blob();
    form.append("photo", blob, "plate.jpg");
  } else {
    form.append("photo", {
      uri: photoUri,
      name: "plate.jpg",
      type: "image/jpeg",
    } as unknown as Blob);
  }
  const res = await fetch(`${API_URL}/scan`, { method: "POST", body: form });
  if (!res.ok) {
    throw new Error(`scan failed with ${res.status}`);
  }
  return (await res.json()) as ScanResponse;
}
