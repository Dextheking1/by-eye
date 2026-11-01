import { Image, ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import type { ScanSummary } from "../api";
import { absoluteUrl } from "../api";
import type { SavedRecipe } from "../storage";
import { colors, fonts, radius, space } from "../theme";

interface Props {
  onScanPress: () => void;
  onPickPress: () => void;
  onSamplePress: () => void;
  recentScans: ScanSummary[];
  recentUnavailable: boolean;
  savedRecipes: SavedRecipe[];
  onOpenScan: (scanId: string) => void;
  error: string | null;
}

function whenLabel(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function HomeScreen({
  onScanPress,
  onPickPress,
  onSamplePress,
  recentScans,
  recentUnavailable,
  savedRecipes,
  onOpenScan,
  error,
}: Props) {
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.wordmark}>By Eye</Text>
      <Text style={styles.headline}>What is on your plate, measured.</Text>
      <Text style={styles.lede}>
        Take a photo of your plate. By Eye finds everything on it and measures each item, so a
        recipe cooked by feel becomes a recipe written down.
      </Text>

      <TouchableOpacity style={styles.primary} activeOpacity={0.88} onPress={onScanPress}>
        <Text style={styles.primaryText}>Scan your plate</Text>
      </TouchableOpacity>
      <View style={styles.secondaryRow}>
        <TouchableOpacity style={styles.secondary} activeOpacity={0.85} onPress={onPickPress}>
          <Text style={styles.secondaryText}>Use a photo instead</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.secondary} activeOpacity={0.85} onPress={onSamplePress}>
          <Text style={styles.secondaryText}>Try a sample plate</Text>
        </TouchableOpacity>
      </View>

      {error && <Text style={styles.error}>{error}</Text>}

      <Text style={styles.sectionTitle}>Recent scans</Text>
      {recentUnavailable ? (
        <Text style={styles.quiet}>
          Recent scans live on the By Eye server. Start the server and they will show up here.
        </Text>
      ) : recentScans.length === 0 ? (
        <Text style={styles.quiet}>Nothing scanned yet. Your plates will appear here.</Text>
      ) : (
        recentScans.slice(0, 4).map((scan) => (
          <TouchableOpacity
            key={scan.scan_id}
            style={styles.row}
            activeOpacity={0.85}
            onPress={() => onOpenScan(scan.scan_id)}
          >
            <Image source={{ uri: absoluteUrl(scan.photo_url) }} style={styles.thumb} />
            <View style={styles.rowText}>
              <Text style={styles.rowTitle}>
                {scan.item_count} item{scan.item_count === 1 ? "" : "s"} measured
              </Text>
              <Text style={styles.rowSub}>{whenLabel(scan.created_at)}</Text>
            </View>
            <Text style={styles.rowChevron}>›</Text>
          </TouchableOpacity>
        ))
      )}

      {savedRecipes.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Your saved recipes</Text>
          {savedRecipes.slice(0, 4).map((recipe) => (
            <View key={recipe.id} style={styles.row}>
              {recipe.photoUrl ? (
                <Image source={{ uri: absoluteUrl(recipe.photoUrl) }} style={styles.thumb} />
              ) : (
                <View style={[styles.thumb, styles.thumbEmpty]} />
              )}
              <View style={styles.rowText}>
                <Text style={styles.rowTitle} numberOfLines={1}>
                  {recipe.title}
                </Text>
                <Text style={styles.rowSub}>
                  {recipe.items.length} items, saved {whenLabel(recipe.savedAt)}
                </Text>
              </View>
            </View>
          ))}
        </>
      )}

      <Text style={styles.credit}>Measured by SAM 3.1 and Muse Spark</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.paper },
  content: { padding: space.lg, paddingTop: space.xxl, paddingBottom: space.xl },
  wordmark: {
    fontFamily: fonts.display,
    fontSize: 30,
    lineHeight: 36,
    color: colors.terracottaDeep,
  },
  headline: {
    fontFamily: fonts.display,
    fontSize: 30,
    lineHeight: 36,
    color: colors.ink,
    marginTop: space.md,
  },
  lede: {
    fontFamily: fonts.body,
    fontSize: 16,
    lineHeight: 24,
    color: colors.inkSoft,
    marginTop: space.sm,
  },
  primary: {
    marginTop: space.xl,
    backgroundColor: colors.terracotta,
    borderRadius: radius.md,
    paddingVertical: 16,
    alignItems: "center",
  },
  primaryText: { fontFamily: fonts.bodySemiBold, fontSize: 16, color: colors.paper },
  secondaryRow: { flexDirection: "row", gap: space.sm, marginTop: space.sm },
  secondary: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    paddingVertical: 12,
    alignItems: "center",
    backgroundColor: colors.paper,
  },
  secondaryText: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.ink },
  error: {
    fontFamily: fonts.body,
    fontSize: 14,
    lineHeight: 20,
    color: colors.danger,
    marginTop: space.md,
  },
  sectionTitle: {
    fontFamily: fonts.bodySemiBold,
    fontSize: 16,
    color: colors.ink,
    marginTop: space.xl,
    marginBottom: space.sm,
  },
  quiet: { fontFamily: fonts.body, fontSize: 14, lineHeight: 20, color: colors.inkSoft },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    paddingVertical: space.sm,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  thumb: { width: 52, height: 52, borderRadius: radius.sm, backgroundColor: colors.paperDeep },
  thumbEmpty: { borderWidth: 1, borderColor: colors.line },
  rowText: { flex: 1 },
  rowTitle: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.ink },
  rowSub: { fontFamily: fonts.body, fontSize: 12, lineHeight: 16, color: colors.inkSoft, marginTop: 2 },
  rowChevron: { fontFamily: fonts.body, fontSize: 20, color: colors.inkSoft },
  credit: {
    fontFamily: fonts.body,
    fontSize: 12,
    lineHeight: 16,
    color: colors.inkSoft,
    marginTop: space.xl,
    textAlign: "center",
  },
});
