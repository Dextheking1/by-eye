// Local declarations for packages whose shipped types are missing in
// this install (the font packages ship none; react-native-svg's type
// files did not survive install). Kept narrow: only what the app uses.

declare module "*.css";

declare module "@expo-google-fonts/inter" {
  export const Inter_400Regular: number;
  export const Inter_500Medium: number;
  export const Inter_600SemiBold: number;
  export const Inter_700Bold: number;
}

declare module "@expo-google-fonts/fraunces" {
  export const Fraunces_600SemiBold: number;
}

declare module "react-native-svg" {
  import type { ComponentType } from "react";
  import type { StyleProp, ViewStyle } from "react-native";

  export interface SvgProps {
    style?: StyleProp<ViewStyle>;
    viewBox?: string;
    width?: number | string;
    height?: number | string;
    children?: React.ReactNode;
  }
  export interface ShapeProps {
    fill?: string;
    stroke?: string;
    strokeWidth?: number;
    opacity?: number;
    onPress?: () => void;
  }
  const Svg: ComponentType<SvgProps>;
  export default Svg;
  export const G: ComponentType<{ transform?: string; children?: React.ReactNode }>;
  export const Path: ComponentType<ShapeProps & { d: string }>;
  export const Circle: ComponentType<ShapeProps & { cx: number; cy: number; r: number }>;
  export const Line: ComponentType<
    ShapeProps & { x1: number; y1: number; x2: number; y2: number }
  >;
}
