import { useState } from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import type { ScanResponse } from "../api";
import HudOverlay from "../components/HudOverlay";
import { saveRecipe } from "../storage";
import { colors, fonts, radius, space } from "../theme";

interface Props {
  scan: ScanResponse;
  photoUri: string;
  onBack: () => void;
  onRecipesChanged: () => void;
}

export default function ResultScreen({ scan, photoUri, onBack, onRecipesChanged }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const onSave = async () => {
    await saveRecipe(scan);
    setSaved(true);
    onRecipesChanged();
  };

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <TouchableOpacity onPress={onBack} activeOpacity={0.7} style={styles.backRow}>
        <Text style={styles.backText}>‹ Your plates</Text>
      </TouchableOpacity>
      <Text style={styles.title}>Here is what is on your plate</Text>

      <View style={styles.hudWrap}>
        <HudOverlay
          photoUri={photoUri}
          imageWidth={scan.image.width}
          imageHeight={scan.image.height}
          items={scan.items}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
      </View>
      <Text style={styles.hint}>Tap an item to see exactly where it was found.</Text>

      <View style={styles.list}>
        {scan.items.map((item) => {
          const selected = item.id === selectedId;
          return (
            <TouchableOpacity
              key={item.id}
              style={[styles.row, selected && styles.rowSelected]}
              activeOpacity={0.85}
              onPress={() => setSelectedId(selected ? null : item.id)}
            >
              <View style={styles.rowText}>
                <Text style={styles.rowName}>{item.name}</Text>
                {item.coverage_percent != null && (
                  <Text style={styles.rowNote}>covers {item.coverage_percent}% of the photo</Text>
                )}
                {item.note ? <Text style={styles.rowNote}>{item.note}</Text> : null}
              </View>
              <View style={styles.rowAmount}>
                {item.amount_label ? (
                  <Text style={[styles.amount, !item.publishable && styles.amountStruck]}>
                    {item.amount_label}
                  </Text>
                ) : (
                  <Text style={styles.amountMissing}>not measured</Text>
                )}
                {item.publishable && item.band_label ? (
                  <Text style={styles.band}>between {item.band_label}</Text>
                ) : item.amount_label ? (
                  <Text style={styles.band}>rough guess only</Text>
                ) : null}
              </View>
            </TouchableOpacity>
          );
        })}
      </View>

      <TouchableOpacity
        style={[styles.save, saved && styles.saveDone]}
        activeOpacity={0.88}
        onPress={onSave}
        disabled={saved}
      >
        <Text style={styles.saveText}>{saved ? "Saved to your recipes" : "Save this recipe"}</Text>
      </TouchableOpacity>

      <Text style={styles.credit}>{scan.credit}</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.hud },
  content: { padding: space.lg, paddingTop: space.xl, paddingBottom: space.xl },
  backRow: { paddingVertical: space.xs, alignSelf: "flex-start" },
  backText: { fontFamily: fonts.bodyMedium, fontSize: 14, color: colors.hudMuted },
  title: {
    fontFamily: fonts.display,
    fontSize: 24,
    lineHeight: 32,
    color: colors.hudText,
    marginTop: space.sm,
    marginBottom: space.md,
  },
  hudWrap: { marginHorizontal: -space.xs },
  hint: {
    fontFamily: fonts.body,
    fontSize: 12,
    lineHeight: 16,
    color: colors.hudMuted,
    marginTop: space.sm,
  },
  list: { marginTop: space.lg, borderTopWidth: 1, borderTopColor: colors.hudLine },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: space.md,
    paddingVertical: space.md,
    paddingHorizontal: space.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.hudLine,
    borderRadius: radius.sm,
  },
  rowSelected: { backgroundColor: colors.hudPanel },
  rowText: { flex: 1 },
  rowName: { fontFamily: fonts.bodySemiBold, fontSize: 16, color: colors.hudText },
  rowNote: {
    fontFamily: fonts.body,
    fontSize: 12,
    lineHeight: 16,
    color: colors.hudMuted,
    marginTop: 2,
  },
  rowAmount: { alignItems: "flex-end" },
  amount: { fontFamily: fonts.bodySemiBold, fontSize: 16, color: colors.terracottaSoft },
  amountStruck: { textDecorationLine: "line-through", color: colors.hudMuted },
  amountMissing: { fontFamily: fonts.body, fontSize: 14, color: colors.hudMuted },
  band: { fontFamily: fonts.body, fontSize: 12, lineHeight: 16, color: colors.hudMuted, marginTop: 2 },
  save: {
    marginTop: space.xl,
    backgroundColor: colors.terracotta,
    borderRadius: radius.md,
    paddingVertical: 16,
    alignItems: "center",
  },
  saveDone: { backgroundColor: colors.hudPanel, borderWidth: 1, borderColor: colors.terracotta },
  saveText: { fontFamily: fonts.bodySemiBold, fontSize: 16, color: colors.paper },
  credit: {
    fontFamily: fonts.body,
    fontSize: 12,
    lineHeight: 16,
    color: colors.hudMuted,
    marginTop: space.lg,
    textAlign: "center",
  },
});
