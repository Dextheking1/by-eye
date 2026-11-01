// The wait, made honest and calm. The three stages name the real
// phases happening on the server (Spark identifies, SAM segments and
// Spark measures, the card is shaped). A thin scan line drifts over
// the dimmed photo; the bar fills with elapsed time and completes
// when the real answer lands.

import { useEffect, useRef, useState } from "react";
import { Animated, Easing, Image, StyleSheet, Text, View } from "react-native";

import { colors, fonts, radius, space } from "../theme";

const STAGES = [
  { until: 25, label: "Finding the food" },
  { until: 70, label: "Measuring each item" },
  { until: Infinity, label: "Writing it down" },
];

export default function AnalyzingScreen({ photoUri }: { photoUri: string }) {
  const [elapsed, setElapsed] = useState(0);
  const scanY = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const t = setInterval(() => setElapsed((e) => e + 0.5), 500);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(scanY, {
          toValue: 1,
          duration: 2600,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(scanY, {
          toValue: 0,
          duration: 2600,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [scanY]);

  const stage = STAGES.find((s) => elapsed < s.until) ?? STAGES[STAGES.length - 1];
  const progress = Math.min(0.96, elapsed / 100);
  const translateY = scanY.interpolate({ inputRange: [0, 1], outputRange: [8, 300] });

  return (
    <View style={styles.screen}>
      <View style={styles.frame}>
        <Image source={{ uri: photoUri }} style={styles.photo} resizeMode="cover" />
        <View style={styles.dim} />
        <Animated.View style={[styles.scanLine, { transform: [{ translateY }] }]} />
      </View>
      <Text style={styles.stage}>{stage.label}</Text>
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width: `${Math.round(progress * 100)}%` }]} />
      </View>
      <Text style={styles.quiet}>This takes about a minute. Your plate is being measured, not guessed.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.hud,
    padding: space.lg,
    paddingTop: space.xxl,
  },
  frame: {
    width: "100%",
    height: 320,
    borderRadius: radius.lg,
    overflow: "hidden",
    backgroundColor: colors.hudPanel,
    position: "relative",
  },
  photo: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    width: "100%",
    height: "100%",
  },
  dim: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(22, 19, 14, 0.45)",
  },
  scanLine: {
    position: "absolute",
    left: 12,
    right: 12,
    height: 2,
    borderRadius: 1,
    backgroundColor: colors.terracotta,
    opacity: 0.9,
  },
  stage: {
    fontFamily: fonts.display,
    fontSize: 24,
    lineHeight: 32,
    color: colors.hudText,
    marginTop: space.xl,
  },
  barTrack: {
    height: 3,
    borderRadius: 2,
    backgroundColor: colors.hudLine,
    marginTop: space.md,
    overflow: "hidden",
  },
  barFill: { height: "100%", backgroundColor: colors.terracotta, borderRadius: 2 },
  quiet: {
    fontFamily: fonts.body,
    fontSize: 14,
    lineHeight: 20,
    color: colors.hudMuted,
    marginTop: space.md,
  },
});
