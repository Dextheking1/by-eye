// The result HUD: the plate photo with each item's real SAM 3.1 mask
// outline drawn over it, a marker at each item's centre of mass, a
// thin leader line out to a label at the edge. Restrained Jarvis:
// hairlines and small type, terracotta only where it means something.

import { useMemo, useState } from "react";
import { Image, LayoutChangeEvent, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import Svg, { Circle, G, Line, Path } from "react-native-svg";

import type { ScanItem } from "../api";
import { colors, fonts, radius } from "../theme";

interface Props {
  photoUri: string;
  imageWidth: number;
  imageHeight: number;
  items: ScanItem[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

interface LabelSpot {
  item: ScanItem;
  side: "left" | "right";
  yPx: number; // label centre, in container px
  anchorXPx: number;
  anchorYPx: number;
}

const LABEL_H = 40;
const LABEL_GAP = 6;

export default function HudOverlay({ photoUri, imageWidth, imageHeight, items, selectedId, onSelect }: Props) {
  const [box, setBox] = useState({ w: 0, h: 0 });

  const onLayout = (e: LayoutChangeEvent) => {
    const { width } = e.nativeEvent.layout;
    setBox({ w: width, h: (width * imageHeight) / imageWidth });
  };

  const labels = useMemo<LabelSpot[]>(() => {
    if (!box.w) return [];
    const spots: LabelSpot[] = items
      .filter((i) => i.anchor)
      .map((item) => {
        const ax = item.anchor!.x * box.w;
        const ay = item.anchor!.y * box.h;
        return {
          item,
          side: item.anchor!.x < 0.5 ? ("left" as const) : ("right" as const),
          yPx: ay,
          anchorXPx: ax,
          anchorYPx: ay,
        };
      });
    // De-overlap labels per side: sort by y, push down until they fit.
    for (const side of ["left", "right"] as const) {
      const group = spots.filter((s) => s.side === side).sort((a, b) => a.yPx - b.yPx);
      let cursor = LABEL_H / 2 + 2;
      for (const spot of group) {
        spot.yPx = Math.max(spot.yPx, cursor);
        cursor = spot.yPx + LABEL_H + LABEL_GAP;
      }
      const overflow = cursor - LABEL_GAP - box.h;
      if (overflow > 0) {
        for (const spot of group) spot.yPx -= overflow;
      }
    }
    return spots;
  }, [box, items]);

  const strokeW = Math.max(2, imageWidth / 480);

  return (
    <View style={[styles.frame, { aspectRatio: imageWidth / imageHeight }]} onLayout={onLayout}>
      <Image source={{ uri: photoUri }} style={styles.photo} resizeMode="cover" />
      {box.w > 0 && (
        <Svg style={styles.svgFill} viewBox={`0 0 ${imageWidth} ${imageHeight}`}>
          {items.map((item) => {
            const selected = item.id === selectedId;
            return item.outlines.map((outline, idx) => (
              <G key={`${item.id}-${idx}`} transform={`translate(${outline.tx}, ${outline.ty})`}>
                <Path
                  d={outline.d}
                  fill={selected ? "rgba(180, 85, 45, 0.30)" : "rgba(180, 85, 45, 0.07)"}
                  stroke={selected ? colors.terracotta : "rgba(243, 237, 226, 0.65)"}
                  strokeWidth={selected ? strokeW * 1.4 : strokeW}
                  onPress={() => onSelect(selected ? null : item.id)}
                />
              </G>
            ));
          })}
          {labels.map(({ item, side, yPx, anchorXPx, anchorYPx }) => {
            const selected = item.id === selectedId;
            const edgeX = side === "left" ? 10 : box.w - 10;
            const ax = (anchorXPx / box.w) * imageWidth;
            const ay = (anchorYPx / box.h) * imageHeight;
            const ex = (edgeX / box.w) * imageWidth;
            const ey = (yPx / box.h) * imageHeight;
            return (
              <G key={`leader-${item.id}`}>
                <Line
                  x1={ax}
                  y1={ay}
                  x2={ex}
                  y2={ey}
                  stroke={selected ? colors.terracotta : "rgba(243, 237, 226, 0.45)"}
                  strokeWidth={selected ? 2 : 1.2}
                />
                <Circle
                  cx={ax}
                  cy={ay}
                  r={selected ? 8 : 5.5}
                  fill={selected ? colors.terracotta : colors.hud}
                  stroke={selected ? colors.hudText : "rgba(243, 237, 226, 0.8)"}
                  strokeWidth={2}
                />
              </G>
            );
          })}
        </Svg>
      )}
      {labels.map(({ item, side, yPx }) => {
        const selected = item.id === selectedId;
        return (
          <TouchableOpacity
            key={`label-${item.id}`}
            activeOpacity={0.85}
            onPress={() => onSelect(selected ? null : item.id)}
            style={[
              styles.label,
              side === "left" ? { left: 10 } : { right: 10 },
              { top: yPx - LABEL_H / 2 },
              selected && styles.labelSelected,
            ]}
          >
            <Text style={styles.labelName} numberOfLines={1}>
              {item.name}
            </Text>
            <Text style={styles.labelAmount} numberOfLines={1}>
              {item.publishable ? item.amount_label ?? "" : "rough guess"}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    width: "100%",
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
  svgFill: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  label: {
    position: "absolute",
    maxWidth: "38%",
    minHeight: LABEL_H,
    justifyContent: "center",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radius.sm,
    backgroundColor: "rgba(22, 19, 14, 0.78)",
    borderWidth: 1,
    borderColor: "rgba(243, 237, 226, 0.22)",
  },
  labelSelected: {
    borderColor: colors.terracotta,
    backgroundColor: "rgba(22, 19, 14, 0.9)",
  },
  labelName: {
    fontFamily: fonts.bodySemiBold,
    fontSize: 12,
    lineHeight: 16,
    color: colors.hudText,
  },
  labelAmount: {
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    lineHeight: 16,
    color: colors.terracottaSoft,
  },
});
