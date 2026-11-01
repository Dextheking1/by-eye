// Web font loading: the faces are declared in global.css with
// @font-face under the same family names the theme uses, so web gets
// real Inter and the display serif without bundling font files.

import "./global.css";

export function useAppFonts(): boolean {
  return true;
}
